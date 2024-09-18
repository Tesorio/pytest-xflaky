import enum
import json
import os
import shutil
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import pytest
from pytest_jsonreport.plugin import pytest_configure as jsonreport_pytest_configure
from pytest_xflaky.add_decorator import add_decorators

from .github_blame import GithubBlame


class XflakyAction(enum.Enum):
    COLLECT = "collect"
    FIX = "fix"
    REPORT = "report"


@dataclass
class Test:
    nodeid: str
    lineno: int

    def __str__(self):
        return f"{self.nodeid}:{self.lineno}"

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return other.nodeid == self.nodeid and other.lineno == self.lineno

    def get_filename(self):
        if "::" in self.nodeid:
            return self.nodeid.split("::")[0]


@dataclass
class MaybeFlakyTest:
    test: Test
    ok: int
    failed: int
    min_failures: bool
    min_successes: bool

    def is_flaky(self):
        return self.ok >= self.min_successes and self.failed >= self.min_failures


class TextFileReportWriter:
    def __init__(self, config):
        self.text_report_file = config.option.xflaky_text_report_file
        self.fp = open(self.text_report_file, "w")

    def close(self):
        self.fp.close()

    def _print(self, line):
        line = f"{line}\n"
        sys.stdout.write(line)
        self.fp.write(line)

    def write(self, tests: list[MaybeFlakyTest], flaky: int):
        self._print("FAILED TESTS:")
        failed_tests = [test for test in tests if test.failed > 0]
        for maybe_flaky_test in failed_tests:
            label = " FLAKY" if maybe_flaky_test.is_flaky() else ""
            self._print(
                f"{maybe_flaky_test.test} (failed: {maybe_flaky_test.failed}/{maybe_flaky_test.ok + maybe_flaky_test.failed}){label}"
            )

        failures = sum(test.failed for test in tests)
        successes = sum(test.ok for test in tests)
        runs = failures + successes

        self._print("-")
        self._print(
            f"Flaky tests result (tests: {len(tests)}, runs: {runs}, successes: {successes}, failures: {failures}, flaky: {flaky})",
        )


class GitHubReportWriter:
    def __init__(self, config):
        self.config = config

    def write(self, tests: list[MaybeFlakyTest], flaky: int):
        token = self.config.option.xflaky_github_token
        if not token:
            token = os.getenv("GITHUB_TOKEN")

        failed_tests = [test for test in tests if test.failed > 0]
        github_blame = GithubBlame(token)

        report = {}
        for maybe_flaky_test in failed_tests:
            data = asdict(maybe_flaky_test)
            data["is_flaky"] = maybe_flaky_test.is_flaky()
            if data["is_flaky"]:
                filename = maybe_flaky_test.test.get_filename()
                lineno = maybe_flaky_test.test.lineno
                data["blame"] = github_blame.blame(filename, lineno)
                if data["blame"]:
                    report_key = data["blame"]["github_username"]
                else:
                    report_key = None

                report.setdefault(report_key, []).append(data)

        with open(self.config.option.xflaky_github_report_file, "w") as fp:
            json.dump(report, fp)

    def close(self):
        pass


class Plugin:
    def __init__(self, config, action: XflakyAction):
        self.config = config
        self.action = action

        match action:
            case XflakyAction.COLLECT:
                self.action_collect()
            case XflakyAction.REPORT:
                self.action_report()
            case XflakyAction.FIX:
                self.action_fix()
            case _:
                raise NotImplementedError(action)

    def action_collect(self):
        self.check_jsonreport()
        self.make_reports_dir()

        report_file = self.config.option.json_report_file
        directory = Path(self.config.option.xflaky_reports_directory)
        filename = f"{uuid.uuid4()}-{os.path.basename(report_file)}"
        self.new_report_file = str(directory / filename)

    def action_report(self):
        finder = FlakyTestFinder(
            directory=self.config.option.xflaky_reports_directory,
            min_failures=self.config.option.xflaky_min_failures,
            min_successes=self.config.option.xflaky_min_successes,
        )

        tests, flaky = finder.run()

        report_writers = [
            TextFileReportWriter(self.config),
        ]

        if self.config.option.xflaky_github_report:
            report_writers.append(GitHubReportWriter(self.config))

        for report_writer in report_writers:
            report_writer.write(tests, flaky)
            report_writer.close()

        if flaky > 0:
            pytest.exit("Flaky tests were found", returncode=1)
        else:
            pytest.exit("No flaky tests found", returncode=0)

    def action_fix(self):
        add_decorators(self.config.option.xflaky_text_report_file)

        pytest.exit("Fixers applied", returncode=0)

    def check_jsonreport(self):
        if not self.config.pluginmanager.hasplugin("pytest_jsonreport"):
            jsonreport_pytest_configure(self.config)

        if not self.config.option.json_report:
            raise Exception("cannot run without --json-report")

    def make_reports_dir(self):
        try:
            os.makedirs(self.config.option.xflaky_reports_directory)
        except FileExistsError:
            pass

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session):
        report_file = self.config.option.json_report_file
        shutil.copy(report_file, self.new_report_file)

    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("-", "XFLAKY report")
        terminalreporter.write_line(f"Report file copied to {self.new_report_file}")


class FlakyTestFinder:
    def __init__(self, *, directory: str, min_failures: int, min_successes: int):
        self.directory = directory
        self.min_failures = min_failures
        self.min_successes = min_successes

    def run(self) -> list[MaybeFlakyTest]:
        cache = {}
        for test, failure in self.collect_tests():
            cache.setdefault(
                test,
                MaybeFlakyTest(
                    test=test,
                    ok=0,
                    failed=0,
                    min_failures=self.min_failures,
                    min_successes=self.min_successes,
                ),
            )

            if failure:
                cache[test].failed += 1
            else:
                cache[test].ok += 1

        tests = list(cache.values())
        flaky_total = sum(1 for test in tests if test.is_flaky())
        return tests, flaky_total

    def collect_tests(self):
        for f in os.listdir(self.directory):
            if f.endswith(".json"):
                yield from self.iter_parse_file(f)

    def iter_parse_file(self, filename):
        outcomes = {"error", "failed"}
        with open(f"{self.directory}/{filename}") as f:
            data = json.load(f)
            for test in data["tests"]:
                yield (
                    Test(nodeid=test["nodeid"], lineno=test["lineno"]),
                    test["outcome"] in outcomes,
                )


def xflaky_action_from_config(config) -> XflakyAction:
    action = None

    if config.option.xflaky_report:
        action = XflakyAction.REPORT

    if config.option.xflaky_fix:
        if action:
            pytest.exit(
                "Cannot use more than one xflaky action at a time, found: --xflaky-report and --xflaky-fix",
                returncode=1,
            )

        action = XflakyAction.FIX

    if config.option.xflaky_collect:
        if action:
            pytest.exit(
                "Cannot use more than one xflaky action at a time, found: --xflaky and --xflaky-report",
                returncode=1,
            )

        action = XflakyAction.COLLECT

    return action


def pytest_configure(config):
    action = xflaky_action_from_config(config)
    if not action:
        return

    plugin = Plugin(config, action)
    config.pluginmanager.register(plugin)


def pytest_addoption(parser):
    group = parser.getgroup("xflaky")
    group.addoption(
        "--xflaky-collect",
        default=False,
        action="store_true",
        help="Collect flaky tests",
    )
    group.addoption(
        "--xflaky-text-report-file",
        default=".xflaky_report.txt",
        help="File to store text report",
    )
    group.addoption(
        "--xflaky-github-report",
        default=False,
        action="store_true",
        help="Generate GitHub report",
    )
    group.addoption(
        "--xflaky-github-token",
        default="",
        help="GitHub token to use for API requests (defaults to GITHUB_TOKEN)",
    )
    group.addoption(
        "--xflaky-github-report-file",
        default=".xflaky_report_github.json",
        help="File to store GitHub report",
    )
    group.addoption(
        "--xflaky-reports-directory",
        default=".reports",
        help="Directory to store json reports",
    )
    group.addoption(
        "--xflaky-report",
        default=False,
        action="store_true",
        help="Generate xflaky report",
    )
    group.addoption(
        "--xflaky-fix",
        default=False,
        action="store_true",
        help="Fix flaky tests",
    )
    group.addoption(
        "--xflaky-min-failures",
        default=1,
        help="Minimum number of failures to consider a test flaky",
        type=int,
    )
    group.addoption(
        "--xflaky-min-successes",
        default=1,
        help="Minimum number of successes to consider a test flaky",
        type=int,
    )

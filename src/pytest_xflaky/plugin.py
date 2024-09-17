import collections
import json
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from pytest_jsonreport.plugin import pytest_configure as jsonreport_pytest_configure
from pytest_xflaky.add_decorator import add_decorators


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
        self.final_report_file = config.option.xflaky_final_report_file
        self.fp = open(self.final_report_file, "w")

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
        succeses = sum(test.ok for test in tests)
        runs = failures + succeses

        self._print("-")
        self._print(
            f"Flaky tests result (tests: {len(tests)}, runs: {runs}, succeses: {succeses}, failures: {failures}, flaky: {flaky})",
        )


class Plugin:
    def __init__(self, config):
        self.config = config

        self.make_reports_dir()

        if self.config.option.xflaky_report:
            report_writer = TextFileReportWriter(self.config)

            if self.generate_report(report_writer):
                if not self.config.option.xflaky_fix:
                    pytest.exit("Flaky tests were found", returncode=1)

                else:
                    add_decorators(config.option.xflaky_final_report_file)
                    pytest.exit("Fixers applied", returncode=0)

            else:
                pytest.exit("No flaky tests found", returncode=0)

        else:
            self.check_jsonreport()

        report_file = self.config.option.json_report_file
        directory = Path(self.config.option.xflaky_reports_directory)
        filename = f"{uuid.uuid4()}-{os.path.basename(report_file)}"
        self.new_report_file = str(directory / filename)

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

    def generate_report(self, report_writer):
        finder = FlakyTestFinder(
            directory=self.config.option.xflaky_reports_directory,
            min_failures=self.config.option.xflaky_min_failures,
            min_successes=self.config.option.xflaky_min_succeses,
        )

        tests, flaky = finder.run()

        report_writer.write(tests, flaky)
        report_writer.close()

        return flaky > 0

    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("-", "XFLAKY report")
        terminalreporter.write_line(f"Report file copied to {self.new_report_file}")


class FlakyTestFinder:
    def __init__(self, *, directory: str, min_failures: int):
        self.directory = directory
        self.min_failures = min_failures

    def run(self) -> list[MaybeFlakyTest]:
        cache = {}
        for test, failure in self.collect_tests():
            cache.setdefault(
                test,
                MaybeFlakyTest(
                    test=test, ok=0, failed=0, min_failures=self.min_failures
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


def pytest_configure(config):
    if not config.option.xflaky:
        return

    plugin = Plugin(config)
    config.pluginmanager.register(plugin)


def pytest_addoption(parser):
    group = parser.getgroup("xflaky")
    group.addoption(
        "--xflaky",
        default=False,
        action="store_true",
        help="Enable xflaky",
    )
    group.addoption(
        "--xflaky-final-report-file",
        default=".xflaky_report.txt",
        help="File to store final report",
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
        help="Find flaky tests",
    )
    group.addoption(
        "--xflaky-fix",
        default=False,
        action="store_true",
        help="Apply fixes",
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

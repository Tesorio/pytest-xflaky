import collections
import json
import os
import shutil
import sys
import uuid
from dataclasses import dataclass

import pytest
from pytest_jsonreport.plugin import pytest_configure as jsonreport_pytest_configure


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
class FlakyTest:
    test: Test
    ok: int
    failed: int


class Plugin:
    def __init__(self, config):
        self.config = config

        self.check_jsonreport()
        self.make_reports_dir()

        if self.config.option.xflaky_report:
            self.generate_report()

        report_file = self.config.option.json_report_file
        directory = self.config.option.xflaky_reports_directory
        self.new_report_file = f"{uuid.uuid4()}-{os.path.basename(report_file)}"

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

    def generate_report(self):
        finder = FlakyTestFinder(
            directory=self.config.option.xflaky_reports_directory,
            min_failures=self.config.option.xflaky_min_failures,
        )

        flaky_tests = finder.run()
        if flaky_tests:
            self.print_report(flaky_tests)
            pytest.exit(1)

        print("No flaky tests found")

    def print_report(self, flaky_tests):
        for flaky_test in flaky_tests:
            print(
                f"Flaky test found: {flaky_test.test} (ok: {flaky_test.ok}, failed: {flaky_test.failed}"
            )

    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("-", "XFLAKY report")
        terminalreporter.write_line(f"Report file copied to {self.new_report_file}")


class FlakyTestFinder:
    def __init__(self, *, directory: str, min_failures: int):
        self.directory = directory
        self.min_failures = min_failures

    def run(self) -> list[FlakyTest]:
        ok = {}
        failures = {}
        for test, failure in self.collect_tests():
            if failure:
                failures.setdefault(test, 0)
                failures[test] += 1
            else:
                ok.setdefault(test, 0)
                ok[test] += 1

        flaky_tests = []
        for test in failures:
            if failures[test] > self.min_failures:
                ok_ = ok.get(test, 0)
                if ok_ > 0:
                    flaky_tests.append(
                        FlakyTest(test=test, ok=ok_, failed=failures[test])
                    )

        return flaky_tests

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
        "--xflaky-min-failures",
        default=1,
        help="Minimum number of failures to consider a test flaky",
    )

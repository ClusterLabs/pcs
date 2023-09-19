import sys
import unittest
from dataclasses import (
    dataclass,
    field,
)
from io import StringIO


class ParallelTestManager:
    def __init__(self, result_class, verbosity: int):
        self.result_class = result_class
        self.verbosity = verbosity

    def run_test(self, test_name: str) -> "ParallelTestResult":
        test = unittest.defaultTestLoader.loadTestsFromName(test_name)
        test_runner = ParallelTestRunner(
            verbosity=self.verbosity, resultclass=self.result_class
        )
        result = test_runner.run(test)
        return ParallelTestResult(
            result.testsRun,
            result.wasSuccessful(),
            result.get_errors(),
            result.get_failures(),
            result.get_skips(),
            result.get_error_names(),
            result.get_failed_names(),
            len(result.errors),
            len(result.failures),
            len(result.skipped),
            len(result.expectedFailures),
            len(result.unexpectedSuccesses),
        )


class VanillaTextTestResult(unittest.TextTestResult):
    # pylint: disable=no-self-use
    def get_failed_names(self) -> list[str]:
        return []

    def get_error_names(self) -> list[str]:
        return []

    def get_errors(self) -> list[str]:
        return self._get_fail_descriptions("ERROR", self.errors)

    def get_failures(self) -> list[str]:
        return self._get_fail_descriptions("FAIL", self.failures)

    def get_skips(self) -> dict[str, int]:
        return {}

    def _get_fail_descriptions(
        self, severity: str, item_list: list[tuple[unittest.TestCase, str]]
    ) -> list[str]:
        line_list = []
        for test, err in item_list:
            line_list.append(self.separator1)
            line_list.append(f"{severity}: {self.getDescription(test)}")
            line_list.append(self.separator2)
            line_list.append(f"{err}")
        return line_list

    def stopTest(self, test):
        # super().stopTest(test)
        if self.stream.seekable():
            self.stream.seek(0)
        if self.stream.readable():
            sys.stderr.write(self.stream.read())
        sys.stderr.flush()


@dataclass
class ParallelTestResult:
    """Representation of test result that can be pickled"""

    # pylint: disable=too-many-instance-attributes
    tests_run: int = 0
    was_successful: bool = True
    error_reports: list[str] = field(default_factory=list)
    failure_reports: list[str] = field(default_factory=list)
    skip_reports: dict[str, int] = field(default_factory=dict)
    error_names: list[str] = field(default_factory=list)
    failure_names: list[str] = field(default_factory=list)
    error_count: int = 0
    failure_count: int = 0
    skip_count: int = 0
    expected_failure_count: int = 0
    unexpected_success_count: int = 0

    def print_summary(
        self,
        time: float,
        vanilla: bool,
        last_slash: bool,
    ) -> None:
        # pylint: disable=import-outside-toplevel too-many-branches
        summary_lines = []
        if self.error_count or self.failure_count or self.skip_count:
            summary_lines.append("")
        elif vanilla:
            summary_lines.append("")

        summary_lines.extend(self.error_reports)
        summary_lines.extend(self.failure_reports)

        if not vanilla:
            from pcs_test.tools.color_text_runner.format import Output

            output = Output(True)
            if self.error_count or self.failure_count or self.skip_count:
                summary_lines.append(unittest.TextTestResult.separator1)
                summary_lines.append("")
            if self.error_count or self.failure_count:
                summary_lines.append("")
                summary_lines.append(
                    output.red(
                        "for running failed tests only (errors are first then "
                        "failures):"
                    )
                )
                error_overview = " \\\n".join(
                    output.lightgrey(err)
                    for err in self.error_names + self.failure_names
                )
                if last_slash:
                    error_overview = f"{error_overview} \\"
                summary_lines.append("")
                summary_lines.append(error_overview)
            if self.skip_count:
                summary_lines.append("")
                summary_lines.append(
                    output.blue("Some tests have been skipped:")
                )
                summary_lines.append(
                    "\n".join(
                        [
                            f"{reason}\n  ({count}x)"
                            for reason, count in sorted(
                                self.skip_reports.items()
                            )
                        ]
                    )
                )
            summary_lines.append("")

        summary_lines.append(unittest.TextTestResult.separator2)
        summary_lines.append(
            f"Ran {self.tests_run} test{'s' if self.tests_run != 1 else ''} in "
            f"{time:.3f}s"
        )
        summary_lines.append("")

        infos = []
        if self.failure_count:
            infos.append(f"failures={self.failure_count}")
        if self.error_count:
            infos.append(f"errors={self.error_count}")
        if self.skip_count:
            infos.append(f"skipped={self.skip_count}")
        if self.expected_failure_count:
            infos.append(f"expected failures={self.expected_failure_count}")
        if self.unexpected_success_count:
            infos.append(
                f"unexpected successes={self.unexpected_success_count}"
            )
        info_line = "{result}{infos}".format(
            result="OK" if self.was_successful else "FAILED",
            infos=f" ({', '.join(infos)})" if infos else "",
        )
        summary_lines.append(info_line)
        print("\n".join(summary_lines), file=sys.stderr)


class ParallelTestRunner(unittest.TextTestRunner):
    def _makeResult(self):
        return self.resultclass(
            # pylint: disable=protected-access
            unittest.runner._WritelnDecorator(StringIO()),
            self.descriptions,
            self.verbosity,
        )

    def run(self, test):
        result = self._makeResult()
        result.failfast = self.failfast
        result.buffer = self.buffer
        start_test_run = getattr(result, "startTestRun", None)
        if start_test_run is not None:
            start_test_run()
        try:
            test(result)
        finally:
            stop_test_run = getattr(result, "stopTestRun", None)
            if stop_test_run is not None:
                stop_test_run()
        return result


def aggregate_test_results(
    results: list[ParallelTestResult],
) -> ParallelTestResult:
    result = ParallelTestResult()
    for res in results:
        result.tests_run += res.tests_run
        result.error_reports.extend(res.error_reports)
        result.failure_reports.extend(res.failure_reports)
        result.error_names.extend(res.error_names)
        result.failure_names.extend(res.failure_names)
        result.was_successful = result.was_successful and res.was_successful
        result.error_count += res.error_count
        result.failure_count += res.failure_count
        result.skip_count += res.skip_count
        result.expected_failure_count += res.expected_failure_count
        result.unexpected_success_count += res.unexpected_success_count
        for reason, count in res.skip_reports.items():
            result.skip_reports[reason] = (
                result.skip_reports.get(reason, 0) + count
            )
    result.error_names = sorted(set(result.error_names))
    result.failure_names = sorted(set(result.failure_names))
    return result

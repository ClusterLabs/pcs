import unittest

from pcs_test.tools.color_text_runner.format import (
    Format,
    Output,
    separator1,
)
from pcs_test.tools.color_text_runner.writer import (
    DotWriter,
    ImprovedVerboseWriter,
    StandardVerboseWriter,
    TimeWriter,
    Writer,
)
from pcs_test.tools.parallel_test_runner import VanillaTextTestResult


class ColorTextTestResult(VanillaTextTestResult):
    slash_last = False
    traditional_verbose = False
    traceback_highlight = False
    fast_info = False
    rich_format = True
    measure_time = False

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.verbosity = 2 if self.traditional_verbose else verbosity

        self._format = Format(Output(self.rich_format))
        # pylint: disable=invalid-name
        self.reportWriter = self.__chooseWriter()(
            self.stream,
            self._format,
            self.descriptions,
            self.traceback_highlight,
            self.fast_info,
        )
        self.skip_map = {}

    def startTest(self, test):
        super(unittest.TextTestResult, self).startTest(test)
        self.reportWriter.startTest(test)

    def addSuccess(self, test):
        super(unittest.TextTestResult, self).addSuccess(test)
        self.reportWriter.addSuccess(test)

    def addError(self, test, err):
        super(unittest.TextTestResult, self).addError(test, err)
        self.reportWriter.addError(test, err, traceback=self.errors[-1][1])

    def addFailure(self, test, err):
        super(unittest.TextTestResult, self).addFailure(test, err)
        self.reportWriter.addFailure(test, err, traceback=self.failures[-1][1])

    def addSkip(self, test, reason):
        super(unittest.TextTestResult, self).addSkip(test, reason)
        self.skip_map.setdefault(reason, []).append(test)
        self.reportWriter.addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        super(unittest.TextTestResult, self).addExpectedFailure(test, err)
        self.reportWriter.addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        super(unittest.TextTestResult, self).addUnexpectedSuccess(test)
        self.reportWriter.addUnexpectedSuccess(test)

    def get_failed_names(self) -> list[str]:
        return [self._format.test_name(test) for test, _ in self.failures]

    def get_error_names(self) -> list[str]:
        return [self._format.test_name(test) for test, _ in self.errors]

    def get_errors(self) -> list[str]:
        return self._format.error_list(
            "ERROR", self.errors, self.descriptions, self.traceback_highlight
        )

    def get_failures(self) -> list[str]:
        return self._format.error_list(
            "FAIL", self.failures, self.descriptions, self.traceback_highlight
        )

    def get_skips(self) -> dict[str, int]:
        return {
            reason: len(test_list)
            for reason, test_list in self.skip_map.items()
        }

    def printErrors(self):
        error_lines = self.get_errors() + self.get_failures()
        if self.errors or self.failures or self.skip_map:
            error_lines.extend([separator1, ""])
        if self.errors + self.failures:
            error_lines.extend(
                [""]
                + self._format.error_overview(
                    self.errors, self.failures, self.slash_last
                )
            )

        if self.skip_map:
            error_lines.extend([""] + self._format.skip_overview(self.skip_map))

        if self.verbosity:
            error_lines.insert(0, "")

        for line in error_lines:
            self.stream.writeln(line)

    def __chooseWriter(self):  # pylint: disable=invalid-name
        if self.measure_time:
            return TimeWriter
        if self.traditional_verbose:
            return StandardVerboseWriter
        if self.verbosity > 1:
            return ImprovedVerboseWriter
        if self.verbosity > 0:
            return DotWriter
        return Writer


def get_text_test_result_class(
    *,
    slash_last_fail_in_overview=False,
    traditional_verbose=False,
    traceback_highlight=False,
    fast_info=False,
    rich_format=True,
    measure_time=False,
):
    ColorTextTestResult.slash_last = slash_last_fail_in_overview
    ColorTextTestResult.traditional_verbose = traditional_verbose
    ColorTextTestResult.traceback_highlight = traceback_highlight
    ColorTextTestResult.fast_info = fast_info
    ColorTextTestResult.rich_format = rich_format
    ColorTextTestResult.measure_time = measure_time

    return ColorTextTestResult

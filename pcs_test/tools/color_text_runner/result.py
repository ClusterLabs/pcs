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


def get_text_test_result_class(
    slash_last_fail_in_overview=False,
    traditional_verbose=False,
    traceback_highlight=False,
    fast_info=False,
    rich_format=True,
    measure_time=False,
):
    class ColorTextTestResult(unittest.TextTestResult):
        def __init__(self, stream, descriptions, verbosity):
            super().__init__(stream, descriptions, verbosity)
            self.verbosity = 2 if traditional_verbose else verbosity

            self._format = Format(Output(rich_format))
            # pylint: disable=invalid-name
            self.reportWriter = self.__chooseWriter()(
                self.stream,
                self._format,
                self.descriptions,
                traceback_highlight,
                fast_info,
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
            self.reportWriter.addFailure(
                test, err, traceback=self.failures[-1][1]
            )

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

        def printErrors(self):
            line_list = self._format.error_list(
                "ERROR",
                self.errors,
                self.descriptions,
                traceback_highlight,
            ) + self._format.error_list(
                "FAIL",
                self.failures,
                self.descriptions,
                traceback_highlight,
            )

            if (self.errors + self.failures) or self.skip_map:
                line_list.extend([separator1, ""])

            if self.errors + self.failures:
                line_list.extend(
                    [""]
                    + self._format.error_overview(
                        self.errors, self.failures, slash_last_fail_in_overview
                    )
                )

            if self.skip_map:
                line_list.extend([""] + self._format.skips(self.skip_map))

            if self.verbosity:
                line_list.insert(0, "")

            for line in line_list:
                self.stream.writeln(line)

        def __chooseWriter(self):  # pylint: disable=invalid-name
            if measure_time:
                return TimeWriter
            if traditional_verbose:
                return StandardVerboseWriter
            if self.verbosity > 1:
                return ImprovedVerboseWriter
            if self.verbosity > 0:
                return DotWriter
            return Writer

    return ColorTextTestResult

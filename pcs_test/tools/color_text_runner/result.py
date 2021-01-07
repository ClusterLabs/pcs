import unittest

from pcs_test.tools.color_text_runner.format import (
    separator1,
    format_error_list,
    format_error_overview,
    format_skips,
)
from pcs_test.tools.color_text_runner.writer import (
    DotWriter,
    StandardVerboseWriter,
    ImprovedVerboseWriter,
    Writer,
)


def get_text_test_result_class(
    slash_last_fail_in_overview=False,
    traditional_verbose=False,
    traceback_highlight=False,
    fast_info=False,
):
    # TextTestResult is neede here. Direct inheriting from TestResult does not
    # work in python 2.6
    TextTestResult = unittest.TextTestResult

    class ColorTextTestResult(TextTestResult):
        # pylint: disable=bad-super-call, invalid-name
        def __init__(self, stream, descriptions, verbosity):
            super().__init__(stream, descriptions, verbosity)
            self.verbosity = 2 if traditional_verbose else verbosity

            self.reportWriter = self.__chooseWriter()(
                self.stream,
                self.descriptions,
                traceback_highlight,
                fast_info,
            )
            self.skip_map = {}

        def startTest(self, test):
            super(TextTestResult, self).startTest(test)
            self.reportWriter.startTest(test)

        def addSuccess(self, test):
            super(TextTestResult, self).addSuccess(test)
            self.reportWriter.addSuccess(test)

        def addError(self, test, err):
            super(TextTestResult, self).addError(test, err)
            self.reportWriter.addError(test, err, traceback=self.errors[-1][1])

        def addFailure(self, test, err):
            super(TextTestResult, self).addFailure(test, err)
            self.reportWriter.addFailure(
                test, err, traceback=self.failures[-1][1]
            )

        def addSkip(self, test, reason):
            super(TextTestResult, self).addSkip(test, reason)
            self.skip_map.setdefault(reason, []).append(test)
            self.reportWriter.addSkip(test, reason)

        def addExpectedFailure(self, test, err):
            super(TextTestResult, self).addExpectedFailure(test, err)
            self.reportWriter.addExpectedFailure(test, err)

        def addUnexpectedSuccess(self, test):
            super(TextTestResult, self).addUnexpectedSuccess(test)
            self.reportWriter.addUnexpectedSuccess(test)

        def printErrors(self):
            line_list = format_error_list(
                "ERROR",
                self.errors,
                self.descriptions,
                traceback_highlight,
            ) + format_error_list(
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
                    + format_error_overview(
                        self.errors, self.failures, slash_last_fail_in_overview
                    )
                )

            if self.skip_map:
                line_list.extend([""] + format_skips(self.skip_map))

            if self.verbosity:
                line_list.insert(0, "")

            for line in line_list:
                self.stream.writeln(line)

        def __chooseWriter(self):
            if traditional_verbose:
                return StandardVerboseWriter
            if self.verbosity > 1:
                return ImprovedVerboseWriter
            if self.verbosity > 0:
                return DotWriter
            return Writer

    return ColorTextTestResult

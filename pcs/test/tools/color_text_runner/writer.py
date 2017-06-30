from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.color_text_runner.format import (
    blue,
    red,
    green,
    lightgrey,
    get_description,
    format_module,
    format_test_method_name,
    format_traceback,
)


class Writer(object):
    def __init__(
        self, stream, descriptions, traceback_highlight=False, fast_info=False,
    ):
        self.stream = stream
        self.descriptions = descriptions
        self.traceback_highlight = traceback_highlight
        self.fast_info = fast_info

    def addSuccess(self, test):
        pass

    def addError(self, test, err, traceback):
        pass

    def addFailure(self, test, err, traceback):
        pass

    def addSkip(self, test, reason):
        pass

    def startTest(self, test):
        pass

    def addExpectedFailure(self, test, err):
        pass

    def addUnexpectedSuccess(self, test):
        pass

    def show_fast_info(self, traceback):
        if self.fast_info:
            self.stream.writeln()
            self.stream.writeln(
                format_traceback(traceback) if self.traceback_highlight
                    else traceback
            )

class DotWriter(Writer):
    def addSuccess(self, test):
        self.stream.write(green("."))
        self.stream.flush()

    def addError(self, test, err, traceback):
        self.stream.write(red('E'))
        self.stream.flush()
        self.show_fast_info(traceback)

    def addFailure(self, test, err, traceback):
        self.stream.write(red('F'))
        self.stream.flush()
        self.show_fast_info(traceback)

    def addSkip(self, test, reason):
        self.stream.write(blue('s'))
        self.stream.flush()

    def addExpectedFailure(self, test, err):
        self.stream.write(blue('x'))
        self.stream.flush()

    def addUnexpectedSuccess(self, test):
        self.stream.write(red('u'))
        self.stream.flush()

class StandardVerboseWriter(Writer):
    def addSuccess(self, test):
        self.stream.writeln(green("OK"))

    def addError(self, test, err, traceback):
        self.stream.writeln(red("ERROR"))
        self.show_fast_info(traceback)

    def addFailure(self, test, err, traceback):
        self.stream.writeln(red("FAIL"))
        self.show_fast_info(traceback)

    def addSkip(self, test, reason):
        self.stream.writeln(
            blue("skipped {0!r}".format(reason))
        )

    def startTest(self, test):
        self.stream.write(get_description(test, self.descriptions))
        self.stream.write(" ... ")
        self.stream.flush()

    def addExpectedFailure(self, test, err):
        self.stream.writeln(blue("expected failure"))

    def addUnexpectedSuccess(self, test):
        self.stream.writeln(red("unexpected success"))

class ImprovedVerboseWriter(StandardVerboseWriter):
    def __init__(
        self, stream, descriptions, traceback_highlight=False, fast_info=False,
    ):
        super(ImprovedVerboseWriter, self).__init__(
            stream,
            descriptions,
            traceback_highlight,
            fast_info
        )
        self.last_test = None

    def __is_new_module(self, test):
        return (
            not self.last_test
            or
            test.__class__.__module__ != self.last_test.__class__.__module__
        )

    def __is_new_class(self, test):
        return (
            self.__is_new_module(test)
            or
            test.__class__.__name__ != self.last_test.__class__.__name__
        )

    def __format_module(self, test):
        if not self.__is_new_module(test):
            return lightgrey(test.__class__.__module__)
        return format_module(test)

    def __format_class(self, test):
        if not self.__is_new_class(test):
            return lightgrey(test.__class__.__name__)
        return test.__class__.__name__

    def startTest(self, test):
        self.stream.write(
            self.__format_module(test) + lightgrey(".")
            + self.__format_class(test) + lightgrey(".")
            + format_test_method_name(test) + lightgrey(" : ")
        )
        self.stream.flush()
        self.last_test = test

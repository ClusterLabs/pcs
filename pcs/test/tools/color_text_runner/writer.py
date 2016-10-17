from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.color_text_runner.format import (
    blue,
    red,
    green,
    lightgrey,
    get_description,
    format_module,
    format_test_method_name,
)


class Writer(object):
    def __init__(self, stream, descriptions):
        self.stream = stream
        self.descriptions = descriptions

    def addSuccess(self, test):
        pass

    def addError(self, test, err):
        pass

    def addFailure(self, test, err):
        pass

    def addSkip(self, test, reason):
        pass

    def startTest(self, test):
        pass

    def addExpectedFailure(self, test, err):
        pass

    def addUnexpectedSuccess(self, test):
        pass

class DotWriter(Writer):
    def addSuccess(self, test):
        self.stream.write(green("."))
        self.stream.flush()

    def addError(self, test, err):
        self.stream.write(red('E'))
        self.stream.flush()

    def addFailure(self, test, err):
        self.stream.write(red('F'))
        self.stream.flush()

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

    def addError(self, test, err):
        self.stream.writeln(red("ERROR"))

    def addFailure(self, test, err):
        self.stream.writeln(red("FAIL"))

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
    def __init__(self, stream, descriptions):
        super(ImprovedVerboseWriter, self).__init__(stream, descriptions)
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

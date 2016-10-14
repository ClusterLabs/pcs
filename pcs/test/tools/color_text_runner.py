from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools import pcs_unittest as unittest


palete = {
    "black": '\033[30m',
    "red": '\033[31m',
    "green": '\033[32m',
    "orange": '\033[33m',
    "blue": '\033[34m',
    "purple": '\033[35m',
    "cyan": '\033[36m',
    "lightgrey": '\033[37m',
    "darkgrey": '\033[90m',
    "lightred": '\033[91m',
    "lightgreen": '\033[92m',
    "yellow": '\033[93m',
    "lightblue": '\033[94m',
    "pink": '\033[95m',
    "lightcyan": '\033[96m',
    "end" : '\033[0m',
    "bold" : '\033[1m',
    "underline" : '\033[4m',
}

#apply is builtin but is deprecated since 2.3 => no problem to redefine it here
def apply(key_list, text):
    return("".join([palete[key] for key in key_list]) + text + palete["end"])

TextTestResult = unittest.TextTestResult
#pylint: disable=bad-super-call
class ColorTextTestResult(TextTestResult):
    def addSuccess(self, test):
        super(TextTestResult, self).addSuccess(test)
        if self.showAll:
            self.stream.writeln(apply(["green", "bold"], "OK"))
        elif self.dots:
            self.stream.write(apply(["green", "bold"], "."))
            self.stream.flush()

    def addError(self, test, err):
        super(TextTestResult, self).addError(test, err)
        if self.showAll:
            self.stream.writeln(apply(["red", "bold"], "ERROR"))
        elif self.dots:
            self.stream.write(apply(["red", "bold"], 'E'))
            self.stream.flush()

    def addFailure(self, test, err):
        super(TextTestResult, self).addFailure(test, err)
        if self.showAll:
            self.stream.writeln(apply(["lightred", "bold"], "FAIL"))
        elif self.dots:
            self.stream.write(apply(["lightred", "bold"], 'F'))
            self.stream.flush()

    def addSkip(self, test, reason):
        super(TextTestResult, self).addSkip(test, reason)
        if self.showAll:
            self.stream.writeln(
                apply(["blue", "bold"], "skipped {0!r}".format(reason))
            )
        elif self.dots:
            self.stream.write(apply(["blue", "bold"], 's'))
            self.stream.flush()

    def getDescription(self, test):
        doc_first_line = test.shortDescription()
        if self.descriptions and doc_first_line:
            return '\n'.join((str(test), doc_first_line))
        else:
            module_parts = test.__class__.__module__.split(".")
            module = module_parts[-1]
            package = ".".join(module_parts[:-1])+"." if module_parts else ""

            return (
                test._testMethodName
                +" "
                +apply(["lightgrey"], "(")
                +apply(["lightgrey"], package)
                +apply(["bold"], module)
                +"."
                +test.__class__.__name__
                +apply(["lightgrey"], ")")
            )

    def __format_test_name(self, test):
        return (
            test.__class__.__module__
            + "." + test.__class__.__name__
            + "." + test._testMethodName
        )

    def printErrors(self):
        super(ColorTextTestResult, self).printErrors()
        if not self.errors and not self.failures:
            return

        self.stream.writeln()
        self.stream.writeln(self.separator1)
        self.stream.writeln()
        self.stream.writeln(
            "for running failed tests only (errors are first then failures):"
        )
        self.stream.writeln()
        self.stream.write(" \\\n".join(
            [
                self.__format_test_name(test)
                for test, _ in self.errors + self.failures
            ]
        ))
        self.stream.writeln()

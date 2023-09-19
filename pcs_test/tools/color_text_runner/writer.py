import datetime


class Writer:
    # pylint: disable=invalid-name
    def __init__(
        self,
        stream,
        format_,
        descriptions,
        traceback_highlight=False,
        fast_info=False,
    ):
        self.stream = stream
        self.format = format_
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
                self.format.traceback(traceback)
                if self.traceback_highlight
                else traceback
            )


class DotWriter(Writer):
    def addSuccess(self, test):
        self.stream.write(self.format.green("."))
        self.stream.flush()

    def addError(self, test, err, traceback):
        self.stream.write(self.format.red("E"))
        self.stream.flush()
        self.show_fast_info(traceback)

    def addFailure(self, test, err, traceback):
        self.stream.write(self.format.red("F"))
        self.stream.flush()
        self.show_fast_info(traceback)

    def addSkip(self, test, reason):
        self.stream.write(self.format.blue("s"))
        self.stream.flush()

    def addExpectedFailure(self, test, err):
        self.stream.write(self.format.blue("x"))
        self.stream.flush()

    def addUnexpectedSuccess(self, test):
        self.stream.write(self.format.red("u"))
        self.stream.flush()


class StandardVerboseWriter(Writer):
    def addSuccess(self, test):
        self.stream.writeln(self.format.green("OK"))
        self.stream.flush()

    def addError(self, test, err, traceback):
        self.stream.writeln(self.format.red("ERROR"))
        self.stream.flush()
        self.show_fast_info(traceback)

    def addFailure(self, test, err, traceback):
        self.stream.writeln(self.format.red("FAIL"))
        self.stream.flush()
        self.show_fast_info(traceback)

    def addSkip(self, test, reason):
        self.stream.writeln(self.format.blue("skipped {0!r}".format(reason)))
        self.stream.flush()

    def startTest(self, test):
        self.stream.write(self.format.description(test, self.descriptions))
        self.stream.write(" ... ")
        self.stream.flush()

    def addExpectedFailure(self, test, err):
        self.stream.writeln(self.format.blue("expected failure"))
        self.stream.flush()

    def addUnexpectedSuccess(self, test):
        self.stream.writeln(self.format.red("unexpected success"))
        self.stream.flush()


class TimeWriter(StandardVerboseWriter):
    def __init__(
        self,
        stream,
        format_,
        descriptions,
        traceback_highlight=False,
        fast_info=False,
    ):
        super().__init__(
            stream,
            format_,
            descriptions,
            traceback_highlight=traceback_highlight,
            fast_info=fast_info,
        )
        self._start_time_map = {}

    def _print_time(self, test):
        end = datetime.datetime.now()
        testname = self.format.test_name(test)
        delta = (end - self._start_time_map[testname]).total_seconds()
        self.stream.writeln(f"{delta:11.6f}s needed to run {testname}")

    def addSuccess(self, test):
        super().addSuccess(test)
        self._print_time(test)

    def addError(self, test, err, traceback):
        super().addError(test, err, traceback)
        self._print_time(test)

    def addFailure(self, test, err, traceback):
        super().addFailure(test, err, traceback)
        self._print_time(test)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._print_time(test)

    def startTest(self, test):
        super().startTest(test)
        self._start_time_map[
            self.format.test_name(test)
        ] = datetime.datetime.now()

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._print_time(test)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._print_time(test)


class ImprovedVerboseWriter(StandardVerboseWriter):
    def __init__(
        self,
        stream,
        format_,
        descriptions,
        traceback_highlight=False,
        fast_info=False,
    ):
        super().__init__(
            stream, format_, descriptions, traceback_highlight, fast_info
        )
        self.last_test = None

    def __is_new_module(self, test):
        return (
            not self.last_test
            or test.__class__.__module__ != self.last_test.__class__.__module__
        )

    def __is_new_class(self, test):
        return (
            self.__is_new_module(test)
            or test.__class__.__name__ != self.last_test.__class__.__name__
        )

    def __format_module(self, test):
        if not self.__is_new_module(test):
            return self.format.lightgrey(test.__class__.__module__)
        return self.format.module(test)

    def __format_class(self, test):
        if not self.__is_new_class(test):
            return self.format.lightgrey(test.__class__.__name__)
        return test.__class__.__name__

    def startTest(self, test):
        self.stream.write(self.__format_module(test))
        self.stream.write(self.format.lightgrey("."))
        self.stream.write(self.__format_class(test))
        self.stream.write(self.format.lightgrey("."))
        self.stream.write(self.format.test_method_name(test))
        self.stream.write(self.format.lightgrey(" : "))
        self.last_test = test

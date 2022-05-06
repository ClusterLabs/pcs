import re

separator1 = "=" * 70
separator2 = "-" * 70


class Output:
    palete = {
        "black": "\033[30m",
        "red": "\033[31m",
        "green": "\033[32m",
        "orange": "\033[33m",
        "blue": "\033[34m",
        "purple": "\033[35m",
        "cyan": "\033[36m",
        "lightgrey": "\033[37m",
        "darkgrey": "\033[90m",
        "lightred": "\033[91m",
        "lightgreen": "\033[92m",
        "yellow": "\033[93m",
        "lightblue": "\033[94m",
        "pink": "\033[95m",
        "lightcyan": "\033[96m",
        "end": "\033[0m",
        "bold": "\033[1m",
        "underline": "\033[4m",
    }

    def __init__(self, rich):
        self._rich = rich

    def _apply(self, key_list, text):
        if not self._rich:
            return text
        return (
            "".join([self.palete[key] for key in key_list])
            + text
            + self.palete["end"]
        )

    def lightgrey(self, text):
        return self._apply(["lightgrey"], text)

    def bold(self, text):
        return self._apply(["bold"], text)

    def blue(self, text):
        return self._apply(["blue", "bold"], text)

    def red(self, text):
        return self._apply(["red", "bold"], text)

    def green(self, text):
        return self._apply(["green", "bold"], text)


class Format:
    def __init__(self, output):
        self._output = output

    def __getattr__(self, name):
        return getattr(self._output, name)

    def module_name(self, name):
        prefix = ""
        part_list = name.split("_")

        if part_list[0].startswith("test"):
            prefix = "test"
            part_list[0] = part_list[0][len("test") :]

        return prefix + "_".join(
            [self._output.bold(part) for part in part_list]
        )

    def module(self, test):
        parts = test.__class__.__module__.split(".")
        return self._output.lightgrey(".").join(
            parts[:-1] + [self.module_name(parts[-1])]
        )

    def test_method_name(self, test):
        if not hasattr(test, "_testMethodName"):
            return test.id()

        # pylint: disable=protected-access
        parts = test._testMethodName.split("_")
        if parts[0].startswith("test"):
            parts[0] = self._output.lightgrey("test") + parts[0][len("test") :]
        return self._output.lightgrey("_").join(parts)

    def error_overview(self, errors, failures, slash_last):
        return (
            [
                self._output.red(
                    "for running failed tests only (errors are first then "
                    "failures):"
                ),
                "",
            ]
            + [
                self._output.lightgrey(err)
                for err in slash_errors(
                    [self.test_name(test) for test, _ in errors + failures],
                    slash_last,
                )
            ]
            + [""]
        )

    def test_name(self, test):
        if (
            test.__class__.__module__ == "subunit"
            and test.__class__.__name__ == "RemotedTestCase"
        ):
            return self.test_method_name(test)
        return (
            self.module(test)
            + "."
            + test.__class__.__name__
            + "."
            + self.test_method_name(test)
        )

    def description(self, test, descriptions):
        doc_first_line = test.shortDescription()
        if descriptions and doc_first_line:
            return "\n".join((str(test), doc_first_line))
        module_parts = test.__class__.__module__.split(".")
        module = module_parts[-1]
        package = ".".join(module_parts[:-1]) + "." if module_parts else ""

        return (
            # pylint: disable=protected-access
            test._testMethodName
            + " "
            + self._output.lightgrey("(")
            + self._output.lightgrey(package)
            + self._output.bold(module)
            + "."
            + test.__class__.__name__
            + self._output.lightgrey(")")
        )

    def error_list(self, flavour, errors, descriptions, traceback_highlight):
        line_list = []
        for test, err in errors:
            line_list.extend(
                [
                    self._output.lightgrey(separator1),
                    "%s: %s"
                    % (
                        self._output.red(flavour),
                        self.description(test, descriptions),
                    ),
                    self._output.lightgrey(separator2),
                    "%s" % self.traceback(err) if traceback_highlight else err,
                ]
            )
        return line_list

    def traceback(self, err):
        formated_err = []
        path_regex = re.compile(
            r'^  File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<name>.*)$'
        )
        was_prev_path = False
        for line in err.splitlines():
            if line == "Traceback (most recent call last):":
                formated_err.append(self._output.lightgrey(line))
                was_prev_path = False
                continue

            match = path_regex.match(line)
            if match:
                path = match.group("path").split("/")
                formated_err.append(
                    self._output.lightgrey('  File "')
                    + self._output.lightgrey("/").join(
                        path[:-1] + [self._output.bold(path[-1])]
                    )
                    + self._output.lightgrey('", line ')
                    + self._output.bold(match.group("line"))
                    + self._output.lightgrey(", in ")
                    + self._output.bold(match.group("name"))
                )
                was_prev_path = True
            elif was_prev_path:
                formated_err.append(self._output.bold(line))
                was_prev_path = False
            else:
                formated_err.append(line)
                was_prev_path = False
        return "\n".join(formated_err) + "\n"

    def skips(self, skip_map):
        return (
            [self._output.blue("Some tests have been skipped:")]
            + [
                self._output.lightgrey(
                    "{0} ({1}x)".format(reason, len(test_list))
                )
                for reason, test_list in skip_map.items()
            ]
            + [""]
        )


def slash_errors(error_list, slash_last=True):
    if not slash_last:
        return slash_errors(error_list[:-1]) + [error_list[-1]]
    return ["{0} \\".format(err) for err in error_list]

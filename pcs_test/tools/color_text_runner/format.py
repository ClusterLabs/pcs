import re
import unittest

separator1 = "=" * 70
separator2 = "-" * 70


class Output:
    palette = {
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
            "".join([self.palette[key] for key in key_list])
            + text
            + self.palette["end"]
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
        error_names = sorted({self.test_name(test) for test, _ in errors})
        failure_names = sorted({self.test_name(test) for test, _ in failures})

        overview = []
        overview.append(
            self._output.red(
                "for running failed tests only (errors are first then "
                "failures):"
            )
        )
        overview.append("")
        overview.extend(
            self._output.lightgrey(err)
            for err in slash_errors(
                error_names + failure_names,
                slash_last,
            )
        )
        overview.append("")

        return overview

    def test_name(self, test):
        # pylint: disable=protected-access
        if isinstance(test, unittest.case._SubTest):
            test = test.test_case
        return "{module_name}.{class_name}.{method_name}".format(
            module_name=self.module(test),
            class_name=test.__class__.__name__,
            method_name=self.test_method_name(test),
        )

    def description(self, test, descriptions):
        subtest_desc = None
        # pylint: disable=protected-access
        if isinstance(test, unittest.case._SubTest):
            subtest_desc = test._subDescription()
            test = test.test_case
        module_parts = test.__class__.__module__.split(".")
        module = module_parts[-1]
        package = ".".join(module_parts[:-1]) + "." if module_parts else ""

        desc = (
            "{method_name} ({package_name}{module_name}.{class_name})".format(
                method_name=test._testMethodName,
                package_name=self._output.lightgrey(package),
                module_name=self._output.bold(module),
                class_name=test.__class__.__name__,
            )
        )

        if subtest_desc:
            desc = f"{desc} {subtest_desc}"

        doc_first_line = test.shortDescription()
        if descriptions and doc_first_line:
            return f"{desc}\n{doc_first_line}"
        return desc

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
        formatted_err = []
        path_regex = re.compile(
            r'^  File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<name>.*)$'
        )
        was_prev_path = False
        for line in err.splitlines():
            if line == "Traceback (most recent call last):":
                formatted_err.append(self._output.lightgrey(line))
                was_prev_path = False
                continue

            match = path_regex.match(line)
            if match:
                path = match.group("path").split("/")
                formatted_err.append(
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
                formatted_err.append(self._output.bold(line))
                was_prev_path = False
            else:
                formatted_err.append(line)
                was_prev_path = False
        return "\n".join(formatted_err) + "\n"

    def skip_overview(self, skip_map):
        return (
            [self._output.blue("Some tests have been skipped:")]
            + [
                "{0} ({1}x)".format(reason, len(test_list))
                for reason, test_list in skip_map.items()
            ]
            + [""]
        )


def slash_errors(error_list, slash_last=True):
    if not slash_last:
        return slash_errors(error_list[:-1]) + [error_list[-1]]
    return ["{0} \\".format(err) for err in error_list]

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re
from functools import partial


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

separator1 = '=' * 70
separator2 = '-' * 70

#apply is builtin but is deprecated since 2.3 => no problem to redefine it here
def apply(key_list, text):
    return("".join([palete[key] for key in key_list]) + text + palete["end"])

lightgrey = partial(apply, ["lightgrey"])
bold = partial(apply, ["bold"])
blue = partial(apply, ["blue", "bold"])
red = partial(apply, ["red", "bold"])
green = partial(apply, ["green", "bold"])

def format_module_name(name):
    prefix = ""
    part_list = name.split("_")

    if part_list[0].startswith("test"):
        prefix = "test"
        part_list[0] = part_list[0][len("test"):]

    return prefix + "_".join([bold(part) for part in part_list])

def format_module(test):
    parts = test.__class__.__module__.split(".")
    return lightgrey(".").join(parts[:-1] + [format_module_name(parts[-1])])

def format_test_method_name(test):
    parts = test._testMethodName.split("_")

    if parts[0].startswith("test"):
        parts[0] = lightgrey("test") + parts[0][len("test"):]

    return lightgrey("_").join(parts)

def format_error_overview(errors, failures, slash_last):
    return [
        red("for running failed tests only (errors are first then failures):"),
        "",
    ] + [
        lightgrey(err) for err in slash_errors(
            [format_test_name(test) for test, _ in errors + failures],
            slash_last
        )
    ] + [""]

def slash_errors(error_list, slash_last=True):
    if not slash_last:
        return slash_errors(error_list[:-1]) + [error_list[-1]]
    return ["{0} \\".format(err) for err in error_list]

def format_test_name(test):
    return (
        format_module(test)
        + "." + test.__class__.__name__
        + "." + format_test_method_name(test)
    )

def get_description(test, descriptions):
    doc_first_line = test.shortDescription()
    if descriptions and doc_first_line:
        return '\n'.join((str(test), doc_first_line))
    else:
        module_parts = test.__class__.__module__.split(".")
        module = module_parts[-1]
        package = ".".join(module_parts[:-1])+"." if module_parts else ""

        return (
            test._testMethodName
            +" "
            +lightgrey("(")
            +lightgrey(package)
            +bold(module)
            +"."
            +test.__class__.__name__
            +lightgrey(")")
        )

def format_error_list(flavour, errors, descriptions, traceback_highlight):
    line_list = []
    for test, err in errors:
        line_list.extend([
            lightgrey(separator1),
            "%s: %s" % (red(flavour), get_description(test, descriptions)),
            lightgrey(separator2),
            "%s" % format_traceback(err) if traceback_highlight else err,
            "",
        ])
    return line_list

def format_traceback(err):
    formated_err = []
    path_regex = re.compile(
        '^  File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<name>.*)$'
    )
    was_prev_path = False
    for line in err.splitlines():
        if line == "Traceback (most recent call last):":
            formated_err.append(lightgrey(line))
            was_prev_path = False
            continue

        match = path_regex.match(line)
        if match:
            path = match.group("path").split("/")
            formated_err.append(
                lightgrey('  File "')
                + lightgrey("/").join(path[:-1] + [bold(path[-1])])
                + lightgrey('", line ') + bold(match.group("line"))
                + lightgrey(', in ') + bold(match.group("name"))
            )
            was_prev_path = True
        elif was_prev_path:
            formated_err.append(bold(line))
            was_prev_path = False
        else:
            formated_err.append(line)
            was_prev_path = False
    return "\n".join(formated_err)

def format_skips(skip_map):
    return [blue("Some tests have been skipped:")] + [
        lightgrey("{0} ({1}x)".format(reason, len(test_list)))
        for reason, test_list in skip_map.items()
    ] + [""]

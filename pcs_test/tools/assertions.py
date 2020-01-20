import difflib
import doctest
import re
from lxml.doctestcompare import LXMLOutputChecker
from lxml.etree import LXML_VERSION

from pcs.common.reports import ReportItemSeverity
from pcs.lib.errors import LibraryError

# pylint: disable=invalid-name, no-self-use

# cover python2 vs. python3 differences
_re_object_type = type(re.compile(""))

def prepare_diff(first, second):
    """
    Return a string containing a diff of first and second
    """
    return "".join(
        difflib.Differ().compare(first.splitlines(1), second.splitlines(1))
    )

def ac(a, b):
    """
    Compare the actual output 'a' and an expected output 'b', print diff b a
    """
    if a != b:
        raise AssertionError(
            "strings not equal:\n{0}".format(prepare_diff(b, a))
        )

def start_tag_error_text():
    """lxml 3.7+ gives a longer 'start tag expected' error message,
    handle it here so multiple tests can just get the appropriate
    string from this function.
    """
    msg = "Start tag expected, '<' not found, line 1, column 1"
    if LXML_VERSION >= (3, 7, 0, 0):
        msg += " (<string>, line 1)"
    return msg

def console_report(*lines):
    #after lines append last new line
    return "\n".join(lines + ("",))

class AssertPcsMixin:
    """Run pcs command and assert its result"""

    def assert_pcs_success_all(self, command_list):
        for command in command_list:
            stdout, pcs_returncode = self.pcs_runner.run(command)
            if pcs_returncode != 0:
                raise AssertionError(
                    (
                        "Command '{0}' does not succeed.\n"
                        "return_code: {1}\n"
                        "stdout:\n{2}"
                    ).format(command, pcs_returncode, stdout)
                )

    def assert_pcs_success(
        self, command, stdout_full=None, stdout_start=None, stdout_regexp=None,
        despace=False
    ):
        full = stdout_full
        if (
            stdout_start is None
            and
            stdout_full is None
            and
            stdout_regexp is None
        ):
            full = ""
        self.assert_pcs_result(
            command,
            stdout_full=full,
            stdout_start=stdout_start,
            stdout_regexp=stdout_regexp,
            returncode=0,
            despace=despace,
        )

    def assert_pcs_fail(
        self, command, stdout_full=None, stdout_start=None, stdout_regexp=None
    ):
        self.assert_pcs_result(
            command,
            stdout_full=stdout_full,
            stdout_start=stdout_start,
            stdout_regexp=stdout_regexp,
            returncode=1
        )

    def assert_pcs_fail_regardless_of_force(
        self, command, stdout_full=None, stdout_start=None, stdout_regexp=None
    ):
        self.assert_pcs_fail(command, stdout_full, stdout_start, stdout_regexp)
        self.assert_pcs_fail(
            command + " --force", stdout_full, stdout_start, stdout_regexp
        )

    def assert_pcs_result(
        self, command, stdout_full=None, stdout_start=None, stdout_regexp=None,
        returncode=0, despace=False
    ):
        msg = (
            "Please specify exactly one: stdout_start or stdout_full or"
            " stdout_regexp"
        )
        specified_stdout = [
            stdout
            for stdout in (stdout_full, stdout_start, stdout_regexp)
            if stdout is not None
        ]
        if not specified_stdout:
            raise Exception(msg + ", none specified")
        if len(specified_stdout) > 1:
            raise Exception(msg + ", both specified")

        stdout, pcs_returncode = self.pcs_runner.run(command)
        self.assertEqual(
            returncode,
            pcs_returncode,
            (
                'Expected return code "{0}", but was "{1}"'
                + '\ncommand: {2}\nstdout:\n{3}'
            ).format(returncode, pcs_returncode, command, stdout)
        )
        message_template = (
            "{reason}\ncommand: {cmd}\ndiff is (expected is 2nd):\n{diff}"
            +
            "\nFull stdout:\n{stdout}"
        )
        if stdout_start:
            expected_start = self.__prepare_output(stdout_start)
            if not stdout.startswith(expected_start):
                self.fail(
                    message_template.format(
                        reason="Stdout does not start as expected",
                        cmd=command,
                        diff=prepare_diff(
                            stdout[:len(expected_start)], expected_start
                        ),
                        stdout=stdout
                    )
                )
        elif stdout_regexp:
            if not isinstance(stdout_regexp, _re_object_type):
                stdout_regexp = re.compile(stdout_regexp)
            if not stdout_regexp.search(stdout):
                self.fail(
                    (
                        "Stdout does not match the expected regexp\n"
                        "command: {cmd}\nregexp:\n{regexp} (flags: {flags})\n"
                        "\nFull stdout:\n{stdout}"
                    ).format(
                        cmd=command,
                        regexp=stdout_regexp.pattern,
                        flags=", ".join(
                            self.__prepare_regexp_flags(stdout_regexp.flags)
                        ),
                        stdout=stdout,
                    )
                )
        else:
            expected_full = self.__prepare_output(stdout_full)
            if (
                (despace and _despace(stdout) != _despace(expected_full))
                or
                (not despace and stdout != expected_full)
            ):
                self.assertEqual(
                    stdout,
                    expected_full,
                    message_template.format(
                        reason="Stdout is not as expected",
                        cmd=command,
                        diff=prepare_diff(stdout, expected_full),
                        stdout=stdout
                    )
                )

    def __prepare_output(self, output):
        if isinstance(output, list):
            return console_report(*output)
        return output

    def __prepare_regexp_flags(self, flags):
        # python2 has different flags than python3
        possible_flags = [
            "ASCII",
            "DEBUG",
            "IGNORECASE",
            "LOCALE",
            "MULTILINE",
            "DOTALL",
            "UNICODE",
            "VERBOSE",
        ]
        used_flags = [
            f for f in possible_flags
            if hasattr(re, f) and (flags & getattr(re, f))
        ]
        return sorted(used_flags)


class ExtendedAssertionsMixin:
    def assert_raises(
        self, expected_exception, callable_obj, property_dict=None
    ):
        if property_dict is None:
            property_dict = {}
        try:
            callable_obj()
            raise AssertionError(
                "No exception raised. Expected exception: {exception}".format(
                    exception=expected_exception.__class__.__name__
                )
            )
        except expected_exception as e:
            for prop, value in property_dict.items():
                try:
                    self.assertEqual(value, getattr(e, prop))
                except AttributeError:
                    raise AssertionError(
                        "Property {property} doesn't exist in exception"
                        " {exception}".format(
                            property=prop,
                            exception=e.__class__.__name__
                        )
                    )


def assert_xml_equal(expected_xml, got_xml, context_explanation=""):
    checker = LXMLOutputChecker()
    if not checker.check_output(expected_xml, got_xml, 0):
        raise AssertionError(
            "{context_explanation}{xml_diff}".format(
                context_explanation=(
                    "" if not context_explanation
                    else "\n{0}\n".format(context_explanation)
                ),
                xml_diff=checker.output_difference(
                    doctest.Example("", expected_xml),
                    got_xml,
                    0
                )
            )
        )

SEVERITY_SHORTCUTS = {
    ReportItemSeverity.INFO: "I",
    ReportItemSeverity.WARNING: "W",
    ReportItemSeverity.ERROR: "E",
    ReportItemSeverity.DEBUG: "D",
}

def _format_report_item_info(info):
    return ", ".join([
        "{0}:{1}".format(key, repr(value)) for key, value in info.items()
    ])

def _expected_report_item_format(report_item_expectation):
    return "{0} {1} {{{2}}} ! {3}".format(
        SEVERITY_SHORTCUTS.get(
            report_item_expectation[0], report_item_expectation[0]
        ),
        report_item_expectation[1],
        _format_report_item_info(report_item_expectation[2]),
        report_item_expectation[3] if len(report_item_expectation) > 3 else None
    )

def _format_report_item(report_item):
    return _expected_report_item_format((
        report_item.severity,
        report_item.code,
        report_item.info,
        report_item.forceable
    ))

def assert_report_item_equal(real_report_item, report_item_info):
    if not __report_item_equal(real_report_item, report_item_info):
        raise AssertionError(
            "ReportItem not equal\nexpected: {0}\nactual:   {1}"
            .format(
                repr((
                    report_item_info[0],
                    report_item_info[1],
                    report_item_info[2],
                    None if len(report_item_info) < 4 else report_item_info[3]
                )),
                _format_report_item(real_report_item)
            )
        )

def _unexpected_report_given(
    remaining_expected_report_info_list,
    expected_report_info_list, real_report_item, real_report_item_list
):
    return AssertionError(
        (
            "\n  Unexpected real report given:"
            "\n  =============================\n    {0}\n"
            "\n  remaining expected reports ({1}) are:"
            "\n  ------------------------------------\n    {2}\n"
            "\n  all expected reports ({3}) are:"
            "\n  ------------------------------\n    {4}\n"
            "\n  all real reports ({5}):"
            "\n  ---------------------\n    {6}"
        )
        .format(
            _format_report_item(real_report_item),
            len(remaining_expected_report_info_list),
            "\n    ".join(map(
                _expected_report_item_format,
                remaining_expected_report_info_list,
            )) if remaining_expected_report_info_list
            else "No other report is expected!",
            len(expected_report_info_list),
            "\n    ".join(map(
                _expected_report_item_format,
                expected_report_info_list,
            )) if expected_report_info_list else "No report is expected!",
            len(real_report_item_list),
            "\n    ".join(map(_format_report_item, real_report_item_list)),
        )
    )

def assert_report_item_list_equal(
    real_report_item_list, expected_report_info_list, hint=""
):
    remaining_expected_report_info_list = expected_report_info_list[:]
    duplicate_report_item_is_missing = False
    for real_report_item in real_report_item_list:
        found_report_info = __find_report_info(
            expected_report_info_list,
            real_report_item
        )
        if found_report_info is None:
            raise _unexpected_report_given(
                remaining_expected_report_info_list,
                expected_report_info_list,
                real_report_item,
                real_report_item_list,
            )
        if found_report_info in remaining_expected_report_info_list:
            remaining_expected_report_info_list.remove(found_report_info)
        else:
            duplicate_report_item_is_missing = True
    if remaining_expected_report_info_list or duplicate_report_item_is_missing:
        def format_items(item_type, item_list):
            caption = "{0} ReportItems({1})".format(item_type, len(item_list))
            return "{0}\n{1}\n{2}".format(
                caption,
                "-"*len(caption),
                "\n".join(map(repr, item_list))
            )

        raise AssertionError(
            "\nExpected LibraryError is missing\n{0}\n\n{1}\n\n{2}".format(
                "{0}\n".format(hint) if hint else "",
                format_items("expected", expected_report_info_list),
                format_items("real", real_report_item_list),
            )
        )

def assert_raise_library_error(callableObj, *report_info_list):
    try:
        callableObj()
        raise AssertionError("LibraryError not raised")
    except LibraryError as e:
        assert_report_item_list_equal(e.args, list(report_info_list))

def __find_report_info(expected_report_info_list, real_report_item):
    for report_info in expected_report_info_list:
        if __report_item_equal(real_report_item, report_info):
            return report_info
    return None

def __report_item_equal(real_report_item, report_item_info):
    return (
        real_report_item.severity == report_item_info[0]
        and
        real_report_item.code == report_item_info[1]
        and
        #checks only presence and match of expected in info,
        #extra info is ignored
        all(
            (k in real_report_item.info and real_report_item.info[k] == v)
            for k, v in report_item_info[2].items()
        )
        and
        (
            real_report_item.forceable == (
                None if len(report_item_info) < 4 else report_item_info[3]
            )
        )
    )

def assert_pcs_status(status1, status2):
    if _despace(status1) != _despace(status2):
        raise AssertionError(
            "strings not equal:\n{0}".format(prepare_diff(status1, status2))
        )

def _despace(string):
    # ignore whitespace changes between various pacemaker versions
    return re.sub(r"[ \t]+", " ", string)

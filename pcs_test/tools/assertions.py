import difflib
import doctest
import re

from lxml.doctestcompare import LXMLOutputChecker
from lxml.etree import LXML_VERSION

from pcs.common import reports
from pcs.lib.errors import LibraryError

from pcs_test.tools.fixture import ReportItemFixture


def prepare_diff(first, second):
    """
    Return a string containing a diff of first and second
    """
    return "".join(
        difflib.Differ().compare(first.splitlines(1), second.splitlines(1))
    )


def ac(a, b):
    # pylint: disable=invalid-name
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


class AssertPcsMixin:
    """Run pcs command and assert its result"""

    def assert_pcs_success_all(self, command_list):
        for command in command_list:
            stdout, stderr, retval = self.pcs_runner.run(command)
            if retval != 0:
                raise AssertionError(
                    f"Command '{command}' did not succeed\n"
                    f"** return code: {retval}\n"
                    f"** stdout:\n{stdout}\n"
                    f"** stderr:\n{stderr}\n"
                )

    def assert_pcs_success(
        self,
        command,
        stdout_full=None,
        stdout_start=None,
        stdout_regexp=None,
        stderr_full=None,
        stderr_start=None,
        stderr_regexp=None,
        despace=False,
    ):
        # pylint: disable=too-many-arguments
        # It is common that successful commands don't print anything, so we
        # default stdout and stderr to an empty string if not specified
        # otherwise.
        self.assert_pcs_result(
            command,
            stdout_full=self.__default_output_to_empty_str(
                stdout_full, stdout_start, stdout_regexp
            ),
            stdout_start=stdout_start,
            stdout_regexp=stdout_regexp,
            stderr_full=self.__default_output_to_empty_str(
                stderr_full, stderr_start, stderr_regexp
            ),
            stderr_start=stderr_start,
            stderr_regexp=stderr_regexp,
            returncode=0,
            despace=despace,
        )

    def assert_pcs_fail(
        self,
        command,
        stderr_full=None,
        stderr_start=None,
        stderr_regexp=None,
        stdout_full=None,
        stdout_start=None,
        stdout_regexp=None,
    ):
        # It is common that failed commands don't print anything to stdout, so
        # we default stdout to an empty string if not specified otherwise.
        self.assert_pcs_result(
            command,
            stdout_full=self.__default_output_to_empty_str(
                stdout_full, stdout_start, stdout_regexp
            ),
            stdout_start=stdout_start,
            stdout_regexp=stdout_regexp,
            stderr_full=stderr_full,
            stderr_start=stderr_start,
            stderr_regexp=stderr_regexp,
            returncode=1,
        )

    def assert_pcs_fail_regardless_of_force(
        self,
        command,
        stderr_full=None,
        stderr_start=None,
        stderr_regexp=None,
        stdout_full=None,
        stdout_start=None,
        stdout_regexp=None,
    ):
        self.assert_pcs_fail(
            command,
            stdout_full=stdout_full,
            stdout_start=stdout_start,
            stdout_regexp=stdout_regexp,
            stderr_full=stderr_full,
            stderr_start=stderr_start,
            stderr_regexp=stderr_regexp,
        )
        self.assert_pcs_fail(
            command + ["--force"],
            stdout_full=stdout_full,
            stdout_start=stdout_start,
            stdout_regexp=stdout_regexp,
            stderr_full=stderr_full,
            stderr_start=stderr_start,
            stderr_regexp=stderr_regexp,
        )

    def assert_pcs_result(
        self,
        command,
        stdout_full=None,
        stdout_start=None,
        stdout_regexp=None,
        stderr_full=None,
        stderr_start=None,
        stderr_regexp=None,
        returncode=0,
        despace=False,
    ):
        # pylint: disable=too-many-arguments
        self.__check_output_specified(
            stdout_full, stdout_start, stdout_regexp, "stdout"
        )
        self.__check_output_specified(
            stderr_full, stderr_start, stderr_regexp, "stderr"
        )

        stdout_actual, stderr_actual = self.assert_pcs_success_ignore_output(
            command, returncode
        )

        message_template = (
            f"{{reason}}\n** Command: {command}\n** {{detail}}\n"
            f"** Retval: {returncode}\n"
            f"** Full stdout:\n{stdout_actual}\n"
            f"** Full stderr:\n{stderr_actual}\n"
        )
        self.__fail_on_unexpected_output(
            stdout_actual,
            stdout_full,
            stdout_start,
            stdout_regexp,
            despace,
            "stdout",
            message_template,
        )

        self.__fail_on_unexpected_output(
            stderr_actual,
            stderr_full,
            stderr_start,
            stderr_regexp,
            despace,
            "stderr",
            message_template,
        )

    def assert_pcs_success_ignore_output(self, command, returncode=0):
        stdout, stderr, retval_actual = self.pcs_runner.run(command)

        self.assertEqual(
            returncode,
            retval_actual,
            (
                f"Expected return code '{returncode}' but was '{retval_actual}'\n"
                f"** command: {command}\n"
                f"** stdout:\n{stdout}\n"
                f"** stderr:\n{stderr}\n"
            ),
        )
        return stdout, stderr

    @staticmethod
    def __default_output_to_empty_str(output_full, output_start, output_regexp):
        if (
            output_start is None
            and output_full is None
            and output_regexp is None
        ):
            return ""
        return output_full

    @staticmethod
    def __check_output_specified(
        output_full, output_start, output_regexp, label
    ):
        msg = (
            f"Please specify exactly one: {label}_full or {label}_start or "
            f"{label}_regexp"
        )
        specified_output = [
            output
            for output in (output_full, output_start, output_regexp)
            if output is not None
        ]
        if not specified_output:
            raise TypeError(msg + ", none specified")
        if len(specified_output) > 1:
            raise TypeError(msg + ", more than one specified")

    def __fail_on_unexpected_output(
        self,
        output_actual,
        output_full,
        output_start,
        output_regexp,
        despace,
        label,
        message_template,
    ):
        if output_start:
            expected_start = self.__prepare_output(output_start)
            if not output_actual.startswith(expected_start):
                diff = prepare_diff(
                    output_actual[: len(expected_start)], expected_start
                )
                raise AssertionError(
                    message_template.format(
                        reason=f"{label} does not start as expected",
                        detail=f"diff is (expected is 2nd):\n{diff}\n",
                    )
                )
            return

        if output_regexp:
            if not isinstance(output_regexp, re.Pattern):
                output_regexp = re.compile(output_regexp)
            if not output_regexp.search(output_actual):
                flags = ", ".join(
                    self.__prepare_regexp_flags(output_regexp.flags)
                )
                raise AssertionError(
                    message_template.format(
                        reason=f"{label} does not match the expected regexp",
                        detail=(
                            f"regexp:\n{output_regexp.pattern}\n"
                            f"regexp flags: {flags}\n"
                        ),
                    )
                )
            return

        expected_full = self.__prepare_output(output_full)
        if (despace and _despace(output_actual) != _despace(expected_full)) or (
            not despace and output_actual != expected_full
        ):
            diff = prepare_diff(output_actual, expected_full)
            raise AssertionError(
                message_template.format(
                    reason=f"{label} is not as expected",
                    detail=f"diff is (expected is 2nd):\n{diff}\n",
                ),
            )

    @staticmethod
    def __prepare_output(output):
        return "\n".join(output + [""]) if isinstance(output, list) else output

    @staticmethod
    def __prepare_regexp_flags(used_flags):
        return sorted([flag.name for flag in re.RegexFlag if used_flags & flag])


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
                except AttributeError as exc:
                    raise AssertionError(
                        "Property {property} doesn't exist in exception"
                        " {exception}".format(
                            property=prop, exception=exc.__class__.__name__
                        )
                    ) from exc


def assert_xml_equal(expected_xml, got_xml, context_explanation=""):
    checker = LXMLOutputChecker()
    if not checker.check_output(expected_xml, got_xml, 0):
        raise AssertionError(
            "{context_explanation}{xml_diff}".format(
                context_explanation=(
                    ""
                    if not context_explanation
                    else "\n{0}\n".format(context_explanation)
                ),
                xml_diff=checker.output_difference(
                    doctest.Example("", expected_xml), got_xml, 0
                ),
            )
        )


SEVERITY_SHORTCUTS = {
    reports.ReportItemSeverity.INFO: "I",
    reports.ReportItemSeverity.WARNING: "W",
    reports.ReportItemSeverity.DEPRECATION: "DW",
    reports.ReportItemSeverity.ERROR: "E",
    reports.ReportItemSeverity.DEBUG: "D",
}


def _format_report_item_info(info):
    return ", ".join(
        ["{0}:{1}".format(key, repr(value)) for key, value in info.items()]
    )


def _expected_report_item_format(report_item_expectation):
    return "{0} {1} {{{2}}} ! {3} {4}".format(
        SEVERITY_SHORTCUTS.get(
            report_item_expectation[0], report_item_expectation[0]
        ),
        report_item_expectation[1],
        _format_report_item_info(report_item_expectation[2]),
        (
            report_item_expectation[3]
            if len(report_item_expectation) > 3
            else None
        ),
        (
            report_item_expectation[4]
            if len(report_item_expectation) > 4
            else None
        ),
    )


def _format_report_item(report_item):
    return _expected_report_item_format(
        (
            report_item.severity.level,
            report_item.message.code,
            report_item.message.to_dto().payload,
            report_item.severity.force_code,
        )
    )


def assert_report_item_equal(real_report_item, report_item_info):
    if not __report_item_equal(real_report_item, report_item_info):
        raise AssertionError(
            "ReportItem not equal\nexpected: {0}\nactual:   {1}".format(
                repr(
                    (
                        report_item_info[0],
                        report_item_info[1],
                        report_item_info[2],
                        (
                            None
                            if len(report_item_info) < 4
                            else report_item_info[3]
                        ),
                        (
                            None
                            if len(report_item_info) < 5
                            else report_item_info[4]
                        ),
                    )
                ),
                _format_report_item(real_report_item),
            )
        )


def _unexpected_report_given(
    remaining_expected_report_info_list,
    expected_report_info_list,
    real_report_item,
    real_report_item_list,
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
        ).format(
            _format_report_item(real_report_item),
            len(remaining_expected_report_info_list),
            (
                "\n    ".join(
                    map(
                        _expected_report_item_format,
                        remaining_expected_report_info_list,
                    )
                )
                if remaining_expected_report_info_list
                else "No other report is expected!"
            ),
            len(expected_report_info_list),
            (
                "\n    ".join(
                    map(
                        _expected_report_item_format,
                        expected_report_info_list,
                    )
                )
                if expected_report_info_list
                else "No report is expected!"
            ),
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
            expected_report_info_list, real_report_item
        )
        if found_report_info is None:
            if (
                real_report_item.severity.level
                == reports.ReportItemSeverity.DEBUG
            ):
                # ignore debug report items not specified as expected
                continue
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
                caption, "-" * len(caption), "\n".join(map(repr, item_list))
            )

        raise AssertionError(
            "\nReport lists doesn't match{0}\n\n{1}\n\n{2}".format(
                "\n{0}".format(hint) if hint else "",
                format_items("expected", expected_report_info_list),
                format_items("real", real_report_item_list),
            )
        )


def assert_raise_library_error(callable_obj, *report_info_list):
    try:
        callable_obj()
        raise AssertionError("LibraryError not raised")
    except LibraryError as e:
        assert_report_item_list_equal(e.args, list(report_info_list))


def __find_report_info(expected_report_info_list, real_report_item):
    for report_info in expected_report_info_list:
        if __report_item_equal(real_report_item, report_info):
            return report_info
    return None


def __report_item_equal(
    real_report_item: reports.ReportItem, report_item_info: ReportItemFixture
) -> bool:
    report_dto: reports.ReportItemDto = real_report_item.to_dto()
    return (
        report_dto.severity.level == report_item_info[0]
        and report_dto.message.code == report_item_info[1]
        and report_dto.message.payload == report_item_info[2]
        and (
            report_dto.severity.force_code
            == (None if len(report_item_info) < 4 else report_item_info[3])
        )
        and report_dto.context
        == (report_item_info[4] if len(report_item_info) >= 5 else None)
    )


def assert_pcs_status(status1, status2):
    if _despace(status1) != _despace(status2):
        raise AssertionError(
            "strings not equal:\n{0}".format(prepare_diff(status1, status2))
        )


def _despace(string):
    # ignore whitespace changes between various pacemaker versions
    return re.sub(r"[ \t]+", " ", string)

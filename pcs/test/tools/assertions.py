from __future__ import (
    absolute_import,
    division,
    print_function,
)

import doctest
from lxml.doctestcompare import LXMLOutputChecker
from lxml.etree import LXML_VERSION
import re

from pcs.lib.errors import LibraryError
from pcs.test.tools.misc import prepare_diff

# cover python2 vs. python3 differences
_re_object_type = type(re.compile(""))

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

class AssertPcsMixin(object):
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
        self, command, stdout_full=None, stdout_start=None, stdout_regexp=None
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
            returncode=0
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
        returncode=0
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
        if len(specified_stdout) < 1:
            raise Exception(msg + ", none specified")
        elif len(specified_stdout) > 1:
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
            if stdout != expected_full:
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


class ExtendedAssertionsMixin(object):
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
                repr((
                    real_report_item.severity,
                    real_report_item.code,
                    real_report_item.info,
                    real_report_item.forceable
                ))
            )
        )

def assert_report_item_list_equal(real_report_item_list, report_info_list):
    for report_item in real_report_item_list:
        report_info_list.remove(
            __find_report_info(report_info_list, report_item)
        )
    if report_info_list:
        raise AssertionError(
            "LibraryError is missing expected ReportItems ("
            +str(len(report_info_list))+"):\n"
            + "\n".join(map(repr, report_info_list))

            + "\nreal ReportItems ("+str(len(real_report_item_list))+"):\n"
            + "\n".join(map(repr, real_report_item_list))
        )

def assert_raise_library_error(callableObj, *report_info_list):
    if not report_info_list:
        raise AssertionError(
            "Raising LibraryError expected, but no report item specified."
            + " Please specify report items, that you expect in LibraryError"
        )
    try:
        callableObj()
        raise AssertionError("LibraryError not raised")
    except LibraryError as e:
        assert_report_item_list_equal(e.args, list(report_info_list))

def __find_report_info(report_info_list, report_item):
    for report_info in report_info_list:
        if __report_item_equal(report_item, report_info):
            return report_info
    raise AssertionError(
        "Unexpected report given: \n{0} \nexpected reports are: \n{1}"
        .format(
            repr((
                report_item.severity,
                report_item.code,
                report_item.info,
                report_item.forceable
            )),
            "\n".join(map(repr, report_info_list)) if report_info_list
                else "  No report is expected!"
        )
    )

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

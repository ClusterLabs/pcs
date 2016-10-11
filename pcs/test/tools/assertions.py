from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import doctest
from lxml.doctestcompare import LXMLOutputChecker

from pcs.lib.errors import LibraryError
from pcs.test.tools.misc import prepare_diff

def console_report(*lines):
    #after lines append last new line
    return "\n".join(lines + ("",))

class AssertPcsMixin(object):
    """Run pcs command and assert its result"""

    def assert_pcs_success(self, command, stdout_full=None, stdout_start=None):
        full = stdout_full
        if stdout_start is None and stdout_full is None:
            full = ""
        self.assert_pcs_result(
            command,
            stdout_full=full,
            stdout_start=stdout_start
        )

    def assert_pcs_fail(self, command, stdout_full=None, stdout_start=None):
        self.assert_pcs_result(
            command,
            stdout_full=stdout_full,
            stdout_start=stdout_start,
            returncode=1
        )

    def assert_pcs_result(
        self, command, stdout_full=None, stdout_start=None, returncode=0
    ):
        msg = "Please specify exactly one: stdout_start or stdout_full"
        if stdout_start is None and stdout_full is None:
            raise Exception(msg + ", none specified")
        if stdout_start is not None and stdout_full is not None:
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
                self.assertTrue(
                    False,
                    message_template.format(
                        reason="Stdout does not start as expected",
                        cmd=command,
                        diff=prepare_diff(
                            stdout[:len(expected_start)], expected_start
                        ),
                        stdout=stdout
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


def assert_xml_equal(expected_xml, got_xml):
    checker = LXMLOutputChecker()
    if not checker.check_output(expected_xml, got_xml, 0):
        raise AssertionError(checker.output_difference(
            doctest.Example("", expected_xml),
            got_xml,
            0
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
            "\n".join(map(repr, report_info_list))
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


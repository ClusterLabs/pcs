import unittest

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    ParametrizedTestMetaClass,
    get_tmp_file,
    outdent,
    write_file_to_tmpfile,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.pcs_runner import PcsRunner

empty_cib = rc("cib-empty.xml")

ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)


class PcsAlertTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_alert")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()


class CreateAlertTest(PcsAlertTest):
    def test_create_multiple_without_id(self):
        self.assert_pcs_success("alert config".split(), "")

        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success("alert create path=test2".split())
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
 Alert: alert-1 (path=test)
 Alert: alert-2 (path=test2)
""",
        )

    def test_create_multiple_with_id(self):
        self.assert_pcs_success("alert config".split(), "")
        self.assert_pcs_success("alert create id=alert1 path=test".split())
        self.assert_pcs_success(
            "alert create id=alert2 description=desc path=test".split()
        )
        self.assert_pcs_success(
            "alert create description=desc2 path=test2 id=alert3".split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert1 (path=test)
 Alert: alert2 (path=test)
  Description: desc
 Alert: alert3 (path=test2)
  Description: desc2
""",
        )

    def test_create_with_options(self):
        self.assert_pcs_success(
            (
                "alert create id=alert1 description=desc path=test "
                "options opt2=val2 opt1=val1 meta m2=v2 m1=v1"
            ).split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert1 (path=test)
  Description: desc
  Options: opt1=val1 opt2=val2
  Meta options: m1=v1 m2=v2
""",
        )

    def test_already_exists(self):
        self.assert_pcs_success("alert create id=alert1 path=test".split())
        self.assert_pcs_fail(
            "alert create id=alert1 path=test".split(),
            "Error: 'alert1' already exists\n" + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert1 (path=test)
""",
        )

    def test_path_is_required(self):
        self.assert_pcs_fail(
            "alert create id=alert1".split(),
            "Error: required option 'path' is missing\n" + ERRORS_HAVE_OCCURRED,
        )


class UpdateAlertTest(PcsAlertTest):
    def test_update_everything(self):
        self.assert_pcs_success("alert config".split(), "")
        self.assert_pcs_success(
            (
                "alert create id=alert1 description=desc path=test "
                "options opt1=val1 opt3=val3 meta m1=v1 m3=v3"
            ).split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert1 (path=test)
  Description: desc
  Options: opt1=val1 opt3=val3
  Meta options: m1=v1 m3=v3
""",
        )
        self.assert_pcs_success(
            (
                "alert update alert1 description=new_desc path=/new/path "
                "options opt1= opt2=test opt3=1 meta m1= m2=v m3=3"
            ).split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert1 (path=/new/path)
  Description: new_desc
  Options: opt2=test opt3=1
  Meta options: m2=v m3=3
""",
        )

    def test_not_existing_alert(self):
        self.assert_pcs_fail(
            "alert update alert1".split(),
            "Error: alert 'alert1' does not exist\n",
        )


class DeleteRemoveAlertTest(PcsAlertTest):
    command = None

    def _test_usage(self):
        self.assert_pcs_fail(
            ["alert", self.command],
            stderr_start=outdent(
                f"""
                Usage: pcs alert <command>
                    {self.command} <"""
            ),
        )

    def _test_not_existing_alert(self):
        self.assert_pcs_fail(
            ["alert", self.command, "alert1"],
            ("Error: alert 'alert1' does not exist\n" + ERRORS_HAVE_OCCURRED),
        )

    def _test_one(self):
        self.assert_pcs_success("alert config".split(), "")

        self.assert_pcs_success("alert create path=test id=alert1".split())
        self.assert_pcs_success(
            "alert config".split(),
            outdent(
                """\
                Alerts:
                 Alert: alert1 (path=test)
                """
            ),
        )
        self.assert_pcs_success(["alert", self.command, "alert1"])
        self.assert_pcs_success("alert config".split(), "")

    def _test_multiple(self):
        self.assert_pcs_success("alert config".split(), "")

        self.assert_pcs_success("alert create path=test id=alert1".split())
        self.assert_pcs_success("alert create path=test id=alert2".split())
        self.assert_pcs_success("alert create path=test id=alert3".split())
        self.assert_pcs_success(
            "alert config".split(),
            outdent(
                """\
                Alerts:
                 Alert: alert1 (path=test)
                 Alert: alert2 (path=test)
                 Alert: alert3 (path=test)
                """
            ),
        )
        self.assert_pcs_success(["alert", self.command, "alert1", "alert3"])
        self.assert_pcs_success(
            "alert config".split(),
            outdent(
                """\
                Alerts:
                 Alert: alert2 (path=test)
                """
            ),
        )


class DeleteAlertTest(
    DeleteRemoveAlertTest, metaclass=ParametrizedTestMetaClass
):
    command = "delete"


class RemoveAlertTest(
    DeleteRemoveAlertTest, metaclass=ParametrizedTestMetaClass
):
    command = "remove"


class AddRecipientTest(PcsAlertTest):
    def test_success(self):
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
""",
        )
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value".split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
""",
        )
        self.assert_pcs_success(
            (
                "alert recipient add alert value=rec_value2 id=my-recipient "
                "description=description options o2=2 o1=1 meta m2=v2 m1=v1"
            ).split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
   Recipient: my-recipient (value=rec_value2)
    Description: description
    Options: o1=1 o2=2
    Meta options: m1=v1 m2=v2
""",
        )

    def test_already_exists(self):
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value id=rec".split()
        )
        self.assert_pcs_fail(
            "alert recipient add alert value=value id=rec".split(),
            "Error: 'rec' already exists\n" + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_fail(
            "alert recipient add alert value=value id=alert".split(),
            "Error: 'alert' already exists\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_same_value(self):
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value id=rec".split()
        )
        self.assert_pcs_fail(
            "alert recipient add alert value=rec_value".split(),
            (
                "Error: Recipient 'rec_value' in alert 'alert' already exists, "
                "use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: rec (value=rec_value)
""",
        )
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value --force".split(),
            stderr_full="Warning: Recipient 'rec_value' in alert 'alert' already exists\n",
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: rec (value=rec_value)
   Recipient: alert-recipient (value=rec_value)
""",
        )

    def test_no_value(self):
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_fail(
            "alert recipient add alert id=rec".split(),
            "Error: required option 'value' is missing\n"
            + ERRORS_HAVE_OCCURRED,
        )


class UpdateRecipientAlert(PcsAlertTest):
    def test_success(self):
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success(
            (
                "alert recipient add alert value=rec_value "
                "description=description options o1=1 o3=3 meta m1=v1 m3=v3"
            ).split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
    Description: description
    Options: o1=1 o3=3
    Meta options: m1=v1 m3=v3
""",
        )
        self.assert_pcs_success(
            (
                "alert recipient update alert-recipient value=new "
                "description=desc options o1= o2=v2 o3=3 meta m1= m2=2 m3=3"
            ).split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=new)
    Description: desc
    Options: o2=v2 o3=3
    Meta options: m2=2 m3=3
""",
        )
        self.assert_pcs_success(
            "alert recipient update alert-recipient value=new".split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=new)
    Description: desc
    Options: o2=v2 o3=3
    Meta options: m2=2 m3=3
""",
        )

    def test_value_exists(self):
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value".split()
        )
        self.assert_pcs_success("alert recipient add alert value=value".split())
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
   Recipient: alert-recipient-1 (value=value)
""",
        )
        self.assert_pcs_fail(
            "alert recipient update alert-recipient value=value".split(),
            (
                "Error: Recipient 'value' in alert 'alert' already exists, "
                "use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "alert recipient update alert-recipient value=value --force".split(),
            stderr_full="Warning: Recipient 'value' in alert 'alert' already exists\n",
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=value)
   Recipient: alert-recipient-1 (value=value)
""",
        )

    def test_value_same_as_previous(self):
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value".split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
""",
        )
        self.assert_pcs_success(
            "alert recipient update alert-recipient value=rec_value".split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
""",
        )

    def test_no_recipient(self):
        self.assert_pcs_fail(
            "alert recipient update rec description=desc".split(),
            "Error: recipient 'rec' does not exist\n",
        )

    def test_empty_value(self):
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value id=rec".split()
        )
        self.assert_pcs_fail(
            "alert recipient update rec value=".split(),
            "Error: Recipient value '' is not valid.\n" + ERRORS_HAVE_OCCURRED,
        )


class DeleteRemoveRecipientTest(PcsAlertTest):
    command = None

    def _test_usage(self):
        self.assert_pcs_fail(
            ["alert", "recipient", self.command],
            stderr_start=outdent(
                f"""
                Usage: pcs alert <command>
                    recipient {self.command} <"""
            ),
        )

    def _test_one(self):
        self.assert_pcs_success("alert create path=test".split())
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value id=rec".split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            outdent(
                """\
                Alerts:
                 Alert: alert (path=test)
                  Recipients:
                   Recipient: rec (value=rec_value)
                """
            ),
        )
        self.assert_pcs_success(["alert", "recipient", self.command, "rec"])
        self.assert_pcs_success(
            "alert config".split(),
            outdent(
                """\
                Alerts:
                 Alert: alert (path=test)
                """
            ),
        )

    def _test_multiple(self):
        self.assert_pcs_success("alert create path=test id=alert1".split())
        self.assert_pcs_success("alert create path=test id=alert2".split())
        self.assert_pcs_success(
            "alert recipient add alert1 value=rec_value1 id=rec1".split()
        )
        self.assert_pcs_success(
            "alert recipient add alert1 value=rec_value2 id=rec2".split()
        )
        self.assert_pcs_success(
            "alert recipient add alert2 value=rec_value3 id=rec3".split()
        )
        self.assert_pcs_success(
            "alert recipient add alert2 value=rec_value4 id=rec4".split()
        )
        self.assert_pcs_success(
            "alert config".split(),
            outdent(
                """\
                Alerts:
                 Alert: alert1 (path=test)
                  Recipients:
                   Recipient: rec1 (value=rec_value1)
                   Recipient: rec2 (value=rec_value2)
                 Alert: alert2 (path=test)
                  Recipients:
                   Recipient: rec3 (value=rec_value3)
                   Recipient: rec4 (value=rec_value4)
                """
            ),
        )
        self.assert_pcs_success(
            ["alert", "recipient", self.command, "rec1", "rec2", "rec4"]
        )
        self.assert_pcs_success(
            "alert config".split(),
            outdent(
                """\
                Alerts:
                 Alert: alert1 (path=test)
                 Alert: alert2 (path=test)
                  Recipients:
                   Recipient: rec3 (value=rec_value3)
                """
            ),
        )

    def _test_no_recipient(self):
        self.assert_pcs_success("alert create path=test id=alert1".split())
        self.assert_pcs_success(
            "alert recipient add alert1 value=rec_value1 id=rec1".split()
        )
        self.assert_pcs_fail(
            ["alert", "recipient", self.command, "rec1", "rec2", "rec3"],
            (
                "Error: recipient 'rec2' does not exist\n"
                "Error: recipient 'rec3' does not exist\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "alert config".split(),
            outdent(
                """\
                Alerts:
                 Alert: alert1 (path=test)
                  Recipients:
                   Recipient: rec1 (value=rec_value1)
                """
            ),
        )


class DeleteRecipientTest(
    DeleteRemoveRecipientTest, metaclass=ParametrizedTestMetaClass
):
    command = "delete"


class RemoveRecipientTest(
    DeleteRemoveRecipientTest, metaclass=ParametrizedTestMetaClass
):
    command = "remove"

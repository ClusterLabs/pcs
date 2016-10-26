
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil

from pcs.test.tools.misc import (
    get_test_resource as rc,
    is_minimum_pacemaker_version,
    outdent,
)
from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.pcs_runner import PcsRunner
from pcs.test.tools import pcs_unittest as unittest


old_cib = rc("cib-empty.xml")
empty_cib = rc("cib-empty-2.5.xml")
temp_cib = rc("temp-cib.xml")


ALERTS_SUPPORTED = is_minimum_pacemaker_version(1, 1, 15)
ALERTS_NOT_SUPPORTED_MSG = "Pacemaker version is too old (must be >= 1.1.15)" +\
    " to test alerts"


class PcsAlertTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)


@unittest.skipUnless(ALERTS_SUPPORTED, ALERTS_NOT_SUPPORTED_MSG)
class AlertCibUpgradeTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(old_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def test_cib_upgrade(self):
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 No alerts defined
"""
        )

        self.assert_pcs_success(
            "alert create path=test",
            "CIB has been upgraded to the latest schema version.\n"
        )

        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
"""
        )


@unittest.skipUnless(ALERTS_SUPPORTED, ALERTS_NOT_SUPPORTED_MSG)
class CreateAlertTest(PcsAlertTest):
    def test_create_multiple_without_id(self):
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 No alerts defined
"""
        )

        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success("alert create path=test2")
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
 Alert: alert-1 (path=test)
 Alert: alert-2 (path=test2)
"""
        )

    def test_create_multiple_with_id(self):
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 No alerts defined
"""
        )
        self.assert_pcs_success("alert create id=alert1 path=test")
        self.assert_pcs_success(
            "alert create id=alert2 description=desc path=test"
        )
        self.assert_pcs_success(
            "alert create description=desc2 path=test2 id=alert3"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert1 (path=test)
 Alert: alert2 (path=test)
  Description: desc
 Alert: alert3 (path=test2)
  Description: desc2
"""
        )

    def test_create_with_options(self):
        self.assert_pcs_success(
            "alert create id=alert1 description=desc path=test "
            "options opt1=val1 opt2=val2 meta m1=v1 m2=v2"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert1 (path=test)
  Description: desc
  Options: opt1=val1 opt2=val2
  Meta options: m1=v1 m2=v2
"""
        )

    def test_already_exists(self):
        self.assert_pcs_success("alert create id=alert1 path=test")
        self.assert_pcs_fail(
            "alert create id=alert1 path=test",
            "Error: 'alert1' already exists\n"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert1 (path=test)
"""
        )

    def test_path_is_required(self):
        self.assert_pcs_fail(
            "alert create id=alert1",
            "Error: required option 'path' is missing\n"
        )


@unittest.skipUnless(ALERTS_SUPPORTED, ALERTS_NOT_SUPPORTED_MSG)
class UpdateAlertTest(PcsAlertTest):
    def test_update_everything(self):
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 No alerts defined
"""
        )
        self.assert_pcs_success(
            "alert create id=alert1 description=desc path=test "
            "options opt1=val1 opt2=val2 meta m1=v1 m2=v2"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert1 (path=test)
  Description: desc
  Options: opt1=val1 opt2=val2
  Meta options: m1=v1 m2=v2
"""
        )
        self.assert_pcs_success(
            "alert update alert1 description=new_desc path=/new/path "
            "options opt1= opt2=test opt3=1 meta m1= m2=v m3=3"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert1 (path=/new/path)
  Description: new_desc
  Options: opt2=test opt3=1
  Meta options: m2=v m3=3
"""
        )

    def test_not_existing_alert(self):
        self.assert_pcs_fail(
            "alert update alert1", "Error: Alert 'alert1' not found.\n"
        )


@unittest.skipUnless(ALERTS_SUPPORTED, ALERTS_NOT_SUPPORTED_MSG)
class RemoveAlertTest(PcsAlertTest):
    def test_not_existing_alert(self):
        self.assert_pcs_fail(
            "alert remove alert1", "Error: Alert 'alert1' not found.\n"
        )

    def test_one(self):
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 No alerts defined
                """
            )
        )

        self.assert_pcs_success("alert create path=test id=alert1")
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 Alert: alert1 (path=test)
                """
            )
        )
        self.assert_pcs_success("alert remove alert1")
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 No alerts defined
                """
            )
        )

    def test_multiple(self):
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 No alerts defined
                """
            )
        )

        self.assert_pcs_success("alert create path=test id=alert1")
        self.assert_pcs_success("alert create path=test id=alert2")
        self.assert_pcs_success("alert create path=test id=alert3")
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 Alert: alert1 (path=test)
                 Alert: alert2 (path=test)
                 Alert: alert3 (path=test)
                """
            )
        )
        self.assert_pcs_success("alert remove alert1 alert3")
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 Alert: alert2 (path=test)
                """
            )
        )


@unittest.skipUnless(ALERTS_SUPPORTED, ALERTS_NOT_SUPPORTED_MSG)
class AddRecipientTest(PcsAlertTest):
    def test_success(self):
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
"""
        )
        self.assert_pcs_success("alert recipient add alert value=rec_value")
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
"""
        )
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value2 id=my-recipient "
            "description=description options o1=1 o2=2 meta m1=v1 m2=v2"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
   Recipient: my-recipient (value=rec_value2)
    Description: description
    Options: o1=1 o2=2
    Meta options: m1=v1 m2=v2
"""
        )

    def test_already_exists(self):
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value id=rec"
        )
        self.assert_pcs_fail(
            "alert recipient add alert value=value id=rec",
            "Error: 'rec' already exists\n"
        )
        self.assert_pcs_fail(
            "alert recipient add alert value=value id=alert",
            "Error: 'alert' already exists\n"
        )

    def test_same_value(self):
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value id=rec"
        )
        self.assert_pcs_fail(
            "alert recipient add alert value=rec_value",
            "Error: Recipient 'rec_value' in alert 'alert' already exists, "
            "use --force to override\n"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: rec (value=rec_value)
"""
        )
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value --force",
            "Warning: Recipient 'rec_value' in alert 'alert' already exists\n"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: rec (value=rec_value)
   Recipient: alert-recipient (value=rec_value)
"""
        )

    def test_no_value(self):
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_fail(
            "alert recipient add alert id=rec",
            "Error: required option 'value' is missing\n"
        )



@unittest.skipUnless(ALERTS_SUPPORTED, ALERTS_NOT_SUPPORTED_MSG)
class UpdateRecipientAlert(PcsAlertTest):
    def test_success(self):
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value description=description "
            "options o1=1 o2=2 meta m1=v1 m2=v2"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
    Description: description
    Options: o1=1 o2=2
    Meta options: m1=v1 m2=v2
"""
        )
        self.assert_pcs_success(
            "alert recipient update alert-recipient value=new description=desc "
            "options o1= o2=v2 o3=3 meta m1= m2=2 m3=3"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=new)
    Description: desc
    Options: o2=v2 o3=3
    Meta options: m2=2 m3=3
"""
        )
        self.assert_pcs_success(
            "alert recipient update alert-recipient value=new"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=new)
    Description: desc
    Options: o2=v2 o3=3
    Meta options: m2=2 m3=3
"""
        )

    def test_value_exists(self):
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success("alert recipient add alert value=rec_value")
        self.assert_pcs_success("alert recipient add alert value=value")
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
   Recipient: alert-recipient-1 (value=value)
"""
        )
        self.assert_pcs_fail(
            "alert recipient update alert-recipient value=value",
            "Error: Recipient 'value' in alert 'alert' already exists, "
            "use --force to override\n"
        )
        self.assert_pcs_success(
            "alert recipient update alert-recipient value=value --force",
            "Warning: Recipient 'value' in alert 'alert' already exists\n"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=value)
   Recipient: alert-recipient-1 (value=value)
"""
        )

    def test_value_same_as_previous(self):
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success("alert recipient add alert value=rec_value")
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
"""
        )
        self.assert_pcs_success(
            "alert recipient update alert-recipient value=rec_value"
        )
        self.assert_pcs_success(
            "alert config",
            """\
Alerts:
 Alert: alert (path=test)
  Recipients:
   Recipient: alert-recipient (value=rec_value)
"""
        )

    def test_no_recipient(self):
        self.assert_pcs_fail(
            "alert recipient update rec description=desc",
            "Error: Recipient 'rec' does not exist\n"
        )

    def test_empty_value(self):
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value id=rec"
        )
        self.assert_pcs_fail(
            "alert recipient update rec value=",
            "Error: Recipient value '' is not valid.\n"
        )


@unittest.skipUnless(ALERTS_SUPPORTED, ALERTS_NOT_SUPPORTED_MSG)
class RemoveRecipientTest(PcsAlertTest):
    def test_one(self):
        self.assert_pcs_success("alert create path=test")
        self.assert_pcs_success(
            "alert recipient add alert value=rec_value id=rec"
        )
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 Alert: alert (path=test)
                  Recipients:
                   Recipient: rec (value=rec_value)
                """
            )
        )
        self.assert_pcs_success("alert recipient remove rec")
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 Alert: alert (path=test)
                """
            )
        )

    def test_multiple(self):
        self.assert_pcs_success("alert create path=test id=alert1")
        self.assert_pcs_success("alert create path=test id=alert2")
        self.assert_pcs_success(
            "alert recipient add alert1 value=rec_value1 id=rec1"
        )
        self.assert_pcs_success(
            "alert recipient add alert1 value=rec_value2 id=rec2"
        )
        self.assert_pcs_success(
            "alert recipient add alert2 value=rec_value3 id=rec3"
        )
        self.assert_pcs_success(
            "alert recipient add alert2 value=rec_value4 id=rec4"
        )
        self.assert_pcs_success(
            "alert config", outdent("""\
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
            )
        )
        self.assert_pcs_success("alert recipient remove rec1 rec2 rec4")
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 Alert: alert1 (path=test)
                 Alert: alert2 (path=test)
                  Recipients:
                   Recipient: rec3 (value=rec_value3)
                """
            )
        )

    def test_no_recipient(self):
        self.assert_pcs_success("alert create path=test id=alert1")
        self.assert_pcs_success(
            "alert recipient add alert1 value=rec_value1 id=rec1"
        )
        self.assert_pcs_fail(
            "alert recipient remove rec1 rec2 rec3", outdent("""\
                Error: Recipient 'rec2' does not exist
                Error: Recipient 'rec3' does not exist
                """
            )
        )
        self.assert_pcs_success(
            "alert config", outdent("""\
                Alerts:
                 Alert: alert1 (path=test)
                  Recipients:
                   Recipient: rec1 (value=rec_value1)
                """
            )
        )

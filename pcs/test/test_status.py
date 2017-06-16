from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil
from textwrap import dedent

from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_runner import PcsRunner
from pcs.test.tools.pcs_unittest import TestCase


class StonithWarningTest(TestCase, AssertPcsMixin):
    empty_cib = rc("cib-empty.xml")
    temp_cib = rc("temp-cib.xml")

    def setUp(self):
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)

    def fixture_stonith(self, action=False):
        self.assert_pcs_success(
            "stonith create S fence_apc ipaddr=i login=l {0} --force".format(
                "action=reboot" if action else ""
            ),
            "Warning: stonith option 'action' is deprecated and should not be"
                " used, use pcmk_off_action, pcmk_reboot_action instead\n"
            if action
            else ""
        )

    def fixture_resource(self):
        self.assert_pcs_success(
            "resource create dummy ocf:pacemaker:Dummy action=reboot --force",
            "Warning: invalid resource option 'action', allowed options are: "
                "envfile, fail_start_on, fake, op_sleep, passwd, state,"
                " trace_file, trace_ra\n"
        )

    def test_warning_stonith_action(self):
        self.fixture_stonith(action=True)
        self.assert_pcs_success(
            "status",
            stdout_start=dedent("""\
                Cluster name: test99
                WARNING: following stonith devices have the 'action' attribute set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: S
                Stack: unknown
                Current DC: NONE
            """)
        )

    def test_action_ignored_for_non_stonith_resources(self):
        self.fixture_stonith(action=False)
        self.fixture_resource()

        self.assert_pcs_success(
            "status",
            stdout_start=dedent("""\
                Cluster name: test99
                Stack: unknown
                Current DC: NONE
            """)
        )

    def test_warn_when_no_stonith(self):
        self.assert_pcs_success(
            "status",
            stdout_start=dedent("""\
                Cluster name: test99
                WARNING: no stonith devices and stonith-enabled is not false
                Stack: unknown
                Current DC: NONE
            """)
        )

    def test_disabled_stonith_does_not_care_about_missing_devices(self):
        self.assert_pcs_success("property set stonith-enabled=false")
        self.assert_pcs_success(
            "status",
            stdout_start=dedent("""\
                Cluster name: test99
                Stack: unknown
                Current DC: NONE
            """)
        )

import shutil
from textwrap import dedent
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_test_resource as rc,
    is_minimum_pacemaker_version,
)
from pcs_test.tools.pcs_runner import PcsRunner

PCMK_2_0_3_PLUS = is_minimum_pacemaker_version(2, 0, 3)

class StonithWarningTest(TestCase, AssertPcsMixin):
    empty_cib = rc("cib-empty.xml")
    temp_cib = rc("temp-cib.xml")
    corosync_conf = rc("corosync.conf")

    def setUp(self):
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)

    def fixture_stonith_action(self):
        self.assert_pcs_success(
            "stonith create Sa fence_apc ip=i username=u action=reboot --force",
            "Warning: stonith option 'action' is deprecated and should not be"
                " used, use pcmk_off_action, pcmk_reboot_action instead\n"
        )

    def fixture_stonith_cycle(self):
        self.assert_pcs_success(
            "stonith create Sc fence_ipmilan method=cycle"
        )

    def fixture_resource(self):
        self.assert_pcs_success(
            "resource create dummy ocf:pacemaker:Dummy action=reboot "
                "method=cycle --force"
            ,
            "Warning: invalid resource options: 'action', 'method', allowed "
                "options are: 'envfile', 'fail_start_on', 'fake', 'op_sleep', "
                "'passwd', 'state', 'trace_file', 'trace_ra'\n"
        )

    def test_warning_stonith_action(self):
        self.fixture_stonith_action()
        self.fixture_resource()
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'action' option set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: 'Sa'

                    Cluster Summary:
                """)
            )
        else:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'action' option set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: 'Sa'

                    Stack: unknown
                    Current DC: NONE
                """)
            )

    def test_warning_stonith_method_cycle(self):
        self.fixture_stonith_cycle()
        self.fixture_resource()
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'method' option set to 'cycle' which is potentially dangerous, please consider using 'onoff': 'Sc'

                    Cluster Summary:
                """)
            )
        else:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'method' option set to 'cycle' which is potentially dangerous, please consider using 'onoff': 'Sc'

                    Stack: unknown
                    Current DC: NONE
                """)
            )

    def test_stonith_warnings(self):
        self.fixture_stonith_action()
        self.fixture_stonith_cycle()
        self.fixture_resource()
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'action' option set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: 'Sa'
                    Following stonith devices have the 'method' option set to 'cycle' which is potentially dangerous, please consider using 'onoff': 'Sc'

                    Cluster Summary:
                """)
            )
        else:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'action' option set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: 'Sa'
                    Following stonith devices have the 'method' option set to 'cycle' which is potentially dangerous, please consider using 'onoff': 'Sc'

                    Stack: unknown
                    Current DC: NONE
                """)
            )

    def test_warn_when_no_stonith(self):
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99

                    WARNINGS:
                    No stonith devices and stonith-enabled is not false

                    Cluster Summary:
                """)
            )
        else:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99

                    WARNINGS:
                    No stonith devices and stonith-enabled is not false

                    Stack: unknown
                    Current DC: NONE
                """)
            )

    def test_disabled_stonith_does_not_care_about_missing_devices(self):
        self.assert_pcs_success("property set stonith-enabled=false")
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99
                    Cluster Summary:
                """)
            )
        else:
            self.assert_pcs_success(
                "status",
                stdout_start=dedent("""\
                    Cluster name: test99
                    Stack: unknown
                    Current DC: NONE
                """)
            )

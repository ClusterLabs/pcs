from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
    outdent,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class OldCibPushTest(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier0_misc")
        write_file_to_tmpfile(rc("cib-empty-1.2.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def tearDown(self):
        self.temp_cib.close()

    def test_warning_old_push(self):
        self.assert_pcs_success(
            "resource create dummy ocf:pacemaker:Dummy --no-default-ops",
            "Warning: Replacing the whole CIB instead of applying a diff, "
            "a race condition may happen if the CIB is pushed more than "
            "once simultaneously. To fix this, upgrade pacemaker to get "
            "crm_feature_set at least 3.0.9, current is 3.0.8.\n",
        )
        self.assert_pcs_success(
            "resource config",
            # pylint: disable=line-too-long
            # fmt: off
            outdent(
            """\
             Resource: dummy (class=ocf provider=pacemaker type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
            ),
            # fmt: on
        )

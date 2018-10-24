import shutil
from unittest import TestCase

from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.misc import (
    get_test_resource as rc,
    outdent,
)
from pcs.test.tools.pcs_runner import PcsRunner

temp_cib = rc("temp-cib.xml")

class OldCibPushTest(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(rc("cib-empty-1.2.xml"), temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def test_warning_old_push(self):
        self.assert_pcs_success(
            "resource create dummy ocf:pacemaker:Dummy --no-default-ops",
            "Warning: Replacing the whole CIB instead of applying a diff, "
                "a race condition may happen if the CIB is pushed more than "
                "once simultaneously. To fix this, upgrade pacemaker to get "
                "crm_feature_set at least 3.0.9, current is 3.0.8.\n"
        )
        self.assert_pcs_success(
            "resource config",
            outdent("""\
             Resource: dummy (class=ocf provider=pacemaker type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """)
        )

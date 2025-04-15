from textwrap import dedent
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import get_tmp_file, write_data_to_tmpfile
from pcs_test.tools.pcs_runner import PcsRunner

CIB_EPOCH_TEMPLATE = """
    <cib epoch="{epoch}" num_updates="122" admin_epoch="0"
        validate-with="pacemaker-3.2" crm_feature_set="3.1.0"
        update-origin="rh7-3" update-client="crmd" cib-last-written="Thu Aug 23
        16:49:17 2012" have-quorum="0" dc-uuid="2"
    >
      <configuration>
        <crm_config/>
        <nodes>
        </nodes>
        <resources/>
        <constraints/>
      </configuration>
      <status/>
    </cib>
"""

CIB_EPOCH = CIB_EPOCH_TEMPLATE.format(epoch=500)
CIB_EPOCH_OLDER = CIB_EPOCH_TEMPLATE.format(epoch=499)
CIB_EPOCH_NEWER = CIB_EPOCH_TEMPLATE.format(epoch=501)

ERROR_CIB_OLD = (
    "Error: Unable to push to the CIB because pushed configuration is older "
    "than existing one. If you are sure you want to push this configuration, "
    "try to use --config to replace only configuration part instead of whole "
    "CIB. Otherwise get current configuration by running command 'pcs cluster "
    "cib' and update that.\n"
)


class CibPush(AssertPcsMixin, TestCase):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_cluster_cib_push")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        write_data_to_tmpfile(CIB_EPOCH, self.temp_cib)

        self.updated_cib = get_tmp_file("tier1_cluster_cib_push_updated")
        write_data_to_tmpfile("<cib/>", self.updated_cib)
        self.cib_push_cmd = f"cluster cib-push {self.updated_cib.name}".split()
        self.cib_push_diff_cmd = self.cib_push_cmd + [
            f"diff-against={self.temp_cib.name}"
        ]

    def tearDown(self):
        self.temp_cib.close()
        self.updated_cib.close()

    def assert_unable_to_diff(self, reason):
        self.assert_pcs_fail(
            self.cib_push_diff_cmd,
            "Error: unable to diff against original cib '{0}': {1}\n".format(
                self.temp_cib.name, reason
            ),
        )

    def test_cib_too_old(self):
        write_data_to_tmpfile(CIB_EPOCH_OLDER, self.updated_cib)
        self.assert_pcs_fail(self.cib_push_cmd, ERROR_CIB_OLD)

    def test_bad_args(self):
        self.assert_pcs_fail(
            "cluster cib-push a b c".split(), stderr_start="\nUsage: "
        )

    def test_error_scope_and_config(self):
        self.assert_pcs_fail(
            "cluster cib-push file scope=configuration --config".split(),
            "Error: Cannot use both scope and --config\n",
        )

    def test_error_invalid_scope(self):
        self.assert_pcs_fail(
            "cluster cib-push file scope=invalid-scope".split(),
            "Error: invalid CIB scope 'invalid-scope'\n",
        )

    def test_error_scope_and_diff(self):
        self.assert_pcs_fail(
            "cluster cib-push file scope=configuration diff-against=f".split(),
            stderr_start="\nUsage: ",
        )

    def test_error_diff_and_config(self):
        self.assert_pcs_fail(
            "cluster cib-push file diff-against=f --config".split(),
            "Error: Cannot use both scope and diff-against\n",
        )

    def test_error_unknown_option(self):
        self.assert_pcs_fail(
            "cluster cib-push file unknown=value".split(),
            stderr_start="\nUsage: ",
        )

    def test_error_scope_not_present(self):
        self.assert_pcs_fail(
            self.cib_push_cmd + ["--config"],
            (
                "Error: unable to push cib, scope 'configuration' not present "
                "in new cib\n"
            ),
        )

    def test_unable_to_parse_new_cib(self):
        write_data_to_tmpfile("", self.updated_cib)
        self.assert_pcs_fail(
            self.cib_push_cmd, stderr_start="Error: unable to parse new cib:"
        )

    def test_diff_no_difference(self):
        write_data_to_tmpfile(CIB_EPOCH, self.updated_cib)
        self.assert_pcs_success(
            self.cib_push_diff_cmd,
            stderr_full=(
                "The new CIB is the same as the original CIB, nothing to push.\n"
            ),
        )

    def test_cib_updated(self):
        write_data_to_tmpfile(CIB_EPOCH_NEWER, self.updated_cib)
        self.assert_pcs_success(
            self.cib_push_cmd,
            stderr_full=dedent("""\
                CIB updated
                error: Resource start-up disabled since no STONITH resources have been defined
                error: Either configure some or disable STONITH with the stonith-enabled option
                error: NOTE: Clusters with shared data need STONITH to ensure data integrity
                error: CIB did not pass schema validation
                Errors found during check: config not valid
                """),
        )

import json
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_tmp_file,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

from .common import fixture_corosync_conf_minimal


class ClusterUuidGenerateLocal(AssertPcsMixin, TestCase):
    def setUp(self):
        self.corosync_conf_file = get_tmp_file(
            "tier1_cluster_config_uuid_generate.conf"
        )
        self.pcs_runner = PcsRunner(
            cib_file=None,
            corosync_conf_opt=self.corosync_conf_file.name,
        )

    def tearDown(self):
        self.corosync_conf_file.close()

    def test_uuid_not_present(self):
        write_data_to_tmpfile(
            fixture_corosync_conf_minimal(no_cluster_uuid=True),
            self.corosync_conf_file,
        )
        self.assert_pcs_success(["cluster", "config", "uuid", "generate"])
        corosync_json_after, stderr, retval = self.pcs_runner.run(
            ["cluster", "config", "show", "--output-format=json"]
        )
        self.assertIn("cluster_uuid", json.loads(corosync_json_after))
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_uuid_present(self):
        write_data_to_tmpfile(
            fixture_corosync_conf_minimal(),
            self.corosync_conf_file,
        )
        self.assert_pcs_fail(
            ["cluster", "config", "uuid", "generate"],
            (
                "Error: Cluster UUID has already been set, use --force "
                "to override\n"
                "Error: Errors have occurred, therefore pcs is unable "
                "to continue\n"
            ),
        )

    def test_uuid_present_with_force(self):
        write_data_to_tmpfile(
            fixture_corosync_conf_minimal(),
            self.corosync_conf_file,
        )
        corosync_json_before, _, _ = self.pcs_runner.run(
            ["cluster", "config", "show", "--output-format=json"]
        )
        self.assert_pcs_success(
            ["cluster", "config", "uuid", "generate", "--force"],
            stderr_full="Warning: Cluster UUID has already been set\n",
        )
        corosync_json_after, _, _ = self.pcs_runner.run(
            ["cluster", "config", "show", "--output-format=json"]
        )
        self.assertNotEqual(
            json.loads(corosync_json_before)["cluster_uuid"],
            json.loads(corosync_json_after)["cluster_uuid"],
        )

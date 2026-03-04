from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner
from pcs_test.tools.xml import str_to_etree


class NodeRenameCib(AssertPcsMixin, TestCase):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_node_rename_cib")
        write_file_to_tmpfile(get_test_resource("cib-all.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_rename_updates_cib(self):
        self.assert_pcs_success(
            ["cluster", "node", "rename-cib", "localhost", "new-name"],
            stderr_full=(
                "Location constraint 'location-R7-localhost-INFINITY': "
                "node updated from 'localhost' to 'new-name'\n"
                "Location constraint 'location-G2-localhost-INFINITY': "
                "node updated from 'localhost' to 'new-name'\n"
                "Location constraint 'location-R-localhost-INFINITY': "
                "node updated from 'localhost' to 'new-name'\n"
            ),
        )
        self.temp_cib.seek(0)
        cib_tree = str_to_etree(self.temp_cib.read())
        self.assertEqual(
            len(cib_tree.xpath("//rsc_location[@node='new-name']")), 3
        )
        self.assertEqual(
            len(cib_tree.xpath("//rsc_location[@node='localhost']")), 0
        )
        # irrelevant constraints unchanged
        self.assertEqual(
            len(cib_tree.xpath("//rsc_location[@node='non-existing-node']")), 1
        )
        self.assertEqual(
            len(cib_tree.xpath("//rsc_location[@node='another-one']")), 1
        )

    def test_no_match_no_change(self):
        self.assert_pcs_success(
            ["cluster", "node", "rename-cib", "nonexistent", "new-name"],
            stderr_full=(
                "No CIB configuration changes needed for node rename\n"
            ),
        )

    def test_usage_error_no_args(self):
        self.assert_pcs_fail(
            ["cluster", "node", "rename-cib"],
            stderr_start="\nUsage: pcs cluster",
        )

    def test_usage_error_too_many_args(self):
        self.assert_pcs_fail(
            ["cluster", "node", "rename-cib", "a", "b", "c"],
            stderr_start="\nUsage: pcs cluster",
        )

from unittest import TestCase

from pcs.common import reports
from pcs.lib.cluster import validations

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class ValidateAddCluster(TestCase):
    def test_valid_no_reports(self):
        report_list = validations.validate_add_cluster(
            "NAME", ["NODE1", "NODE2", "NODE3"]
        )
        assert_report_item_list_equal(report_list, [])

    def test_invalid_name(self):
        report_list = validations.validate_add_cluster(
            "", ["NODE1", "NODE2", "NODE3"]
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="cluster name",
                    option_value="",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_empty_nodes(self):
        report_list = validations.validate_add_cluster("NAME", [])
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="nodes",
                    option_value="[]",
                    allowed_values="non-empty list of nodes",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_empty_node_names(self):
        report_list = validations.validate_add_cluster(
            "NAME", ["NODE1", "", "NODE3"]
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="node name",
                    option_value="",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_duplicate_node_names(self):
        report_list = validations.validate_add_cluster(
            "NAME", ["NODE1", "NODE2", "NODE3", "NODE1", "NODE2"]
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.NODE_NAMES_DUPLICATION,
                    name_list=["NODE1", "NODE2"],
                )
            ],
        )


class ValidateRemoveClusters(TestCase):
    def test_valid_no_reports(self):
        report_list = validations.validate_remove_clusters(
            ["CLUSTER1", "CLUSTER2", "CLUSTER3"]
        )
        assert_report_item_list_equal(report_list, [])

    def test_empty_list(self):
        report_list = validations.validate_remove_clusters([])
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    container_type=None,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_CLUSTER,
                    container_id=None,
                )
            ],
        )

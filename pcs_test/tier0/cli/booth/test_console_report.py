from pcs_test.tier0.cli.common.test_console_report import NameBuildTest

from pcs.lib.booth import reports


class BoothConfigAccetedByNodeTest(NameBuildTest):

    def test_empty_name_list(self):
        self.assert_message_from_report(
            "Booth config saved",
            reports.booth_config_accepted_by_node(
                name_list=[]
            )
        )

    def test_name_booth_only(self):
        self.assert_message_from_report(
            "Booth config saved",
            reports.booth_config_accepted_by_node(
                name_list=["booth"]
            )
        )

    def test_single_name(self):
        self.assert_message_from_report(
            "Booth config 'some' saved",
            reports.booth_config_accepted_by_node(
                name_list=["some"]
            )
        )

    def test_multiple_names(self):
        self.assert_message_from_report(
            "Booth configs 'another', 'some' saved",
            reports.booth_config_accepted_by_node(
                name_list=["some", "another"],
            )
        )

    def test_node(self):
        self.assert_message_from_report(
            "node1: Booth configs 'another', 'some' saved",
            reports.booth_config_accepted_by_node(
                node="node1",
                name_list=["some", "another"],
            )
        )

class BoothConfigDistributionNodeErrorTest(NameBuildTest):

    def test_empty_name(self):
        self.assert_message_from_report(
            "Unable to save booth config on node 'node1': reason1",
            reports.booth_config_distribution_node_error(
                "node1", "reason1",
            )
        )

    def test_booth_name(self):
        self.assert_message_from_report(
            "Unable to save booth config on node 'node1': reason1",
            reports.booth_config_distribution_node_error(
                "node1", "reason1", name="booth"
            )
        )

    def test_another_name(self):
        self.assert_message_from_report(
            "Unable to save booth config 'another' on node 'node1': reason1",
            reports.booth_config_distribution_node_error(
                "node1", "reason1", name="another"
            )
        )

class BoothConfigReadErrorTest(NameBuildTest):

    def test_empty_name(self):
        self.assert_message_from_report(
            "Unable to read booth config",
            reports.booth_config_read_error(None)
        )

    def test_booth_name(self):
        self.assert_message_from_report(
            "Unable to read booth config",
            reports.booth_config_read_error("booth")
        )

    def test_another_name(self):
        self.assert_message_from_report(
            "Unable to read booth config 'another'",
            reports.booth_config_read_error("another")
        )

class BoothFetchingConfigFromNodeTest(NameBuildTest):

    def test_empty_name(self):
        self.assert_message_from_report(
            "Fetching booth config from node 'node1'...",
            reports.booth_fetching_config_from_node_started("node1")
        )

    def test_booth_name(self):
        self.assert_message_from_report(
            "Fetching booth config from node 'node1'...",
            reports.booth_fetching_config_from_node_started(
                "node1", config="booth"
            )
        )

    def test_another_name(self):
        self.assert_message_from_report(
            "Fetching booth config 'another' from node 'node1'...",
            reports.booth_fetching_config_from_node_started(
                "node1", config="another"
            )
        )

class BoothUnsupportedFileLocation(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Path '/some/file' is not supported for booth config files",
            reports.booth_unsupported_file_location("/some/file")
        )

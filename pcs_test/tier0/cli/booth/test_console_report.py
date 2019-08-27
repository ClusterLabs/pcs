from pcs_test.tier0.cli.common.test_console_report import NameBuildTest

from pcs.lib.booth import reports


class BoothLackOfSitesTest(NameBuildTest):

    def test_no_site(self):
        self.assert_message_from_report(
            (
                "lack of sites for booth configuration (need 2 at least): "
                "sites missing"
            ),
            reports.booth_lack_of_sites([])
        )

    def test_single_site(self):
        self.assert_message_from_report(
            (
                "lack of sites for booth configuration (need 2 at least): "
                "sites site1"
            ),
            reports.booth_lack_of_sites(["site1"])
        )

    def test_multiple_sites(self):
        self.assert_message_from_report(
            (
                "lack of sites for booth configuration (need 2 at least): "
                "sites site1, site2"
            ),
            reports.booth_lack_of_sites(["site1", "site2"])
        )

class BoothEvenPeersNumTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "odd number of peers is required (entered 4 peers)",
            reports.booth_even_peers_num(4)
        )

class BoothAddressDuplicationTest(NameBuildTest):

    def test_single_address(self):
        self.assert_message_from_report(
            "duplicate address for booth configuration: addr1",
            reports.booth_address_duplication(["addr1"])
        )

    def test_multiple_addresses(self):
        self.assert_message_from_report(
            "duplicate address for booth configuration: addr1, addr2, addr3",
            reports.booth_address_duplication(["addr2", "addr1", "addr3"])
        )

class BoothConfigUnexpectedLinesTest(NameBuildTest):

    def test_single_line(self):
        self.assert_message_from_report(
            "unexpected line appeard in config: \nline",
            reports.booth_config_unexpected_lines(["line"])
        )

    def test_multiple_lines(self):
        self.assert_message_from_report(
            "unexpected line appeard in config: \nline\nline2",
            reports.booth_config_unexpected_lines(["line", "line2"])
        )

class BoothInvalidNameTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "booth name '/name' is not valid (invalid characters)",
            reports.booth_invalid_name("/name", "invalid characters")
        )

class BoothTicketNameInvalidTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            (
                "booth ticket name 'ticket&' is not valid, use alphanumeric "
                "chars or dash"
            ),
            reports.booth_ticket_name_invalid("ticket&")
        )

class BoothTicketDuplicateTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "booth ticket name 'ticket_name' already exists in configuration",
            reports.booth_ticket_duplicate("ticket_name")
        )

class BoothTicketDoesNotExistTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "booth ticket name 'ticket_name' does not exist",
            reports.booth_ticket_does_not_exist("ticket_name")
        )

class BoothAlreadyInCibTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "booth instance 'name' is already created as cluster resource",
            reports.booth_already_in_cib("name")
        )

class BoothNotExistsInCibTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "booth instance 'name' not found in cib",
            reports.booth_not_exists_in_cib("name")
        )

class BoothConfigIsUsedTest(NameBuildTest):

    def test_minimal(self):
        self.assert_message_from_report(
            "booth instance 'name' is used",
            reports.booth_config_is_used("name")
        )

    def test_all(self):
        self.assert_message_from_report(
            "booth instance 'name' is used some details",
            reports.booth_config_is_used("name", detail="some details")
        )

class BoothMultipleTimesInCibTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "found more than one booth instance 'name' in cib",
            reports.booth_multiple_times_in_cib("name")
        )

class BoothConfigDistributionStartedTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "Sending booth configuration to cluster nodes...",
            reports.booth_config_distribution_started()
        )

class BoothConfigAcceptedByNodeTest(NameBuildTest):

    def test_defaults(self):
        self.assert_message_from_report(
            "Booth config saved",
            reports.booth_config_accepted_by_node()
        )

    def test_empty_name_list(self):
        self.assert_message_from_report(
            "Booth config saved",
            reports.booth_config_accepted_by_node(
                name_list=[]
            )
        )

    def test_node_and_empty_name_list(self):
        self.assert_message_from_report(
            "node1: Booth config saved",
            reports.booth_config_accepted_by_node(
                node="node1",
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

    def test_name_booth_and_node(self):
        self.assert_message_from_report(
            "node1: Booth config saved",
            reports.booth_config_accepted_by_node(
                node="node1",
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

class BoothDaemonStatusErrorTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "unable to get status of booth daemon: some reason",
            reports.booth_daemon_status_error("some reason")
        )

class BoothTicketsStatusErrorTest(NameBuildTest):

    def test_minimal(self):
        self.assert_message_from_report(
            "unable to get status of booth tickets",
            reports.booth_tickets_status_error()
        )

    def test_all(self):
        self.assert_message_from_report(
            "unable to get status of booth tickets",
            reports.booth_tickets_status_error(reason="some reason")
        )

class BoothPeersStatusErrorTest(NameBuildTest):

    def test_minimal(self):
        self.assert_message_from_report(
            "unable to get status of booth peers",
            reports.booth_peers_status_error()
        )

    def test_all(self):
        self.assert_message_from_report(
            "unable to get status of booth peers",
            reports.booth_peers_status_error(reason="some reason")
        )

class BoothCannotDetermineLocalSiteIpTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "cannot determine local site ip, please specify site parameter",
            reports.booth_cannot_determine_local_site_ip()
        )

class BoothTicketOperationFailedTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            (
                "unable to operation booth ticket 'ticket_name'"
                " for site 'site_ip', reason: reason"
            ),
            reports.booth_ticket_operation_failed(
                "operation", "reason", "site_ip", "ticket_name"
            )
        )

class BoothSkippingConfigTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "Skipping config file 'config_file': reason",
            reports.booth_skipping_config("config_file", "reason")
        )

class BoothCannotIdentifyKeyFileTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            "cannot identify authfile in booth configuration",
            reports.booth_cannot_identify_keyfile()
        )

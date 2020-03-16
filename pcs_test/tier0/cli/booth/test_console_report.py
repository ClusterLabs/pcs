from pcs_test.tier0.cli.common.test_console_report import NameBuildTest

from pcs.common import file_type_codes
from pcs.lib.booth import reports

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
            (
                "Booth configuration '/some/file' is outside of supported "
                "booth config directory '/etc/booth/', ignoring the file"
            ),
            reports.booth_unsupported_file_location(
                "/some/file",
                "/etc/booth/",
                file_type_codes.BOOTH_CONFIG,
            )
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

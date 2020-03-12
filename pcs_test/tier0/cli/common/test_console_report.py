# pylint: disable=too-many-lines

from unittest import mock, TestCase

# TODO: move tests for these functions to proper location
from pcs.common.str_tools import(
    format_optional,
    format_plural,
    _is_multiple,
    _add_s
)
from pcs.cli.common.reports import CODE_BUILDER_MAP
from pcs.common.reports import ReportItem
from pcs.lib import reports

class NameBuildTest(TestCase):
    """
    Base class for the testing of message building.
    """
    def assert_message_from_report(self, message, report, force_text=None):
        if not isinstance(report, ReportItem):
            raise AssertionError("report is not an instance of ReportItem")
        info = report.info if report.info else {}
        build = CODE_BUILDER_MAP[report.code]
        if force_text is not None:
            self.assertEqual(
                message,
                build(info, force_text)
            )
        else:
            self.assertEqual(
                message,
                build(info) if callable(build) else build
            )


class CibMissingMandatorySection(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to get section-name section of cib",
            reports.cib_missing_mandatory_section("section-name")
        )

class CibSaveTmpError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to save CIB to a temporary file: reason",
            reports.cib_save_tmp_error("reason")
        )

class IdAlreadyExists(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "'id' already exists",
            reports.id_already_exists("id")
        )


class FormatOptionalTest(TestCase):
    def test_info_key_is_falsy(self):
        self.assertEqual("", format_optional("", "{0}: "))

    def test_info_key_is_not_falsy(self):
        self.assertEqual("A: ", format_optional("A", "{0}: "))

    def test_default_value(self):
        self.assertEqual("DEFAULT", format_optional("", "{0}: ", "DEFAULT"))

    def test_integer_zero_is_not_falsy(self):
        self.assertEqual("0: ", format_optional(0, "{0}: "))

class IsMultipleTest(TestCase):
    def test_unsupported(self):
        def empty_func():
            pass
        self.assertFalse(_is_multiple(empty_func()))

    def test_empty_string(self):
        self.assertFalse(_is_multiple(""))

    def test_string(self):
        self.assertFalse(_is_multiple("some string"))

    def test_list_empty(self):
        self.assertTrue(_is_multiple(list()))

    def test_list_single(self):
        self.assertFalse(_is_multiple(["the only list item"]))

    def test_list_multiple(self):
        self.assertTrue(_is_multiple(["item1", "item2"]))

    def test_dict_empty(self):
        self.assertTrue(_is_multiple(dict()))

    def test_dict_single(self):
        self.assertFalse(_is_multiple({"the only index": "something"}))

    def test_dict_multiple(self):
        self.assertTrue(_is_multiple({1: "item1", 2: "item2"}))

    def test_set_empty(self):
        self.assertTrue(_is_multiple(set()))

    def test_set_single(self):
        self.assertFalse(_is_multiple({"the only set item"}))

    def test_set_multiple(self):
        self.assertTrue(_is_multiple({"item1", "item2"}))

    def test_integer_zero(self):
        self.assertTrue(_is_multiple(0))

    def test_integer_one(self):
        self.assertFalse(_is_multiple(1))

    def test_integer_negative_one(self):
        self.assertFalse(_is_multiple(-1))

    def test_integer_more(self):
        self.assertTrue(_is_multiple(3))

class AddSTest(TestCase):
    def test_add_s(self):
        self.assertEqual(_add_s("fedora"), "fedoras")

    def test_add_es_s(self):
        self.assertEqual(_add_s("bus"), "buses")

    def test_add_es_x(self):
        self.assertEqual(_add_s("box"), "boxes")

    def test_add_es_o(self):
        self.assertEqual(_add_s("zero"), "zeroes")

    def test_add_es_ss(self):
        self.assertEqual(_add_s("address"), "addresses")

    def test_add_es_sh(self):
        self.assertEqual(_add_s("wish"), "wishes")

    def test_add_es_ch(self):
        self.assertEqual(_add_s("church"), "churches")

@mock.patch("pcs.common.str_tools._add_s")
@mock.patch("pcs.common.str_tools._is_multiple")
class FormatPluralTest(TestCase):
    def test_is_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "is", format_plural(1, "is")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(1)

    def test_is_pl(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = True
        self.assertEqual(
            "are", format_plural(2, "is")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(2)

    def test_do_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "does", format_plural("he", "does")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with("he")

    def test_do_pl(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = True
        self.assertEqual(
            "do", format_plural(["he", "she"], "does")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(["he", "she"])

    def test_have_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "has", format_plural("he", "has")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with("he")

    def test_have_pl(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = True
        self.assertEqual(
            "have", format_plural(["he", "she"], "has")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(["he", "she"])

    def test_plural_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "singular", format_plural(1, "singular", "plural")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(1)

    def test_plural_pl(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = True
        self.assertEqual(
            "plural", format_plural(10, "singular", "plural")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(10)

    def test_regular_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "greeting", format_plural(1, "greeting")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(1)

    def test_regular_pl(self, mock_is_multiple, mock_add_s):
        mock_add_s.return_value = "greetings"
        mock_is_multiple.return_value = True
        self.assertEqual(
            "greetings", format_plural(10, "greeting")
        )
        mock_add_s.assert_called_once_with("greeting")
        mock_is_multiple.assert_called_once_with(10)

class AgentNameGuessedTest(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "Assumed agent name 'ocf:heartbeat:Delay' (deduced from 'Delay')",
            reports.agent_name_guessed("Delay", "ocf:heartbeat:Delay")
        )

class UnableToGetAgentMetadata(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Agent 'agent-name' is not installed or does not provide valid "
                "metadata: reason"
            ),
            reports.unable_to_get_agent_metadata("agent-name", "reason")
        )

class AgentNameGuessFoundMoreThanOne(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Multiple agents match 'agent', please specify full name: "
                "agent1, agent2"
            ),
            reports.agent_name_guess_found_more_than_one(
                "agent", ["agent2", "agent1"]
            )
        )

class AgentNameGuessFoundNone(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to find agent 'agent-name', try specifying its full name",
            reports.agent_name_guess_found_none("agent-name")
        )

class InvalidResourceAgentNameTest(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "Invalid resource agent name ':name'."
                " Use standard:provider:type when standard is 'ocf' or"
                " standard:type otherwise. List of standards and providers can"
                " be obtained by using commands 'pcs resource standards' and"
                " 'pcs resource providers'"
            ,
            reports.invalid_resource_agent_name(":name")
        )

class InvalidiStonithAgentNameTest(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "Invalid stonith agent name 'fence:name'. List of agents can be"
                " obtained by using command 'pcs stonith list'. Do not use the"
                " 'stonith:' prefix. Agent name cannot contain the ':'"
                " character."
            ,
            reports.invalid_stonith_agent_name("fence:name")
        )


class StonithResourcesDoNotExist(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Stonith resource(s) 'device1', 'device2' do not exist",
            reports.stonith_resources_do_not_exist(["device2", "device1"])
        )

class ResourceBundleAlreadyContainsAResource(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            (
                "bundle 'test_bundle' already contains resource "
                "'test_resource', a bundle may contain at most one resource"
            ),
            reports.resource_bundle_already_contains_a_resource(
                "test_bundle", "test_resource"
            )
        )


class ResourceOperationIntevalDuplicationTest(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "multiple specification of the same operation with the same"
                " interval:"
                "\nmonitor with intervals 3600s, 60m, 1h"
                "\nmonitor with intervals 60s, 1m"
            ,
            reports.resource_operation_interval_duplication(
                {
                    "monitor": [
                        ["3600s", "60m", "1h"],
                        ["60s", "1m"],
                    ],
                }
            )
        )

class ResourceOperationIntevalAdaptedTest(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "changing a monitor operation interval from 10 to 11 to make the"
                " operation unique"
            ,
            reports.resource_operation_interval_adapted(
                "monitor", "10", "11"
            )
        )

class IdBelongsToUnexpectedType(NameBuildTest):
    def test_build_message_with_single_type(self):
        self.assert_message_from_report(
            "'ID' is not an ACL permission",
            reports.id_belongs_to_unexpected_type(
                "ID", ["acl_permission"], "op"
            )
        )

    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "'ID' is not a clone/resource",
            reports.id_belongs_to_unexpected_type(
                "ID", ["primitive", "clone"], "op"
            )
        )

    def test_build_message_with_transformation_and_article(self):
        self.assert_message_from_report(
            "'ID' is not an ACL group/ACL user",
            reports.id_belongs_to_unexpected_type(
                "ID", ["acl_target", "acl_group"], "op",
            )
        )

class ObjectWithIdInUnexpectedContext(NameBuildTest):
    def test_with_context_id(self):
        self.assert_message_from_report(
            "resource 'R' exists but does not belong to group 'G'",
            reports.object_with_id_in_unexpected_context(
                "primitive", "R", "group", "G"
            )
        )

    def test_without_context_id(self):
        self.assert_message_from_report(
            "group 'G' exists but does not belong to 'resource'",
            reports.object_with_id_in_unexpected_context(
                "group", "G", "primitive", ""
            )
        )

class ResourceRunOnNodes(NameBuildTest):
    def test_one_node(self):
        self.assert_message_from_report(
            "resource 'R' is running on node 'node1'",
            reports.resource_running_on_nodes("R", {"Started": ["node1"]})
        )
    def test_multiple_nodes(self):
        self.assert_message_from_report(
            "resource 'R' is running on nodes 'node1', 'node2'",
            reports.resource_running_on_nodes(
                "R", {"Started": ["node1", "node2"]}
            )
        )
    def test_multiple_role_multiple_nodes(self):
        self.assert_message_from_report(
            "resource 'R' is master on node 'node3'"
            "; running on nodes 'node1', 'node2'"
            ,
            reports.resource_running_on_nodes(
                "R",
                {
                    "Started": ["node1", "node2"],
                    "Master": ["node3"],
                }
            )
        )

class ResourceDoesNotRun(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "resource 'R' is not running on any node",
            reports.resource_does_not_run("R")
        )


class ResourceIsUnmanaged(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "'R' is unmanaged",
            reports.resource_is_unmanaged("R")
        )


class SbdDeviceInitializationStarted(NameBuildTest):
    def test_more_devices(self):
        self.assert_message_from_report(
            "Initializing devices '/dev1', '/dev2', '/dev3'...",
            reports.sbd_device_initialization_started(
                ["/dev3", "/dev2", "/dev1"]
            )
        )

    def test_one_device(self):
        self.assert_message_from_report(
            "Initializing device '/dev1'...",
            reports.sbd_device_initialization_started(["/dev1"])
        )


class SbdDeviceInitializationSuccess(NameBuildTest):
    def test_more_devices(self):
        self.assert_message_from_report(
            "Devices initialized successfully",
            reports.sbd_device_initialization_success(["/dev2", "/dev1"])
        )

    def test_one_device(self):
        self.assert_message_from_report(
            "Device initialized successfully",
            reports.sbd_device_initialization_success(["/dev1"])
        )


class SbdDeviceInitializationError(NameBuildTest):
    def test_more_devices(self):
        self.assert_message_from_report(
            "Initialization of devices '/dev1', '/dev2' failed: this is reason",
            reports.sbd_device_initialization_error(
                ["/dev2", "/dev1"], "this is reason"
            )
        )

    def test_one_device(self):
        self.assert_message_from_report(
            "Initialization of device '/dev2' failed: this is reason",
            reports.sbd_device_initialization_error(["/dev2"], "this is reason")
        )


class SbdDeviceListError(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Unable to get list of messages from device '/dev': this is reason",
            reports.sbd_device_list_error("/dev", "this is reason")
        )


class SbdDeviceMessageError(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            (
                "Unable to set message 'test' for node 'node1' on device "
                "'/dev1': this is reason"
            ),
            reports.sbd_device_message_error(
                "/dev1", "node1", "test", "this is reason"
            )
        )


class SbdDeviceDumpError(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Unable to get SBD headers from device '/dev1': this is reason",
            reports.sbd_device_dump_error("/dev1", "this is reason")
        )


class SbdCheckStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Running SBD pre-enabling checks...",
            reports.sbd_check_started()
        )

class SbdCheckSuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: SBD pre-enabling checks done",
            reports.sbd_check_success("node1")
        )

class SbdConfigDistributionStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Distributing SBD config...",
            reports.sbd_config_distribution_started()
        )

class SbdConfigAcceptedByNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: SBD config saved",
            reports.sbd_config_accepted_by_node("node1")
        )

class UnableToGetSbdConfig(NameBuildTest):
    def test_no_reason(self):
        self.assert_message_from_report(
            "Unable to get SBD configuration from node 'node1'",
            reports.unable_to_get_sbd_config("node1", "")
        )

    def test_all(self):
        self.assert_message_from_report(
            "Unable to get SBD configuration from node 'node2': reason",
            reports.unable_to_get_sbd_config("node2", "reason")
        )

class SbdEnablingStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Enabling SBD service...",
            reports.sbd_enabling_started()
        )

class SbdDisablingStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Disabling SBD service...",
            reports.sbd_disabling_started()
        )

class FileDistributionStarted(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "Sending 'first', 'second'",
            reports.files_distribution_started(["first", "second"])
        )

    def test_build_messages_with_single_node(self):
        self.assert_message_from_report(
            "Sending 'first' to 'node1'",
            reports.files_distribution_started(["first"], ["node1"])
        )

    def test_build_messages_with_nodes(self):
        self.assert_message_from_report(
            "Sending 'first', 'second' to 'node1', 'node2'",
            reports.files_distribution_started(
                ["first", "second"],
                ["node1", "node2"]
            )
        )


class ResourceIsGuestNodeAlready(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "the resource 'some-resource' is already a guest node",
            reports.resource_is_guest_node_already("some-resource")
        )

class FilesDistributionSkipped(NameBuildTest):
    def test_not_live(self):
        self.assert_message_from_report(
            "Distribution of 'file1' to 'nodeA', 'nodeB' was skipped because "
                "the command does not run on a live cluster (e.g. -f was used)."
                " Please, distribute the file(s) manually."
            ,
            reports.files_distribution_skipped(
                "not_live_cib",
                ["file1"],
                ["nodeA", "nodeB"]
            )
        )

    def test_unreachable(self):
        self.assert_message_from_report(
            "Distribution of 'file1', 'file2' to 'nodeA' was skipped because "
                "pcs is unable to connect to the node(s). Please, distribute "
                "the file(s) manually."
            ,
            reports.files_distribution_skipped(
                "unreachable",
                ["file1", "file2"],
                ["nodeA"]
            )
        )

    def test_unknown_reason(self):
        self.assert_message_from_report(
            "Distribution of 'file1', 'file2' to 'nodeA', 'nodeB' was skipped "
                "because some undefined reason. Please, distribute the file(s) "
                "manually."
            ,
            reports.files_distribution_skipped(
                "some undefined reason",
                ["file1", "file2"],
                ["nodeA", "nodeB"]
            )
        )


class OmittingNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Omitting node 'node1'",
            reports.omitting_node("node1")
        )

class MultipleResultFound(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "more than one resource found: 'ID1', 'ID2'",
            reports.multiple_result_found("resource", ["ID2", "ID1"])
        )

    def test_build_messages(self):
        self.assert_message_from_report(
            "more than one resource for 'NODE-NAME' found: 'ID1', 'ID2'",
            reports.multiple_result_found(
                "resource", ["ID2", "ID1"], "NODE-NAME"
            )
        )

class PaceMakerLocalNodeNotFound(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unable to get local node name from pacemaker: reason",
            reports.pacemaker_local_node_name_not_found("reason")
        )


class ServiceStartStarted(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Starting a_service...",
            reports.service_start_started("a_service")
        )

    def test_with_instance(self):
        self.assert_message_from_report(
            "Starting a_service@an_instance...",
            reports.service_start_started("a_service", "an_instance")
        )


class ServiceStartError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to start a_service: a_reason",
            reports.service_start_error("a_service", "a_reason")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: Unable to start a_service: a_reason",
            reports.service_start_error("a_service", "a_reason", "a_node")
        )

    def test_instance(self):
        self.assert_message_from_report(
            "Unable to start a_service@an_instance: a_reason",
            reports.service_start_error(
                "a_service", "a_reason", instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: Unable to start a_service@an_instance: a_reason",
            reports.service_start_error(
                "a_service", "a_reason", "a_node", "an_instance"
            )
        )


class ServiceStartSuccess(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "a_service started",
            reports.service_start_success("a_service")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: a_service started",
            reports.service_start_success(
                "a_service",
                node="a_node"
            )
        )

    def test_instance(self):
        self.assert_message_from_report(
            "a_service@an_instance started",
            reports.service_start_success(
                "a_service",
                instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: a_service@an_instance started",
            reports.service_start_success("a_service", "a_node", "an_instance")
        )


class ServiceStartSkipped(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "not starting a_service: a_reason",
            reports.service_start_skipped("a_service", "a_reason")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: not starting a_service: a_reason",
            reports.service_start_skipped("a_service", "a_reason", "a_node")
        )

    def test_instance(self):
        self.assert_message_from_report(
            "not starting a_service@an_instance: a_reason",
            reports.service_start_skipped(
                "a_service", "a_reason",
                instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: not starting a_service@an_instance: a_reason",
            reports.service_start_skipped(
                "a_service", "a_reason", "a_node", "an_instance"
            )
        )


class ServiceStopStarted(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Stopping a_service...",
            reports.service_stop_started("a_service")
        )

    def test_with_instance(self):
        self.assert_message_from_report(
            "Stopping a_service@an_instance...",
            reports.service_stop_started("a_service", "an_instance")
        )


class ServiceStopError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to stop a_service: a_reason",
            reports.service_stop_error("a_service", "a_reason")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: Unable to stop a_service: a_reason",
            reports.service_stop_error("a_service", "a_reason", "a_node")
        )

    def test_instance(self):
        self.assert_message_from_report(
            "Unable to stop a_service@an_instance: a_reason",
            reports.service_stop_error(
                "a_service", "a_reason",
                instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: Unable to stop a_service@an_instance: a_reason",
            reports.service_stop_error(
                "a_service", "a_reason", "a_node", "an_instance"
            )
        )


class ServiceStopSuccess(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "a_service stopped",
            reports.service_stop_success("a_service")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: a_service stopped",
            reports.service_stop_success("a_service", "a_node")
        )

    def test_instance(self):
        self.assert_message_from_report(
            "a_service@an_instance stopped",
            reports.service_stop_success(
                "a_service",
                instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: a_service@an_instance stopped",
            reports.service_stop_success("a_service", "a_node", "an_instance")
        )


class ServiceKillError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to kill A, B, C: some reason",
            reports.service_kill_error(["B", "A", "C"], "some reason")
        )


class ServiceKillSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "A, B, C killed",
            reports.service_kill_success(["B", "A", "C"])
        )


class ServiceEnableStarted(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Enabling a_service...",
            reports.service_enable_started("a_service")
        )

    def test_with_instance(self):
        self.assert_message_from_report(
            "Enabling a_service@an_instance...",
            reports.service_enable_started("a_service", "an_instance")
        )


class ServiceEnableError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to enable a_service: a_reason",
            reports.service_enable_error("a_service", "a_reason")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: Unable to enable a_service: a_reason",
            reports.service_enable_error(
                "a_service", "a_reason",
                node="a_node"
            )
        )

    def test_instance(self):
        self.assert_message_from_report(
            "Unable to enable a_service@an_instance: a_reason",
            reports.service_enable_error(
                "a_service", "a_reason",
                instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: Unable to enable a_service@an_instance: a_reason",
            reports.service_enable_error(
                "a_service", "a_reason", "a_node", "an_instance"
            )
        )


class ServiceEnableSuccess(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "a_service enabled",
            reports.service_enable_success("a_service")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: a_service enabled",
            reports.service_enable_success(
                "a_service",
                node="a_node")
        )

    def test_instance(self):
        self.assert_message_from_report(
            "a_service@an_instance enabled",
            reports.service_enable_success(
                "a_service",
                instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: a_service@an_instance enabled",
            reports.service_enable_success("a_service", "a_node", "an_instance")
        )


class ServiceEnableSkipped(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "not enabling a_service: a_reason",
            reports.service_enable_skipped("a_service", "a_reason")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: not enabling a_service: a_reason",
            reports.service_enable_skipped(
                "a_service", "a_reason",
                node="a_node"
            )
        )

    def test_instance(self):
        self.assert_message_from_report(
            "not enabling a_service@an_instance: a_reason",
            reports.service_enable_skipped(
                "a_service", "a_reason",
                instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: not enabling a_service@an_instance: a_reason",
            reports.service_enable_skipped(
                "a_service", "a_reason", "a_node", "an_instance"
            )
        )


class ServiceDisableStarted(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Disabling a_service...",
            reports.service_disable_started("a_service")
        )

    def test_with_instance(self):
        self.assert_message_from_report(
            "Disabling a_service@an_instance...",
            reports.service_disable_started("a_service", "an_instance")
        )


class ServiceDisableError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to disable a_service: a_reason",
            reports.service_disable_error("a_service", "a_reason")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: Unable to disable a_service: a_reason",
            reports.service_disable_error("a_service", "a_reason", "a_node")
        )

    def test_instance(self):
        self.assert_message_from_report(
            "Unable to disable a_service@an_instance: a_reason",
            reports.service_disable_error(
                "a_service", "a_reason", instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: Unable to disable a_service@an_instance: a_reason",
            reports.service_disable_error(
                "a_service", "a_reason", "a_node", "an_instance"
            )
        )


class ServiceDisableSuccess(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "a_service disabled",
            reports.service_disable_success("a_service")
        )

    def test_node(self):
        self.assert_message_from_report(
            "a_node: a_service disabled",
            reports.service_disable_success("a_service", "a_node")
        )

    def test_instance(self):
        self.assert_message_from_report(
            "a_service@an_instance disabled",
            reports.service_disable_success(
                "a_service",
                instance="an_instance"
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "a_node: a_service@an_instance disabled",
            reports.service_disable_success(
                "a_service", "a_node", "an_instance"
            )
        )


class CibDiffError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to diff CIB: error message\n<cib-new />",
            reports.cib_diff_error(
                "error message", "<cib-old />", "<cib-new />"
            )
        )


class CibSimulateError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to simulate changes in CIB: error message",
            reports.cib_simulate_error("error message")
        )

    def test_empty_reason(self):
        self.assert_message_from_report(
            "Unable to simulate changes in CIB",
            reports.cib_simulate_error("")
        )


class CibLoadError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unable to get cib",
            reports.cib_load_error("reason")
        )

class CibLoadErrorBadFormat(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "unable to get cib, something wrong",
            reports.cib_load_error_invalid_format("something wrong")
        )

class CibLoadErrorGetNodesForValidation(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Unable to load CIB to get guest and remote nodes from it, "
                "those nodes cannot be considered in configuration validation"
            ),
            reports.cib_load_error_get_nodes_for_validation()
        )

class CibLoadErrorScopeMissing(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unable to get cib, scope 'scope-name' not present in cib",
            reports.cib_load_error_scope_missing("scope-name", "reason")
        )


class ResourceCleanupError(NameBuildTest):

    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to forget failed operations of resources\nsomething wrong",
            reports.resource_cleanup_error("something wrong")
        )

    def test_node(self):
        self.assert_message_from_report(
            "Unable to forget failed operations of resources\nsomething wrong",
            reports.resource_cleanup_error(
                "something wrong",
                node="N1"
            )
        )

    def test_resource(self):
        self.assert_message_from_report(
            "Unable to forget failed operations of resource: R1\n"
                "something wrong"
            ,
            reports.resource_cleanup_error("something wrong", "R1")
        )

    def test_resource_and_node(self):
        self.assert_message_from_report(
            "Unable to forget failed operations of resource: R1\n"
                "something wrong"
            ,
            reports.resource_cleanup_error(
                "something wrong", "R1", "N1"
            )
        )


class ResourceRefreshError(NameBuildTest):

    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to delete history of resources\nsomething wrong",
            reports.resource_refresh_error("something wrong")
        )

    def test_node(self):
        self.assert_message_from_report(
            "Unable to delete history of resources\nsomething wrong",
            reports.resource_refresh_error(
                "something wrong",
                node="N1",
            )
        )

    def test_resource(self):
        self.assert_message_from_report(
            "Unable to delete history of resource: R1\nsomething wrong",
            reports.resource_refresh_error("something wrong", "R1")
        )

    def test_resource_and_node(self):
        self.assert_message_from_report(
            "Unable to delete history of resource: R1\nsomething wrong",
            reports.resource_refresh_error("something wrong", "R1", "N1")
        )


class ResourceRefreshTooTimeConsuming(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Deleting history of all resources on all nodes will execute more "
                "than 25 operations in the cluster, which may negatively "
                "impact the responsiveness of the cluster. Consider specifying "
                "resource and/or node"
            ,
            reports.resource_refresh_too_time_consuming(25)
        )


class IdNotFound(NameBuildTest):
    def test_id(self):
        self.assert_message_from_report(
            "'ID' does not exist",
            reports.id_not_found("ID", [])
        )

    def test_id_and_type(self):
        self.assert_message_from_report(
            "clone/resource 'ID' does not exist",
            reports.id_not_found("ID", ["primitive", "clone"])
        )

    def test_context(self):
        self.assert_message_from_report(
            "there is no 'ID' in the C_TYPE 'C_ID'",
            reports.id_not_found(
                "ID", [],
                context_type="C_TYPE",
                context_id="C_ID"
            )
        )

    def test_type_and_context(self):
        self.assert_message_from_report(
            "there is no ACL user 'ID' in the C_TYPE 'C_ID'",
            reports.id_not_found(
                "ID", ["acl_target"],
                context_type="C_TYPE",
                context_id="C_ID"
            )
        )


class CibPushError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to update cib\nreason\npushed-cib",
            reports.cib_push_error("reason", "pushed-cib")
        )

class CibPushForcedFullDueToCrmFeatureSet(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Replacing the whole CIB instead of applying a diff, a race "
                "condition may happen if the CIB is pushed more than once "
                "simultaneously. To fix this, upgrade pacemaker to get "
                "crm_feature_set at least 3.0.9, current is 3.0.6."
            ),
            reports.cib_push_forced_full_due_to_crm_feature_set(
                "3.0.9", "3.0.6")
        )

class ClusterStateCannotLoad(NameBuildTest):
    def test_without_reason(self):
        self.assert_message_from_report(
            "error running crm_mon, is pacemaker running?",
            reports.cluster_state_cannot_load("")
        )

    def test_with_reason(self):
        self.assert_message_from_report(
            (
                "error running crm_mon, is pacemaker running?"
                "\n  reason\n  spans several lines"
            ),
            reports.cluster_state_cannot_load("reason\nspans several lines")
        )

class ClusterStateInvalidFormat(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "cannot load cluster status, xml does not conform to the schema",
            reports.cluster_state_invalid_format()
        )

class WaitForIdleNotSupported(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "crm_resource does not support --wait, please upgrade pacemaker",
            reports.wait_for_idle_not_supported()
        )

class WaitForIdleTimedOut(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "waiting timeout\n\nreason",
            reports.wait_for_idle_timed_out("reason")
        )

class WaitForIdleError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "reason",
            reports.wait_for_idle_error("reason")
        )

class WaitForIdleNotLiveCluster(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Cannot use '-f' together with '--wait'",
            reports.wait_for_idle_not_live_cluster()
        )

class CorosyncConfigAcceptedByNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Succeeded",
            reports.corosync_config_accepted_by_node("node1")
        )


class CorosyncConfigReadError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to read /dev/path: this is reason",
            reports.corosync_config_read_error("/dev/path", "this is reason")
        )

class DuplicateConstraintsExist(NameBuildTest):
    def test_single_constraint_empty_force(self):
        self.assert_message_from_report(
            "duplicate constraint already exists\n"
            "  resourceA with resourceD (score:score) (id:id123)",
            reports.duplicate_constraints_exist(
                "rsc_colocation",
                [
                    {
                        "options":
                            {
                                "id": "id123",
                                "rsc": "resourceA",
                                "with-rsc": "resourceD",
                                "score": "score"
                            }
                    }
                ]
            ),
            force_text=""
        )

    def test_single_constraint_force(self):
        self.assert_message_from_report(
            "duplicate constraint already exists force text\n"
            "  resourceA with resourceD (score:score) (id:id123)",
            reports.duplicate_constraints_exist(
                "rsc_colocation",
                [
                    {
                        "options":
                            {
                                "id": "id123",
                                "rsc": "resourceA",
                                "with-rsc": "resourceD",
                                "score": "score"
                            }
                    }
                ]
            ),
            force_text=" force text"
        )

    def test_multiple_constraints_force(self):
        self.assert_message_from_report(
            (
                "duplicate constraint already exists force text\n"
                "  rsc_another rsc=resourceA (id:id123)\n"
                "  rsc_another rsc=resourceB (id:id321)"
            ),
            reports.duplicate_constraints_exist(
                "rsc_another",
                [
                    {
                        "options": {"id": "id123", "rsc": "resourceA"}
                    },
                    {
                        "options": {"id": "id321", "rsc": "resourceB"}
                    }
                ]
            ),
            force_text=" force text"
        )

class CannotGroupResourceAdjacentResourceForNewGroup(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Group 'G' does not exist and therefore does not contain 'AR' "
                "resource to put resources next to"
            ),
            reports.cannot_group_resource_adjacent_resource_for_new_group(
                "AR", "G"
            )
        )

class CannotGroupResourceAdjacentResourceNotInGroup(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "There is no resource 'AR' in the group 'G', cannot put "
                "resources next to it in the group"
            ),
            reports.cannot_group_resource_adjacent_resource_not_in_group(
                "AR", "G"
            )
        )

class CannotGroupResourceAlreadyInTheGroup(NameBuildTest):
    def test_single_resource(self):
        self.assert_message_from_report(
            "'R' already exists in 'G'",
            reports.cannot_group_resource_already_in_the_group(["R"], "G")
        )

    def test_several_resources(self):
        self.assert_message_from_report(
            "'A', 'B' already exist in 'G'",
            reports.cannot_group_resource_already_in_the_group(["B", "A"], "G")
        )

class CannotGroupResourceMoreThanOnce(NameBuildTest):
    def test_single_resource(self):
        self.assert_message_from_report(
            "Resources specified more than once: 'X'",
            reports.cannot_group_resource_more_than_once(["X"])
        )

    def test_multiple_resources(self):
        self.assert_message_from_report(
            "Resources specified more than once: 'A', 'B'",
            reports.cannot_group_resource_more_than_once(["B", "A"])
        )

class CannotGroupResourceNextToItself(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Cannot put resource 'R' next to itself",
            reports.cannot_group_resource_next_to_itself("R")
        )

class CannotGroupResourceNoResources(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "No resources to add",
            reports.cannot_group_resource_no_resources()
        )

class CannotGroupResourceWrongType(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "'R' is a clone resource, clone resources cannot be put into "
                "a group"
            ),
            reports.cannot_group_resource_wrong_type("R", "master")
        )

class QdeviceAlreadyDefined(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "quorum device is already defined",
            reports.qdevice_already_defined()
        )

class QdeviceNotDefined(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "no quorum device is defined in this cluster",
            reports.qdevice_not_defined()
        )

class QdeviceRemoveOrClusterStopNeeded(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "You need to stop the cluster or remove qdevice from "
                "the cluster to continue"
            ),
            reports.qdevice_remove_or_cluster_stop_needed()
        )

class QdeviceClientReloadStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Reloading qdevice configuration on nodes...",
            reports.qdevice_client_reload_started()
        )

class QdeviceAlreadyInitialized(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' has been already initialized",
            reports.qdevice_already_initialized("model")
        )

class QdeviceNotInitialized(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' has not been initialized yet",
            reports.qdevice_not_initialized("model")
        )

class QdeviceInitializationSuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' initialized",
            reports.qdevice_initialization_success("model")
        )

class QdeviceInitializationError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to initialize quorum device 'model': reason",
            reports.qdevice_initialization_error("model", "reason")
        )

class QdeviceCertificateDistributionStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Setting up qdevice certificates on nodes...",
            reports.qdevice_certificate_distribution_started()
        )

class QdeviceCertificateAcceptedByNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Succeeded",
            reports.qdevice_certificate_accepted_by_node("node1")
        )

class QdeviceCertificateRemovalStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Removing qdevice certificates from nodes...",
            reports.qdevice_certificate_removal_started()
        )

class QdeviceCertificateRemovedFromNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node2: Succeeded",
            reports.qdevice_certificate_removed_from_node("node2")
        )

class QdeviceCertificateImportError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to import quorum device certificate: reason",
            reports.qdevice_certificate_import_error("reason")
        )

class QdeviceCertificateSignError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to sign quorum device certificate: reason",
            reports.qdevice_certificate_sign_error("reason")
        )

class QdeviceDestroySuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' configuration files removed",
            reports.qdevice_destroy_success("model")
        )

class QdeviceDestroyError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to destroy quorum device 'model': reason",
            reports.qdevice_destroy_error("model", "reason")
        )

class QdeviceNotRunning(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' is not running",
            reports.qdevice_not_running("model")
        )

class QdeviceGetStatusError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to get status of quorum device 'model': reason",
            reports.qdevice_get_status_error("model", "reason")
        )

class QdeviceUsedByClusters(NameBuildTest):
    def test_single_cluster(self):
        self.assert_message_from_report(
            "Quorum device is currently being used by cluster(s): c1",
            reports.qdevice_used_by_clusters(["c1"])
        )

    def test_multiple_clusters(self):
        self.assert_message_from_report(
            "Quorum device is currently being used by cluster(s): c1, c2",
            reports.qdevice_used_by_clusters(["c1", "c2"])
        )

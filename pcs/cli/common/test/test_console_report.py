# pylint: disable=too-many-lines

from unittest import TestCase

from pcs.cli.common.console_report import(
    indent,
    CODE_TO_MESSAGE_BUILDER_MAP,
    format_optional,
)
from pcs.common import report_codes as codes
from pcs.common.fencing_topology import (
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
    TARGET_TYPE_ATTRIBUTE,
)
from pcs.lib import reports
from pcs.lib.errors import ReportItem

class IndentTest(TestCase):
    def test_indent_list_of_lines(self):
        self.assertEqual(
            indent([
                "first",
                "second"
            ]),
            [
                "  first",
                "  second"
            ]
        )

class NameBuildTest(TestCase):
    """
    Mixin for the testing of message building.
    """
    code = None

    def assert_message_from_info(self, message, info=None):
        info = info if info else {}
        build = CODE_TO_MESSAGE_BUILDER_MAP[self.code]
        self.assertEqual(
            message,
            build(info) if callable(build) else build
        )

    def assert_message_from_report(self, message, report):
        if not isinstance(report, ReportItem):
            raise AssertionError("report is not instance of ReportItem")
        self.assert_message_from_info(message, report.info)


class BuildInvalidOptionsMessageTest(NameBuildTest):
    code = codes.INVALID_OPTIONS
    def test_build_message_with_type(self):
        self.assert_message_from_info(
            "invalid TYPE option 'NAME', allowed options are: FIRST, SECOND",
            {
                "option_names": ["NAME"],
                "option_type": "TYPE",
                "allowed": ["SECOND", "FIRST"],
                "allowed_patterns": [],
            }
        )

    def test_build_message_without_type(self):
        self.assert_message_from_info(
            "invalid option 'NAME', allowed options are: FIRST, SECOND",
            {
                "option_names": ["NAME"],
                "option_type": "",
                "allowed": ["FIRST", "SECOND"],
                "allowed_patterns": [],
            }
        )

    def test_build_message_with_multiple_names(self):
        self.assert_message_from_info(
            "invalid options: 'ANOTHER', 'NAME', allowed option is FIRST",
            {
                "option_names": ["NAME", "ANOTHER"],
                "option_type": "",
                "allowed": ["FIRST"],
                "allowed_patterns": [],
            }
        )

    def test_pattern(self):
        self.assert_message_from_info(
            (
                "invalid option 'NAME', allowed are options matching patterns: "
                "exec_<name>"
            ),
            {
                "option_names": ["NAME"],
                "option_type": "",
                "allowed": [],
                "allowed_patterns": ["exec_<name>"],
            }
        )

    def test_allowed_and_patterns(self):
        self.assert_message_from_info(
            (
                "invalid option 'NAME', allowed option is FIRST and options "
                "matching patterns: exec_<name>"
            ),
            {
                "option_names": ["NAME"],
                "option_type": "",
                "allowed": ["FIRST"],
                "allowed_patterns": ["exec_<name>"],
            }
        )

    def test_no_allowed_options(self):
        self.assert_message_from_info(
            "invalid options: 'ANOTHER', 'NAME', there are no options allowed",
            {
                "option_names": ["NAME", "ANOTHER"],
                "option_type": "",
                "allowed": [],
                "allowed_patterns": [],
            }
        )


class InvalidUserdefinedOptions(NameBuildTest):
    code = codes.INVALID_USERDEFINED_OPTIONS

    def test_without_type(self):
        self.assert_message_from_info(
            (
                "invalid option 'exec_NAME', "
                "exec_NAME cannot contain . and whitespace characters"
            ),
            {
                "option_names": ["exec_NAME"],
                "option_type": "",
                "allowed_description":
                    "exec_NAME cannot contain . and whitespace characters"
                ,
            }
        )

    def test_with_type(self):
        self.assert_message_from_info(
            (
                "invalid heuristics option 'exec_NAME', "
                "exec_NAME cannot contain . and whitespace characters"
            ),
            {
                "option_names": ["exec_NAME"],
                "option_type": "heuristics",
                "allowed_description":
                    "exec_NAME cannot contain . and whitespace characters"
                ,
            }
        )

    def test_more_options(self):
        self.assert_message_from_info(
            "invalid TYPE options: 'ANOTHER', 'NAME', DESC",
            {
                "option_names": ["NAME", "ANOTHER"],
                "option_type": "TYPE",
                "allowed_description": "DESC",
            }
        )


class RequiredOptionIsMissing(NameBuildTest):
    code = codes.REQUIRED_OPTION_IS_MISSING
    def test_build_message_with_type(self):
        self.assert_message_from_info(
            "required TYPE option 'NAME' is missing",
            {
                "option_names": ["NAME"],
                "option_type": "TYPE",
            }
        )

    def test_build_message_without_type(self):
        self.assert_message_from_info(
            "required option 'NAME' is missing",
            {
                "option_names": ["NAME"],
                "option_type": "",
            }
        )

    def test_build_message_with_multiple_names(self):
        self.assert_message_from_info(
            "required options 'ANOTHER', 'NAME' are missing",
            {
                "option_names": ["NAME", "ANOTHER"],
                "option_type": "",
            }
        )

class BuildInvalidOptionValueMessageTest(NameBuildTest):
    code = codes.INVALID_OPTION_VALUE
    def test_build_message_with_multiple_allowed_values(self):
        self.assert_message_from_info(
            "'VALUE' is not a valid NAME value, use FIRST, SECOND",
            {
                "option_name": "NAME",
                "option_value": "VALUE",
                "allowed_values": sorted(["FIRST", "SECOND"]),
            }
        )

    def test_build_message_with_hint(self):
        self.assert_message_from_info(
            "'VALUE' is not a valid NAME value, use some hint",
            {
                "option_name": "NAME",
                "option_value": "VALUE",
                "allowed_values": "some hint",
            }
        )

class BuildServiceStartErrorTest(NameBuildTest):
    code = codes.SERVICE_START_ERROR
    def test_build_message_with_instance_and_node(self):
        self.assert_message_from_info(
            "NODE: Unable to start SERVICE@INSTANCE: REASON",
            {
                "service": "SERVICE",
                "reason": "REASON",
                "node": "NODE",
                "instance": "INSTANCE",
            }
        )
    def test_build_message_with_instance_only(self):
        self.assert_message_from_info(
            "Unable to start SERVICE@INSTANCE: REASON",
            {
                "service": "SERVICE",
                "reason": "REASON",
                "node": "",
                "instance": "INSTANCE",
            }
        )

    def test_build_message_with_node_only(self):
        self.assert_message_from_info(
            "NODE: Unable to start SERVICE: REASON",
            {
                "service": "SERVICE",
                "reason": "REASON",
                "node": "NODE",
                "instance": "",
            }
        )

    def test_build_message_without_node_and_instance(self):
        self.assert_message_from_info(
            "Unable to start SERVICE: REASON",
            {
                "service": "SERVICE",
                "reason": "REASON",
                "node": "",
                "instance": "",
            }
        )

class InvalidCibContent(NameBuildTest):
    code = codes.INVALID_CIB_CONTENT
    def test_build_message(self):
        report = "report\nlines"
        self.assert_message_from_info(
            "invalid cib: \n{0}".format(report),
            {
                "report": report,
            }
        )

class BuildInvalidIdTest(NameBuildTest):
    code = codes.INVALID_ID
    def test_build_message_with_first_char_invalid(self):
        self.assert_message_from_info(
            (
                "invalid ID_DESCRIPTION 'ID', 'INVALID_CHARACTER' is not a"
                " valid first character for a ID_DESCRIPTION"
            ),
            {
                "id_description": "ID_DESCRIPTION",
                "id": "ID",
                "invalid_character": "INVALID_CHARACTER",
                "is_first_char": True,
            }
        )
    def test_build_message_with_non_first_char_invalid(self):
        self.assert_message_from_info(
            (
                "invalid ID_DESCRIPTION 'ID', 'INVALID_CHARACTER' is not a"
                " valid character for a ID_DESCRIPTION"
            ),
            {
                "id_description": "ID_DESCRIPTION",
                "id": "ID",
                "invalid_character": "INVALID_CHARACTER",
                "is_first_char": False,
            }
        )

class BuildRunExternalStartedTest(NameBuildTest):
    code = codes.RUN_EXTERNAL_PROCESS_STARTED

    def test_build_message_minimal(self):
        self.assert_message_from_info(
            "Running: COMMAND\nEnvironment:\n",
            {
                "command": "COMMAND",
                "stdin": "",
                "environment": dict(),
            }
        )

    def test_build_message_with_stdin(self):
        self.assert_message_from_info(
            (
                "Running: COMMAND\nEnvironment:\n"
                "--Debug Input Start--\n"
                "STDIN\n"
                "--Debug Input End--\n"
            ),
            {
                "command": "COMMAND",
                "stdin": "STDIN",
                "environment": dict(),
            }
        )

    def test_build_message_with_env(self):
        self.assert_message_from_info(
            (
                "Running: COMMAND\nEnvironment:\n"
                "  env_a=A\n"
                "  env_b=B\n"
            ),
            {
                "command": "COMMAND",
                "stdin": "",
                "environment": {"env_a": "A", "env_b": "B",},
            }
        )

    def test_build_message_maximal(self):
        self.assert_message_from_info(
            (
                "Running: COMMAND\nEnvironment:\n"
                "  env_a=A\n"
                "  env_b=B\n"
                "--Debug Input Start--\n"
                "STDIN\n"
                "--Debug Input End--\n"
            ),
            {
                "command": "COMMAND",
                "stdin": "STDIN",
                "environment": {"env_a": "A", "env_b": "B",},
            }
        )

    def test_insidious_environment(self):
        self.assert_message_from_info(
            (
                "Running: COMMAND\nEnvironment:\n"
                "  test=a:{green},b:{red}\n"
                "--Debug Input Start--\n"
                "STDIN\n"
                "--Debug Input End--\n"
            ),
            {
                "command": "COMMAND",
                "stdin": "STDIN",
                "environment": {"test": "a:{green},b:{red}",},
            }
        )


class BuildNodeCommunicationStartedTest(NameBuildTest):
    code = codes.NODE_COMMUNICATION_STARTED

    def test_build_message_with_data(self):
        self.assert_message_from_info(
            (
                "Sending HTTP Request to: TARGET\n"
                "--Debug Input Start--\n"
                "DATA\n"
                "--Debug Input End--\n"
            ),
            {
                "target": "TARGET",
                "data": "DATA",
            }
        )

    def test_build_message_without_data(self):
        self.assert_message_from_info(
            "Sending HTTP Request to: TARGET\n",
            {
                "target": "TARGET",
                "data": "",
            }
        )


class NodeCommunicationErrorTimedOut(NameBuildTest):
    code = codes.NODE_COMMUNICATION_ERROR_TIMED_OUT
    def test_success(self):
        self.assert_message_from_info(
            (
                "node-1: Connection timeout, try setting higher timeout in "
                "--request-timeout option (Connection timed out after 60049 "
                "milliseconds)"
            ),
            {
                "node": "node-1",
                "command": "/remote/command",
                "reason": "Connection timed out after 60049 milliseconds",
            }
        )


class FormatOptionalTest(TestCase):
    def test_info_key_is_falsy(self):
        self.assertEqual("", format_optional("", "{0}: "))

    def test_info_key_is_not_falsy(self):
        self.assertEqual("A: ", format_optional("A", "{0}: "))

    def test_default_value(self):
        self.assertEqual("DEFAULT", format_optional("", "{0}: ", "DEFAULT"))


class AgentNameGuessedTest(NameBuildTest):
    code = codes.AGENT_NAME_GUESSED
    def test_build_message_with_data(self):
        self.assert_message_from_info(
            "Assumed agent name 'ocf:heratbeat:Delay' (deduced from 'Delay')",
            {
                "entered_name": "Delay",
                "guessed_name": "ocf:heratbeat:Delay",
            }
        )

class InvalidResourceAgentNameTest(NameBuildTest):
    code = codes.INVALID_RESOURCE_AGENT_NAME
    def test_build_message_with_data(self):
        self.assert_message_from_info(
            "Invalid resource agent name ':name'."
                " Use standard:provider:type when standard is 'ocf' or"
                " standard:type otherwise. List of standards and providers can"
                " be obtained by using commands 'pcs resource standards' and"
                " 'pcs resource providers'"
            ,
            {
                "name": ":name",
            }
        )

class InvalidiStonithAgentNameTest(NameBuildTest):
    code = codes.INVALID_STONITH_AGENT_NAME
    def test_build_message_with_data(self):
        self.assert_message_from_info(
            "Invalid stonith agent name 'fence:name'. List of agents can be"
                " obtained by using command 'pcs stonith list'. Do not use the"
                " 'stonith:' prefix. Agent name cannot contain the ':'"
                " character."
            ,
            {
                "name": "fence:name",
            }
        )

class InvalidOptionType(NameBuildTest):
    code = codes.INVALID_OPTION_TYPE
    def test_allowed_string(self):
        self.assert_message_from_info(
            "specified option name is not valid, use allowed types",
            {
                "option_name": "option name",
                "allowed_types": "allowed types",
            }
        )

    def test_allowed_list(self):
        self.assert_message_from_info(
            "specified option name is not valid, use allowed, types",
            {
                "option_name": "option name",
                "allowed_types": ["allowed", "types"],
            }
        )


class DeprecatedOption(NameBuildTest):
    code = codes.DEPRECATED_OPTION

    def test_no_desc_hint_array(self):
        self.assert_message_from_info(
            "option 'option name' is deprecated and should not be used,"
                " use new_a, new_b instead"
            ,
            {
                "option_name": "option name",
                "option_type": "",
                "replaced_by": ["new_b", "new_a"],
            }
        )

    def test_desc_hint_string(self):
        self.assert_message_from_info(
            "option type option 'option name' is deprecated and should not be"
                " used, use new option instead"
            ,
            {
                "option_name": "option name",
                "option_type": "option type",
                "replaced_by": "new option",
            }
        )


class StonithResourcesDoNotExist(NameBuildTest):
    code = codes.STONITH_RESOURCES_DO_NOT_EXIST
    def test_success(self):
        self.assert_message_from_info(
            "Stonith resource(s) 'device1', 'device2' do not exist",
            {
                "stonith_ids": ["device1", "device2"],
            }
        )

class FencingLevelAlreadyExists(NameBuildTest):
    code = codes.CIB_FENCING_LEVEL_ALREADY_EXISTS
    def test_target_node(self):
        self.assert_message_from_info(
            "Fencing level for 'nodeA' at level '1' with device(s) "
                "'device1,device2' already exists",
            {
                "level": "1",
                "target_type": TARGET_TYPE_NODE,
                "target_value": "nodeA",
                "devices": ["device1", "device2"],
            }
        )

    def test_target_pattern(self):
        self.assert_message_from_info(
            "Fencing level for 'node-\\d+' at level '1' with device(s) "
                "'device1,device2' already exists",
            {
                "level": "1",
                "target_type": TARGET_TYPE_REGEXP,
                "target_value": "node-\\d+",
                "devices": ["device1", "device2"],
            }
        )

    def test_target_attribute(self):
        self.assert_message_from_info(
            "Fencing level for 'name=value' at level '1' with device(s) "
                "'device1,device2' already exists",
            {
                "level": "1",
                "target_type": TARGET_TYPE_ATTRIBUTE,
                "target_value": ("name", "value"),
                "devices": ["device1", "device2"],
            }
        )

class FencingLevelDoesNotExist(NameBuildTest):
    code = codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST
    def test_full_info(self):
        self.assert_message_from_info(
            "Fencing level for 'nodeA' at level '1' with device(s) "
                "'device1,device2' does not exist",
            {
                "level": "1",
                "target_type": TARGET_TYPE_NODE,
                "target_value": "nodeA",
                "devices": ["device1", "device2"],
            }
        )

    def test_only_level(self):
        self.assert_message_from_info(
            "Fencing level at level '1' does not exist",
            {
                "level": "1",
                "target_type": None,
                "target_value": None,
                "devices": None,
            }
        )

    def test_only_target(self):
        self.assert_message_from_info(
            "Fencing level for 'name=value' does not exist",
            {
                "level": None,
                "target_type": TARGET_TYPE_ATTRIBUTE,
                "target_value": ("name", "value"),
                "devices": None,
            }
        )

    def test_only_devices(self):
        self.assert_message_from_info(
            "Fencing level with device(s) 'device1,device2' does not exist",
            {
                "level": None,
                "target_type": None,
                "target_value": None,
                "devices": ["device1", "device2"],
            }
        )

    def test_no_info(self):
        self.assert_message_from_info(
            "Fencing level does not exist",
            {
                "level": None,
                "target_type": None,
                "target_value": None,
                "devices": None,
            }
        )


class ResourceBundleAlreadyContainsAResource(NameBuildTest):
    code = codes.RESOURCE_BUNDLE_ALREADY_CONTAINS_A_RESOURCE
    def test_build_message_with_data(self):
        self.assert_message_from_info(
            (
                "bundle 'test_bundle' already contains resource "
                "'test_resource', a bundle may contain at most one resource"
            ),
            {
                "resource_id": "test_resource",
                "bundle_id": "test_bundle",
            }
        )


class ResourceOperationIntevalDuplicationTest(NameBuildTest):
    code = codes.RESOURCE_OPERATION_INTERVAL_DUPLICATION
    def test_build_message_with_data(self):
        self.assert_message_from_info(
            "multiple specification of the same operation with the same"
                " interval:"
                "\nmonitor with intervals 3600s, 60m, 1h"
                "\nmonitor with intervals 60s, 1m"
            ,
            {
                "duplications":  {
                    "monitor": [
                        ["3600s", "60m", "1h"],
                        ["60s", "1m"],
                    ],
                },
            }
        )

class ResourceOperationIntevalAdaptedTest(NameBuildTest):
    code = codes.RESOURCE_OPERATION_INTERVAL_ADAPTED
    def test_build_message_with_data(self):
        self.assert_message_from_info(
            "changing a monitor operation interval from 10 to 11 to make the"
                " operation unique"
            ,
            {
                "operation_name": "monitor",
                "original_interval": "10",
                "adapted_interval": "11",
            }
        )

class IdBelongsToUnexpectedType(NameBuildTest):
    code = codes.ID_BELONGS_TO_UNEXPECTED_TYPE
    def test_build_message_with_data(self):
        self.assert_message_from_info(
            "'ID' is not a clone/resource",
            {
                "id": "ID",
                "expected_types": ["primitive", "clone"],
                "current_type": "op",
            }
        )

    def test_build_message_with_transformation_and_article(self):
        self.assert_message_from_info(
            "'ID' is not an ACL group/ACL user",
            {
                "id": "ID",
                "expected_types": ["acl_target", "acl_group"],
                "current_type": "op",
            }
        )

class ResourceRunOnNodes(NameBuildTest):
    code = codes.RESOURCE_RUNNING_ON_NODES
    def test_one_node(self):
        self.assert_message_from_info(
            "resource 'R' is running on node 'node1'",
            {
                "resource_id": "R",
                "roles_with_nodes": {"Started": ["node1"]},
            }
        )
    def test_multiple_nodes(self):
        self.assert_message_from_info(
            "resource 'R' is running on nodes 'node1', 'node2'",
            {
                "resource_id": "R",
                "roles_with_nodes": {"Started": ["node1", "node2"]},
            }
        )
    def test_multiple_role_multiple_nodes(self):
        self.assert_message_from_info(
            "resource 'R' is master on node 'node3'"
            "; running on nodes 'node1', 'node2'"
            ,
            {
                "resource_id": "R",
                "roles_with_nodes": {
                    "Started": ["node1", "node2"],
                    "Master": ["node3"],
                },
            }
        )

class ResourceDoesNotRun(NameBuildTest):
    code = codes.RESOURCE_DOES_NOT_RUN
    def test_build_message(self):
        self.assert_message_from_info(
            "resource 'R' is not running on any node",
            {
                "resource_id": "R",
            }
        )

class MutuallyExclusiveOptions(NameBuildTest):
    code = codes.MUTUALLY_EXCLUSIVE_OPTIONS
    def test_build_message(self):
        self.assert_message_from_info(
            "Only one of some options 'a' and 'b' can be used",
            {
                "option_type": "some",
                "option_names": ["a", "b"],
            }
        )

class ResourceIsUnmanaged(NameBuildTest):
    code = codes.RESOURCE_IS_UNMANAGED
    def test_build_message(self):
        self.assert_message_from_info(
            "'R' is unmanaged",
            {
                "resource_id": "R",
            }
        )

class ResourceManagedNoMonitorEnabled(NameBuildTest):
    code = codes.RESOURCE_MANAGED_NO_MONITOR_ENABLED
    def test_build_message(self):
        self.assert_message_from_info(
            "Resource 'R' has no enabled monitor operations."
                " Re-run with '--monitor' to enable them."
            ,
            {
                "resource_id": "R",
            }
        )


class SbdDeviceInitializationStarted(NameBuildTest):
    code = codes.SBD_DEVICE_INITIALIZATION_STARTED
    def test_build_message(self):
        self.assert_message_from_info(
            "Initializing device(s) /dev1, /dev2, /dev3...",
            {
                "device_list": ["/dev1", "/dev2", "/dev3"],
            }
        )


class SbdDeviceInitializationError(NameBuildTest):
    code = codes.SBD_DEVICE_INITIALIZATION_ERROR
    def test_build_message(self):
        self.assert_message_from_info(
            "Initialization of device(s) failed: this is reason",
            {
                "reason": "this is reason"
            }
        )


class SbdDeviceListError(NameBuildTest):
    code = codes.SBD_DEVICE_LIST_ERROR
    def test_build_message(self):
        self.assert_message_from_info(
            "Unable to get list of messages from device '/dev': this is reason",
            {
                "device": "/dev",
                "reason": "this is reason",
            }
        )


class SbdDeviceMessageError(NameBuildTest):
    code = codes.SBD_DEVICE_MESSAGE_ERROR
    def test_build_message(self):
        self.assert_message_from_info(
            "Unable to set message 'test' for node 'node1' on device '/dev1'",
            {
                "message": "test",
                "node": "node1",
                "device": "/dev1",
            }
        )


class SbdDeviceDumpError(NameBuildTest):
    code = codes.SBD_DEVICE_DUMP_ERROR
    def test_build_message(self):
        self.assert_message_from_info(
            "Unable to get SBD headers from device '/dev1': this is reason",
            {
                "device": "/dev1",
                "reason": "this is reason",
            }
        )


class SbdDevcePathNotAbsolute(NameBuildTest):
    code = codes.SBD_DEVICE_PATH_NOT_ABSOLUTE
    def test_build_message(self):
        self.assert_message_from_info(
            "Device path '/dev' on node 'node1' is not absolute",
            {
                "device": "/dev",
                "node": "node1",
            }
        )

    def test_build_message_without_node(self):
        self.assert_message_from_info(
            "Device path '/dev' is not absolute",
            {
                "device": "/dev",
                "node": None,
            }
        )


class SbdDeviceDoesNotExist(NameBuildTest):
    code = codes.SBD_DEVICE_DOES_NOT_EXIST
    def test_build_message(self):
        self.assert_message_from_info(
            "node1: device '/dev' not found",
            {
                "node": "node1",
                "device": "/dev",
            }
        )


class SbdDeviceISNotBlockDevice(NameBuildTest):
    code = codes.SBD_DEVICE_IS_NOT_BLOCK_DEVICE
    def test_build_message(self):
        self.assert_message_from_info(
            "node1: device '/dev' is not a block device",
            {
                "node": "node1",
                "device": "/dev",
            }
        )

class SbdNotUsedCannotSetSbdOptions(NameBuildTest):
    code = codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS
    def test_success(self):
        self.assert_message_from_info(
            "Cluster is not configured to use SBD, cannot specify SBD option(s)"
            " 'device', 'watchdog' for node 'node1'"
            ,
            {
                "node": "node1",
                "options": ["device", "watchdog"],
            }
        )

class SbdWithDevicesNotUsedCannotSetDevice(NameBuildTest):
    code = codes.SBD_WITH_DEVICES_NOT_USED_CANNOT_SET_DEVICE
    def test_success(self):
        self.assert_message_from_info(
            "Cluster is not configured to use SBD with shared storage, cannot "
                "specify SBD devices for node 'node1'"
            ,
            {
                "node": "node1",
            }
        )

class SbdNoDEviceForNode(NameBuildTest):
    code = codes.SBD_NO_DEVICE_FOR_NODE
    def test_not_enabled(self):
        self.assert_message_from_info(
            "No SBD device specified for node 'node1'",
            {
                "node": "node1",
                "sbd_enabled_in_cluster": False,
            }
        )

    def test_enabled(self):
        self.assert_message_from_info(
            "Cluster uses SBD with shared storage so SBD devices must be "
                "specified for all nodes, no device specified for node 'node1'"
            ,
            {
                "node": "node1",
                "sbd_enabled_in_cluster": True,
            }
        )


class SbdTooManyDevicesForNode(NameBuildTest):
    code = codes.SBD_TOO_MANY_DEVICES_FOR_NODE
    def test_build_messages(self):
        self.assert_message_from_info(
            "At most 3 SBD devices can be specified for a node, '/dev1', "
                "'/dev2', '/dev3' specified for node 'node1'"
            ,
            {
                "max_devices": 3,
                "node": "node1",
                "device_list": ["/dev1", "/dev2", "/dev3"]
            }
        )

class RequiredOptionOfAlternativesIsMissing(NameBuildTest):
    code = codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING
    def test_without_type(self):
        self.assert_message_from_info(
            "option 'aAa' or 'bBb' or 'cCc' has to be specified",
            {
                "option_names": ["aAa", "bBb", "cCc"],
            }
        )

    def test_with_type(self):
        self.assert_message_from_info(
            "test option 'aAa' or 'bBb' or 'cCc' has to be specified",
            {
                "option_type": "test",
                "option_names": ["aAa", "bBb", "cCc"],
            }
        )


class PrerequisiteOptionMustNotBeSet(NameBuildTest):
    code = codes.PREREQUISITE_OPTION_MUST_NOT_BE_SET
    def test_without_type(self):
        self.assert_message_from_report(
            "Cannot set option 'a' because option 'b' is already set",
            reports.prerequisite_option_must_not_be_set(
                "a", "b",
            )
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "Cannot set some option 'a' because other option 'b' is "
                "already set"
            ,
            reports.prerequisite_option_must_not_be_set(
                "a", "b", option_type="some", prerequisite_type="other",
            )
        )


class PrerequisiteOptionMustBeDisabled(NameBuildTest):
    code = codes.PREREQUISITE_OPTION_MUST_BE_DISABLED
    def test_without_type(self):
        self.assert_message_from_info(
            "If option 'a' is enabled, option 'b' must be disabled",
            {
                "option_name": "a",
                "prerequisite_name": "b",
            }
        )

    def test_with_type(self):
        self.assert_message_from_info(
            "If some option 'a' is enabled, other option 'b' must be disabled",
            {
                "option_name": "a",
                "option_type": "some",
                "prerequisite_name": "b",
                "prerequisite_type": "other",
            }
        )


class PrerequisiteOptionMustBeEnabledAsWell(NameBuildTest):
    code = codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL
    def test_without_type(self):
        self.assert_message_from_info(
            "If option 'a' is enabled, option 'b' must be enabled as well",
            {
                "option_name": "a",
                "prerequisite_name": "b",
            }
        )

    def test_with_type(self):
        self.assert_message_from_info(
            "If some option 'a' is enabled, "
                "other option 'b' must be enabled as well"
            ,
            {
                "option_name": "a",
                "option_type": "some",
                "prerequisite_name": "b",
                "prerequisite_type": "other",
            }
        )


class PrerequisiteOptionIsMissing(NameBuildTest):
    code = codes.PREREQUISITE_OPTION_IS_MISSING
    def test_without_type(self):
        self.assert_message_from_info(
            "If option 'a' is specified, option 'b' must be specified as well",
            {
                "option_name": "a",
                "prerequisite_name": "b",
            }
        )

    def test_with_type(self):
        self.assert_message_from_info(
            "If some option 'a' is specified, "
                "other option 'b' must be specified as well"
            ,
            {
                "option_name": "a",
                "option_type": "some",
                "prerequisite_name": "b",
                "prerequisite_type": "other",
            }
        )


class FileDistributionStarted(NameBuildTest):
    code = codes.FILES_DISTRIBUTION_STARTED
    def test_build_messages(self):
        self.assert_message_from_report(
            "Sending 'first', 'second'",
            reports.files_distribution_started(["first", "second"])
        )

    def test_build_messages_with_nodes(self):
        self.assert_message_from_report(
            "Sending 'first', 'second' to 'node1', 'node2'",
            reports.files_distribution_started(
                ["first", "second"],
                ["node1", "node2"]
            )
        )


class FileDistributionSucess(NameBuildTest):
    code = codes.FILE_DISTRIBUTION_SUCCESS
    def test_build_messages(self):
        self.assert_message_from_info(
            "node1: successful distribution of the file 'some authfile'",
            {
                "nodes_success_files": None,
                "node": "node1",
                "file_description": "some authfile",
            }
        )

class FileDistributionError(NameBuildTest):
    code = codes.FILE_DISTRIBUTION_ERROR
    def test_build_messages(self):
        self.assert_message_from_info(
            "node1: unable to distribute file 'file1': permission denied",
            {
                "node_file_errors": None,
                "node": "node1",
                "file_description": "file1",
                "reason": "permission denied",
            }
        )


class FileRemoveFromNodesStarted(NameBuildTest):
    code = codes.FILES_REMOVE_FROM_NODES_STARTED
    def test_build_messages(self):
        self.assert_message_from_info(
            "Requesting remove 'first', 'second' from 'node1', 'node2'",
            {
                "file_list": ["first", "second"],
                "node_list": ["node1", "node2"],
            }
        )


class FileRemoveFromNodeSucess(NameBuildTest):
    code = codes.FILE_REMOVE_FROM_NODE_SUCCESS
    def test_build_messages(self):
        self.assert_message_from_info(
            "node1: successful removal of the file 'some authfile'",
            {
                "nodes_success_files": None,
                "node": "node1",
                "file_description": "some authfile",
            }
        )

class FileRemoveFromNodeError(NameBuildTest):
    code = codes.FILE_REMOVE_FROM_NODE_ERROR
    def test_build_messages(self):
        self.assert_message_from_info(
            "node1: unable to remove file 'file1': permission denied",
            {
                "node_file_errors": None,
                "node": "node1",
                "file_description": "file1",
                "reason": "permission denied",
            }
        )


class ServiceCommandsOnNodesStarted(NameBuildTest):
    code = codes.SERVICE_COMMANDS_ON_NODES_STARTED
    def test_build_messages(self):
        self.assert_message_from_report(
            "Requesting 'action1', 'action2'",
            reports.service_commands_on_nodes_started(
                ["action1", "action2"]
            )
        )

    def test_build_messages_with_nodes(self):
        self.assert_message_from_report(
            "Requesting 'action1', 'action2' on 'node1', 'node2'",
            reports.service_commands_on_nodes_started(
                ["action1", "action2"],
                ["node1", "node2"],
            )
        )


class ActionsOnNodesSuccess(NameBuildTest):
    code = codes.SERVICE_COMMAND_ON_NODE_SUCCESS
    def test_build_messages(self):
        self.assert_message_from_info(
            "node1: successful run of 'service enable'",
            {
                "nodes_success_actions": None,
                "node": "node1",
                "service_command_description": "service enable",
            }
        )

class ActionOnNodesError(NameBuildTest):
    code = codes.SERVICE_COMMAND_ON_NODE_ERROR
    def test_build_messages(self):
        self.assert_message_from_info(
            "node1: service command failed: service1 start: permission denied",
            {
                "node_action_errors": None,
                "node": "node1",
                "service_command_description": "service1 start",
                "reason": "permission denied",
            }
        )

class ResourceIsGuestNodeAlready(NameBuildTest):
    code = codes.RESOURCE_IS_GUEST_NODE_ALREADY
    def test_build_messages(self):
        self.assert_message_from_info(
            "the resource 'some-resource' is already a guest node",
            {"resource_id": "some-resource"}
        )

class LiveEnvironmentRequired(NameBuildTest):
    code = codes.LIVE_ENVIRONMENT_REQUIRED
    def test_build_messages(self):
        self.assert_message_from_info(
            "This command does not support '--corosync_conf'",
            {
                "forbidden_options": ["--corosync_conf"]
            }
        )

    def test_build_messages_transformable_codes(self):
        self.assert_message_from_info(
            "This command does not support '--corosync_conf', '-f'",
            {
                "forbidden_options": ["COROSYNC_CONF", "CIB"]
            }
        )

class CorosyncNodeConflictCheckSkipped(NameBuildTest):
    code = codes.COROSYNC_NODE_CONFLICT_CHECK_SKIPPED
    def test_success(self):
        self.assert_message_from_report(
            "Unable to check if there is a conflict with nodes set in corosync "
                "because the command does not run on a live cluster (e.g. -f "
                "was used)"
            ,
            reports.corosync_node_conflict_check_skipped("not_live_cib")
        )


class FilesDistributionSkipped(NameBuildTest):
    code = codes.FILES_DISTRIBUTION_SKIPPED
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


class FilesRemoveFromNodesSkipped(NameBuildTest):
    code = codes.FILES_REMOVE_FROM_NODES_SKIPPED
    def test_not_live(self):
        self.assert_message_from_report(
            "Removing 'file1' from 'nodeA', 'nodeB' was skipped because the "
                "command does not run on a live cluster (e.g. -f was used). "
                "Please, remove the file(s) manually."
            ,
            reports.files_remove_from_nodes_skipped(
                "not_live_cib",
                ["file1"],
                ["nodeA", "nodeB"]
            )
        )

    def test_unreachable(self):
        self.assert_message_from_report(
            "Removing 'file1', 'file2' from 'nodeA' was skipped because pcs is "
                "unable to connect to the node(s). Please, remove the file(s) "
                "manually."
            ,
            reports.files_remove_from_nodes_skipped(
                "unreachable",
                ["file1", "file2"],
                ["nodeA"]
            )
        )

    def test_unknown_reason(self):
        self.assert_message_from_report(
            "Removing 'file1', 'file2' from 'nodeA', 'nodeB' was skipped "
                "because some undefined reason. Please, remove the file(s) "
                "manually."
            ,
            reports.files_remove_from_nodes_skipped(
                "some undefined reason",
                ["file1", "file2"],
                ["nodeA", "nodeB"]
            )
        )

class ServiceCommandsOnNodesSkipped(NameBuildTest):
    code = codes.SERVICE_COMMANDS_ON_NODES_SKIPPED
    def test_not_live(self):
        self.assert_message_from_report(
            "Running action(s) 'pacemaker_remote enable', 'pacemaker_remote "
                "start' on 'nodeA', 'nodeB' was skipped because the command "
                "does not run on a live cluster (e.g. -f was used). Please, "
                "run the action(s) manually."
            ,
            reports.service_commands_on_nodes_skipped(
                "not_live_cib",
                ["pacemaker_remote enable", "pacemaker_remote start"],
                ["nodeA", "nodeB"]
            )
        )

    def test_unreachable(self):
        self.assert_message_from_report(
            "Running action(s) 'pacemaker_remote enable', 'pacemaker_remote "
                "start' on 'nodeA', 'nodeB' was skipped because pcs is unable "
                "to connect to the node(s). Please, run the action(s) manually."
            ,
            reports.service_commands_on_nodes_skipped(
                "unreachable",
                ["pacemaker_remote enable", "pacemaker_remote start"],
                ["nodeA", "nodeB"]
            )
        )

    def test_unknown_reason(self):
        self.assert_message_from_report(
            "Running action(s) 'pacemaker_remote enable', 'pacemaker_remote "
                "start' on 'nodeA', 'nodeB' was skipped because some undefined "
                "reason. Please, run the action(s) manually."
            ,
            reports.service_commands_on_nodes_skipped(
                "some undefined reason",
                ["pacemaker_remote enable", "pacemaker_remote start"],
                ["nodeA", "nodeB"]
            )
        )


class NodeAddressesUnresolvable(NameBuildTest):
    code = codes.NODE_ADDRESSES_UNRESOLVABLE
    def test_one_address(self):
        self.assert_message_from_info(
            "Unable to resolve addresses: 'node1'",
            {
                "address_list": ["node1",],
            }
        )

    def test_more_address(self):
        self.assert_message_from_info(
            "Unable to resolve addresses: 'node1', 'node2', 'node3'",
            {
                "address_list": ["node1", "node2", "node3"],
            }
        )


class NodeNotFound(NameBuildTest):
    code = codes.NODE_NOT_FOUND
    def test_build_messages(self):
        self.assert_message_from_info(
            "Node 'SOME_NODE' does not appear to exist in configuration",
            {
                "node": "SOME_NODE",
                "searched_types": []
            }
        )

    def test_build_messages_with_one_search_types(self):
        self.assert_message_from_info(
            "remote node 'SOME_NODE' does not appear to exist in configuration",
            {
                "node": "SOME_NODE",
                "searched_types": ["remote"]
            }
        )

    def test_build_messages_with_string_search_types(self):
        self.assert_message_from_info(
            "remote node 'SOME_NODE' does not appear to exist in configuration",
            {
                "node": "SOME_NODE",
                "searched_types": "remote"
            }
        )

    def test_build_messages_with_multiple_search_types(self):
        self.assert_message_from_info(
            "nor remote node or guest node 'SOME_NODE' does not appear to exist"
                " in configuration"
            ,
            {
                "node": "SOME_NODE",
                "searched_types": ["remote", "guest"]
            }
        )

class MultipleResultFound(NameBuildTest):
    code = codes.MULTIPLE_RESULTS_FOUND
    def test_build_messages(self):
        self.assert_message_from_info(
            "multiple resource for 'NODE-NAME' found: 'ID1', 'ID2'",
            {
                "result_type": "resource",
                "result_identifier_list": ["ID1", "ID2"],
                "search_description": "NODE-NAME",
            }
        )

class UseCommandNodeAddRemote(NameBuildTest):
    code = codes.USE_COMMAND_NODE_ADD_REMOTE
    def test_build_messages(self):
        self.assert_message_from_info(
            "this command is not sufficient for creating a remote connection,"
                " use 'pcs cluster node add-remote'"
            ,
            {}
        )

class UseCommandNodeAddGuest(NameBuildTest):
    code = codes.USE_COMMAND_NODE_ADD_GUEST
    def test_build_messages(self):
        self.assert_message_from_info(
            "this command is not sufficient for creating a guest node, use "
            "'pcs cluster node add-guest'",
            {}
        )

class UseCommandNodeRemoveGuest(NameBuildTest):
    code = codes.USE_COMMAND_NODE_REMOVE_GUEST
    def test_build_messages(self):
        self.assert_message_from_info(
            "this command is not sufficient for removing a guest node, use "
            "'pcs cluster node remove-guest'",
            {}
        )

class NodeRemoveInPacemakerFailed(NameBuildTest):
    code = codes.NODE_REMOVE_IN_PACEMAKER_FAILED
    def test_without_node(self):
        self.assert_message_from_report(
            "Unable to remove node(s) 'NODE' from pacemaker: reason",
            reports.node_remove_in_pacemaker_failed(
                ["NODE"],
                reason="reason"
            )
        )

    def test_with_node(self):
        self.assert_message_from_report(
            (
                "node-a: Unable to remove node(s) 'NODE1', 'NODE2' from "
                "pacemaker: reason"
            ),
            reports.node_remove_in_pacemaker_failed(
                ["NODE1", "NODE2"],
                node="node-a",
                reason="reason"
            )
        )

class NodeToClearIsStillInCluster(NameBuildTest):
    code = codes.NODE_TO_CLEAR_IS_STILL_IN_CLUSTER
    def test_build_messages(self):
        self.assert_message_from_info(
            "node 'node1' seems to be still in the cluster"
                "; this command should be used only with nodes that have been"
                " removed from the cluster"
            ,
            {
                "node": "node1"
            }
        )


class ServiceStartStarted(NameBuildTest):
    code = codes.SERVICE_START_STARTED
    def test_minimal(self):
        self.assert_message_from_info(
            "Starting a_service...",
            {
                "service": "a_service",
                "instance": None,
            }
        )

    def test_with_instance(self):
        self.assert_message_from_info(
            "Starting a_service@an_instance...",
            {
                "service": "a_service",
                "instance": "an_instance",
            }
        )


class ServiceStartError(NameBuildTest):
    code = codes.SERVICE_START_ERROR
    def test_minimal(self):
        self.assert_message_from_info(
            "Unable to start a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: Unable to start a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "Unable to start a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: Unable to start a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class ServiceStartSuccess(NameBuildTest):
    code = codes.SERVICE_START_SUCCESS
    def test_minimal(self):
        self.assert_message_from_info(
            "a_service started",
            {
                "service": "a_service",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: a_service started",
            {
                "service": "a_service",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "a_service@an_instance started",
            {
                "service": "a_service",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: a_service@an_instance started",
            {
                "service": "a_service",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class ServiceStartSkipped(NameBuildTest):
    code = codes.SERVICE_START_SKIPPED
    def test_minimal(self):
        self.assert_message_from_info(
            "not starting a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: not starting a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "not starting a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: not starting a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class ServiceStopStarted(NameBuildTest):
    code = codes.SERVICE_STOP_STARTED
    def test_minimal(self):
        self.assert_message_from_info(
            "Stopping a_service...",
            {
                "service": "a_service",
                "instance": None,
            }
        )

    def test_with_instance(self):
        self.assert_message_from_info(
            "Stopping a_service@an_instance...",
            {
                "service": "a_service",
                "instance": "an_instance",
            }
        )


class ServiceStopError(NameBuildTest):
    code = codes.SERVICE_STOP_ERROR
    def test_minimal(self):
        self.assert_message_from_info(
            "Unable to stop a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: Unable to stop a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "Unable to stop a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: Unable to stop a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class ServiceStopSuccess(NameBuildTest):
    code = codes.SERVICE_STOP_SUCCESS
    def test_minimal(self):
        self.assert_message_from_info(
            "a_service stopped",
            {
                "service": "a_service",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: a_service stopped",
            {
                "service": "a_service",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "a_service@an_instance stopped",
            {
                "service": "a_service",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: a_service@an_instance stopped",
            {
                "service": "a_service",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class ServiceEnableStarted(NameBuildTest):
    code = codes.SERVICE_ENABLE_STARTED
    def test_minimal(self):
        self.assert_message_from_info(
            "Enabling a_service...",
            {
                "service": "a_service",
                "instance": None,
            }
        )

    def test_with_instance(self):
        self.assert_message_from_info(
            "Enabling a_service@an_instance...",
            {
                "service": "a_service",
                "instance": "an_instance",
            }
        )


class ServiceEnableError(NameBuildTest):
    code = codes.SERVICE_ENABLE_ERROR
    def test_minimal(self):
        self.assert_message_from_info(
            "Unable to enable a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: Unable to enable a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "Unable to enable a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: Unable to enable a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class ServiceEnableSuccess(NameBuildTest):
    code = codes.SERVICE_ENABLE_SUCCESS
    def test_minimal(self):
        self.assert_message_from_info(
            "a_service enabled",
            {
                "service": "a_service",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: a_service enabled",
            {
                "service": "a_service",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "a_service@an_instance enabled",
            {
                "service": "a_service",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: a_service@an_instance enabled",
            {
                "service": "a_service",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class ServiceEnableSkipped(NameBuildTest):
    code = codes.SERVICE_ENABLE_SKIPPED
    def test_minimal(self):
        self.assert_message_from_info(
            "not enabling a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: not enabling a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "not enabling a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: not enabling a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class ServiceDisableStarted(NameBuildTest):
    code = codes.SERVICE_DISABLE_STARTED
    def test_minimal(self):
        self.assert_message_from_info(
            "Disabling a_service...",
            {
                "service": "a_service",
                "instance": None,
            }
        )

    def test_with_instance(self):
        self.assert_message_from_info(
            "Disabling a_service@an_instance...",
            {
                "service": "a_service",
                "instance": "an_instance",
            }
        )


class ServiceDisableError(NameBuildTest):
    code = codes.SERVICE_DISABLE_ERROR
    def test_minimal(self):
        self.assert_message_from_info(
            "Unable to disable a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: Unable to disable a_service: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "Unable to disable a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: Unable to disable a_service@an_instance: a_reason",
            {
                "service": "a_service",
                "reason": "a_reason",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class ServiceDisableSuccess(NameBuildTest):
    code = codes.SERVICE_DISABLE_SUCCESS
    def test_minimal(self):
        self.assert_message_from_info(
            "a_service disabled",
            {
                "service": "a_service",
                "node": None,
                "instance": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "a_node: a_service disabled",
            {
                "service": "a_service",
                "node": "a_node",
                "instance": None,
            }
        )

    def test_instance(self):
        self.assert_message_from_info(
            "a_service@an_instance disabled",
            {
                "service": "a_service",
                "node": None,
                "instance": "an_instance",
            }
        )

    def test_all(self):
        self.assert_message_from_info(
            "a_node: a_service@an_instance disabled",
            {
                "service": "a_service",
                "node": "a_node",
                "instance": "an_instance",
            }
        )


class CibDiffError(NameBuildTest):
    code = codes.CIB_DIFF_ERROR
    def test_success(self):
        self.assert_message_from_info(
            "Unable to diff CIB: error message\n<cib-new />",
            {
                "reason": "error message",
                "cib_old": "<cib-old />",
                "cib_new": "<cib-new />",
            }
        )


class TmpFileWrite(NameBuildTest):
    code = codes.TMP_FILE_WRITE
    def test_success(self):
        self.assert_message_from_info(
            (
                "Writing to a temporary file /tmp/pcs/test.tmp:\n"
                "--Debug Content Start--\n"
                "test file\ncontent\n\n"
                "--Debug Content End--\n"
            ),
            {
                "file_path": "/tmp/pcs/test.tmp",
                "content": "test file\ncontent\n",
            }
        )


class DefaultsCanBeOverriden(NameBuildTest):
    code = codes.DEFAULTS_CAN_BE_OVERRIDEN
    def test_message(self):
        self.assert_message_from_info(
            "Defaults do not apply to resources which override them with their "
            "own defined values"
        )


class CibLoadErrorBadFormat(NameBuildTest):
    code = codes.CIB_LOAD_ERROR_BAD_FORMAT
    def test_message(self):
        self.assert_message_from_info(
            "unable to get cib, something wrong",
            {
                "reason": "something wrong"
            }
        )

class CorosyncAddressIpVersionWrongForLink(NameBuildTest):
    code = codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK
    def test_message(self):
        self.assert_message_from_info(
            "Address '192.168.100.42' cannot be used in link '3' because "
            "the link uses IPv6 addresses",
            {
                "address": "192.168.100.42",
                "expected_address_type": "IPv6",
                "link_number": 3,
            }
        )

class CorosyncBadNodeAddressesCount(NameBuildTest):
    code = codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT
    def test_no_node_info(self):
        self.assert_message_from_info(
            "At least 1 and at most 4 addresses can be specified for a node, "
            "5 addresses specified",
            {
                "actual_count": 5,
                "min_count": 1,
                "max_count": 4,
            }
        )

    def test_node_name(self):
        self.assert_message_from_info(
            "At least 1 and at most 4 addresses can be specified for a node, "
            "5 addresses specified for node 'node1'",
            {
                "actual_count": 5,
                "min_count": 1,
                "max_count": 4,
                "node_name": "node1",
            }
        )

    def test_node_id(self):
        self.assert_message_from_info(
            "At least 1 and at most 4 addresses can be specified for a node, "
            "5 addresses specified for node '2'",
            {
                "actual_count": 5,
                "min_count": 1,
                "max_count": 4,
                "node_index": 2,
            }
        )

    def test_node_name_and_id(self):
        self.assert_message_from_info(
            "At least 1 and at most 4 addresses can be specified for a node, "
            "5 addresses specified for node 'node2'",
            {
                "actual_count": 5,
                "min_count": 1,
                "max_count": 4,
                "node_name": "node2",
                "node_index": 2,
            }
        )

    def test_one_address_allowed(self):
        self.assert_message_from_info(
            "At least 0 and at most 1 address can be specified for a node, "
            "2 addresses specified for node 'node2'",
            {
                "actual_count": 2,
                "min_count": 0,
                "max_count": 1,
                "node_name": "node2",
                "node_index": 2,
            }
        )

    def test_one_address_specified(self):
        self.assert_message_from_info(
            "At least 2 and at most 4 addresses can be specified for a node, "
            "1 address specified for node 'node2'",
            {
                "actual_count": 1,
                "min_count": 2,
                "max_count": 4,
                "node_name": "node2",
                "node_index": 2,
            }
        )

    def test_exactly_one_address_allowed(self):
        self.assert_message_from_info(
            "1 address can be specified for a node, "
            "2 addresses specified for node 'node2'",
            {
                "actual_count": 2,
                "min_count": 1,
                "max_count": 1,
                "node_name": "node2",
                "node_index": 2,
            }
        )

    def test_exactly_two_addresses_allowed(self):
        self.assert_message_from_info(
            "2 addresses can be specified for a node, "
            "1 address specified for node 'node2'",
            {
                "actual_count": 1,
                "min_count": 2,
                "max_count": 2,
                "node_name": "node2",
                "node_index": 2,
            }
        )


class CorosyncIpVersionMismatchInLinks(NameBuildTest):
    code = codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS
    def test_message(self):
        self.assert_message_from_info(
            "Using both IPv4 and IPv6 in one link is not allowed; please, use "
                "either IPv4 or IPv6 in links '0', '3', '4'"
            ,
            {
                "link_numbers": [3, 0, 4]
            }
        )


class CorosyncNodeAddressCountMismatch(NameBuildTest):
    code = codes.COROSYNC_NODE_ADDRESS_COUNT_MISMATCH
    def test_message(self):
        self.assert_message_from_info(
            "All nodes must have the same number of addresses; "
                "nodes 'node3', 'node4', 'node6' have 1 address; "
                "nodes 'node2', 'node5' have 3 addresses; "
                "node 'node1' has 2 addresses"
            ,
            {
                "node_addr_count": {
                    "node1": 2,
                    "node2": 3,
                    "node3": 1,
                    "node4": 1,
                    "node5": 3,
                    "node6": 1,
                },
            }
        )


class CorosyncLinkNumberDuplication(NameBuildTest):
    code = codes.COROSYNC_LINK_NUMBER_DUPLICATION
    def test_message(self):
        self.assert_message_from_info(
            "Link numbers must be unique, duplicate link numbers: '1', '3'",
            {
                "link_number_list": ["1", "3"],
            }
        )

class NodeAddressesAlreadyExist(NameBuildTest):
    code = codes.NODE_ADDRESSES_ALREADY_EXIST
    def test_one_address(self):
        self.assert_message_from_info(
            "Node address 'node1' is already used by existing nodes; please, "
            "use other address",
            {
                "address_list": ["node1"],
            }
        )

    def test_more_addresses(self):
        self.assert_message_from_info(
            "Node addresses 'node1', 'node3' are already used by existing "
            "nodes; please, use other addresses",
            {
                "address_list": ["node1", "node3"],
            }
        )

class NodeAddressesDuplication(NameBuildTest):
    code = codes.NODE_ADDRESSES_DUPLICATION
    def test_message(self):
        self.assert_message_from_info(
            "Node addresses must be unique, duplicate addresses: "
                "'node1', 'node3'"
            ,
            {
                "address_list": ["node1", "node3"],
            }
        )

class NodeNamesAlreadyExist(NameBuildTest):
    code = codes.NODE_NAMES_ALREADY_EXIST
    def test_one_address(self):
        self.assert_message_from_info(
            "Node name 'node1' is already used by existing nodes; please, "
            "use other name",
            {
                "name_list": ["node1"],
            }
        )

    def test_more_addresses(self):
        self.assert_message_from_info(
            "Node names 'node1', 'node3' are already used by existing "
            "nodes; please, use other names",
            {
                "name_list": ["node1", "node3"],
            }
        )

class NodeNamesDuplication(NameBuildTest):
    code = codes.NODE_NAMES_DUPLICATION
    def test_message(self):
        self.assert_message_from_info(
            "Node names must be unique, duplicate names: 'node1', 'node3'",
            {
                "name_list": ["node1", "node3"],
            }
        )


class CorosyncNodesMissing(NameBuildTest):
    code = codes.COROSYNC_NODES_MISSING
    def test_message(self):
        self.assert_message_from_info(
            "No nodes have been specified",
            {
            }
        )


class CorosyncQuorumHeuristicsEnabledWithNoExec(NameBuildTest):
    code = codes.COROSYNC_QUORUM_HEURISTICS_ENABLED_WITH_NO_EXEC
    def test_message(self):
        self.assert_message_from_info(
            "No exec_NAME options are specified, so heuristics are effectively "
                "disabled"
        )


class CorosyncTooManyLinks(NameBuildTest):
    code = codes.COROSYNC_TOO_MANY_LINKS
    def test_udp(self):
        self.assert_message_from_info(
            "Cannot set 2 links, udp/udpu transport supports up to 1 link",
            {
                "actual_count": 2,
                "max_count": 1,
                "transport": "udp/udpu",
            }
        )

    def test_knet(self):
        self.assert_message_from_info(
            "Cannot set 9 links, knet transport supports up to 8 links",
            {
                "actual_count": 9,
                "max_count": 8,
                "transport": "knet",
            }
        )


class CorosyncTransportUnsupportedOptions(NameBuildTest):
    code = codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS
    def test_udp(self):
        self.assert_message_from_info(
            "The udp/udpu transport does not support 'crypto' options, use "
                "'knet' transport"
            ,
            {
                "option_type": "crypto",
                "actual_transport": "udp/udpu",
                "required_transport_list": ["knet"],
            }
        )


class ResourceCleanupError(NameBuildTest):
    code = codes.RESOURCE_CLEANUP_ERROR

    def test_minimal(self):
        self.assert_message_from_info(
            "Unable to forget failed operations of resources\nsomething wrong",
            {
                "reason": "something wrong",
                "resource": None,
                "node": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "Unable to forget failed operations of resources\nsomething wrong",
            {
                "reason": "something wrong",
                "resource": None,
                "node": "N1",
            }
        )

    def test_resource(self):
        self.assert_message_from_info(
            "Unable to forget failed operations of resource: R1\n"
                "something wrong"
            ,
            {
                "reason": "something wrong",
                "resource": "R1",
                "node": None,
            }
        )

    def test_resource_and_node(self):
        self.assert_message_from_info(
            "Unable to forget failed operations of resource: R1\n"
                "something wrong"
            ,
            {
                "reason": "something wrong",
                "resource": "R1",
                "node": "N1",
            }
        )


class ResourceRefreshError(NameBuildTest):
    code = codes.RESOURCE_REFRESH_ERROR

    def test_minimal(self):
        self.assert_message_from_info(
            "Unable to delete history of resources\nsomething wrong",
            {
                "reason": "something wrong",
                "resource": None,
                "node": None,
            }
        )

    def test_node(self):
        self.assert_message_from_info(
            "Unable to delete history of resources\nsomething wrong",
            {
                "reason": "something wrong",
                "resource": None,
                "node": "N1",
            }
        )

    def test_resource(self):
        self.assert_message_from_info(
            "Unable to delete history of resource: R1\nsomething wrong",
            {
                "reason": "something wrong",
                "resource": "R1",
                "node": None,
            }
        )

    def test_resource_and_node(self):
        self.assert_message_from_info(
            "Unable to delete history of resource: R1\nsomething wrong",
            {
                "reason": "something wrong",
                "resource": "R1",
                "node": "N1",
            }
        )


class ResourceRefreshTooTimeConsuming(NameBuildTest):
    code = codes.RESOURCE_REFRESH_TOO_TIME_CONSUMING
    def test_success(self):
        self.assert_message_from_info(
            "Deleting history of all resources on all nodes will execute more "
                "than 25 operations in the cluster, which may negatively "
                "impact the responsiveness of the cluster. Consider specifying "
                "resource and/or node"
            ,
            {
                "threshold": 25,
            }
        )


class IdNotFound(NameBuildTest):
    code = codes.ID_NOT_FOUND
    def test_id(self):
        self.assert_message_from_info(
            "'ID' does not exist",
            {
                "id": "ID",
                "expected_types": [],
                "context_type": "",
                "context_id": "",
            }
        )

    def test_id_and_type(self):
        self.assert_message_from_info(
            "clone/resource 'ID' does not exist",
            {
                "id": "ID",
                "expected_types": ["primitive", "clone"],
                "context_type": "",
                "context_id": "",
            }
        )

    def test_context(self):
        self.assert_message_from_info(
            "there is no 'ID' in the C_TYPE 'C_ID'",
            {
                "id": "ID",
                "expected_types": [],
                "context_type": "C_TYPE",
                "context_id": "C_ID",
            }
        )

    def test_type_and_context(self):
        self.assert_message_from_info(
            "there is no ACL user 'ID' in the C_TYPE 'C_ID'",
            {
                "id": "ID",
                "expected_types": ["acl_target"],
                "context_type": "C_TYPE",
                "context_id": "C_ID",
            }
        )


class CibPushForcedFullDueToCrmFeatureSet(NameBuildTest):
    code = codes.CIB_PUSH_FORCED_FULL_DUE_TO_CRM_FEATURE_SET
    def test_success(self):
        self.assert_message_from_info(
            (
                "Replacing the whole CIB instead of applying a diff, a race "
                "condition may happen if the CIB is pushed more than once "
                "simultaneously. To fix this, upgrade pacemaker to get "
                "crm_feature_set at least 3.0.9, current is 3.0.6."
            ),
            {
                "required_set": "3.0.9",
                "current_set": "3.0.6",
            }
        )

class NodeCommunicationRetrying(NameBuildTest):
    code = codes.NODE_COMMUNICATION_RETRYING
    def test_success(self):
        self.assert_message_from_info(
            (
                "Unable to connect to 'node_name' via address 'failed.address' "
                "and port '2224'. Retrying request 'my/request' via address "
                "'next.address' and port '2225'"
            ),
            {
                "node": "node_name",
                "failed_address": "failed.address",
                "failed_port": "2224",
                "next_address": "next.address",
                "next_port": "2225",
                "request": "my/request",
            }
        )

class HostNotFound(NameBuildTest):
    code = codes.HOST_NOT_FOUND
    def test_single_host(self):
        self.assert_message_from_info(
            (
                "Host 'unknown_host' is not known to pcs, try to authenticate "
                "the host using 'pcs host auth unknown_host' command"
            ),
            {
                "host_list": ["unknown_host"],
            }
        )

    def test_multiple_hosts(self):
        self.assert_message_from_info(
            (
                "Hosts 'another_one', 'unknown_host' are not known to pcs, try "
                "to authenticate the hosts using 'pcs host auth another_one "
                "unknown_host' command"
            ),
            {
                "host_list": ["unknown_host", "another_one"],
            }
        )

class HostAlreadyAuthorized(NameBuildTest):
    code = codes.HOST_ALREADY_AUTHORIZED
    def test_success(self):
        self.assert_message_from_info(
            "host: Already authorized",
            {
                "host_name": "host",
            }
        )

class NodeCommunicationErrorNotAuthorized(NameBuildTest):
    code = codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED
    def test_success(self):
        self.assert_message_from_info(
            (
                "Unable to authenticate to node1 (some error), try running "
                "'pcs host auth node1'"
            ),
            {
                "node": "node1",
                "reason": "some error",
            }
        )

class ClusterDestroyStarted(NameBuildTest):
    code = codes.CLUSTER_DESTROY_STARTED
    def test_multiple_hosts(self):
        self.assert_message_from_info(
            "Destroying cluster on hosts: 'node1', 'node2', 'node3'...",
            {
                "host_name_list": ["node1", "node3", "node2"],
            }
        )

    def test_single_host(self):
        self.assert_message_from_info(
            "Destroying cluster on hosts: 'node1'...",
            {
                "host_name_list": ["node1"],
            }
        )

class ClusterDestroySuccess(NameBuildTest):
    code = codes.CLUSTER_DESTROY_SUCCESS
    def test_success(self):
        self.assert_message_from_info(
            "node1: Successfully destroyed cluster",
            {
                "node": "node1",
            }
        )

class ClusterEnableStarted(NameBuildTest):
    code = codes.CLUSTER_ENABLE_STARTED
    def test_multiple_hosts(self):
        self.assert_message_from_info(
            "Enabling cluster on hosts: 'node1', 'node2', 'node3'...",
            {
                "host_name_list": ["node1", "node3", "node2"],
            }
        )

    def test_single_host(self):
        self.assert_message_from_info(
            "Enabling cluster on hosts: 'node1'...",
            {
                "host_name_list": ["node1"],
            }
        )

class ClusterEnableSuccess(NameBuildTest):
    code = codes.CLUSTER_ENABLE_SUCCESS
    def test_success(self):
        self.assert_message_from_info(
            "node1: Cluster enabled",
            {
                "node": "node1",
            }
        )

class ClusterStartStarted(NameBuildTest):
    code = codes.CLUSTER_START_STARTED
    def test_multiple_hosts(self):
        self.assert_message_from_info(
            "Starting cluster on hosts: 'node1', 'node2', 'node3'...",
            {
                "host_name_list": ["node1", "node3", "node2"],
            }
        )

    def test_single_host(self):
        self.assert_message_from_info(
            "Starting cluster on hosts: 'node1'...",
            {
                "host_name_list": ["node1"],
            }
        )

class ServiceNotInstalled(NameBuildTest):
    code = codes.SERVICE_NOT_INSTALLED
    def test_multiple_services(self):
        self.assert_message_from_info(
            "node1: Required cluster services not installed: 'service1', "
                "'service2', 'service3'"
            ,
            {
                "service_list": ["service1", "service3", "service2"],
                "node": "node1",
            }
        )

    def test_single_service(self):
        self.assert_message_from_info(
            "node1: Required cluster services not installed: 'service'",
            {
                "service_list": ["service"],
                "node": "node1",
            }
        )


class HostAlreadyInClusterConfig(NameBuildTest):
    code = codes.HOST_ALREADY_IN_CLUSTER_CONFIG
    def test_success(self):
        self.assert_message_from_info(
            "host: Cluster configuration files found, the host seems to be in "
                "a cluster already"
            ,
            {
                "host_name": "host",
            }
        )


class HostAlreadyInClusterServices(NameBuildTest):
    code = codes.HOST_ALREADY_IN_CLUSTER_SERVICES
    def test_multiple_services(self):
        self.assert_message_from_info(
            (
                "node1: Running cluster services: 'service1', 'service2', "
                "'service3', the host seems to be in a cluster already"
            ),
            {
                "service_list": ["service1", "service3", "service2"],
                "host_name": "node1",
            }
        )

    def test_single_service(self):
        self.assert_message_from_info(
            "node1: Running cluster services: 'service', the host seems to be "
                "in a cluster already"
            ,
            {
                "service_list": ["service"],
                "host_name": "node1",
            }
        )


class ServiceVersionMismatch(NameBuildTest):
    code = codes.SERVICE_VERSION_MISMATCH
    def test_success(self):
        self.assert_message_from_info(
            "Hosts do not have the same version of 'service'; "
                "hosts 'host4', 'host5', 'host6' have version 2.0; "
                "hosts 'host1', 'host3' have version 1.0; "
                "host 'host2' has version 1.2"
            ,
            {
                "service": "service",
                "hosts_version": {
                    "host1": 1.0,
                    "host2": 1.2,
                    "host3": 1.0,
                    "host4": 2.0,
                    "host5": 2.0,
                    "host6": 2.0,
                }
            }
        )

class WaitForNodeStartupStarted(NameBuildTest):
    code = codes.WAIT_FOR_NODE_STARTUP_STARTED
    def test_success(self):
        self.assert_message_from_info(
            "Waiting for nodes to start: 'node1', 'node2', 'node3'...",
            {
                "node_name_list": ["node1", "node3", "node2"],
            }
        )

class PcsdVersionTooOld(NameBuildTest):
    code = codes.PCSD_VERSION_TOO_OLD
    def test_success(self):
        self.assert_message_from_info(
            (
                "node1: Old version of pcsd is running on the node, therefore "
                "it is unable to perform the action"
            ),
            {
                "node": "node1",
            }
        )

class PcsdSslCertAndKeyDistributionStarted(NameBuildTest):
    code = codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED
    def test_success(self):
        self.assert_message_from_info(
            "Synchronizing pcsd SSL certificates on nodes 'node1', 'node2', "
                "'node3'..."
            ,
            {
                "node_name_list": ["node1", "node3", "node2"],
            }
        )

class PcsdSslCertAndKeySetSuccess(NameBuildTest):
    code = codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS
    def test_success(self):
        self.assert_message_from_info(
            "node1: Success",
            {
                "node": "node1",
            }
        )

class UsingKnownHostAddressForHost(NameBuildTest):
    code = codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST
    def test_success(self):
        self.assert_message_from_info(
            "No addresses specified for host 'node-name', using 'node-addr'",
            {
                "host_name": "node-name",
                "address": "node-addr"
            }
        )

class ResourceInBundleNotAccessible(NameBuildTest):
    code = codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE
    def test_success(self):
        self.assert_message_from_info(
            (
                "Resource 'resourceA' will not be accessible by the cluster "
                "inside bundle 'bundleA', at least one of bundle options "
                "'control-port' or 'ip-range-start' has to be specified"
            ),
            dict(
                bundle_id="bundleA",
                inner_resource_id="resourceA",
            )
        )

class FileAlreadyExists(NameBuildTest):
    code = codes.FILE_ALREADY_EXISTS
    def test_minimal(self):
        self.assert_message_from_info(
            "Corosync authkey file '/etc/corosync/key' already exists",
            {
                "file_role": "COROSYNC_AUTHKEY",
                "file_path": "/etc/corosync/key",
                "node": None,
            }
        )

    def test_with_node(self):
        self.assert_message_from_info(
            "node1: pcs configuration file '/var/lib/pcsd/conf' already exists",
            {
                "file_role": "PCS_SETTINGS_CONF",
                "file_path": "/var/lib/pcsd/conf",
                "node": "node1",
            }
        )

class FileDoesNotExist(NameBuildTest):
    code = codes.FILE_DOES_NOT_EXIST
    def test_success(self):
        self.assert_message_from_info(
            "UNKNOWN_ROLE file '/etc/cluster/something' does not exist",
            {
                "file_role": "UNKNOWN_ROLE",
                "file_path": "/etc/cluster/something",
            }
        )

class FileIoError(NameBuildTest):
    code = codes.FILE_IO_ERROR
    def test_success_a(self):
        self.assert_message_from_info(
            "Unable to chown Booth key '/etc/booth/booth.key': Failed",
            {
                "file_role": "BOOTH_KEY",
                "file_path": "/etc/booth/booth.key",
                "reason": "Failed",
                "operation": "chown",
            }
        )

    def test_success_b(self):
        self.assert_message_from_info(
            "Unable to chmod Booth configuration '/etc/booth/main.cfg': Failed",
            {
                "file_role": "BOOTH_CONFIG",
                "file_path": "/etc/booth/main.cfg",
                "reason": "Failed",
                "operation": "chmod",
            }
        )

    def test_success_c(self):
        self.assert_message_from_info(
            "Unable to remove Pacemaker authkey '/etc/pacemaker/key': Failed",
            {
                "file_role": "PACEMAKER_AUTHKEY",
                "file_path": "/etc/pacemaker/key",
                "reason": "Failed",
                "operation": "remove",
            }
        )

    def test_success_d(self):
        self.assert_message_from_info(
            "Unable to read pcsd SSL certificate '/var/lib/pcsd.crt': Failed",
            {
                "file_role": "PCSD_SSL_CERT",
                "file_path": "/var/lib/pcsd.crt",
                "reason": "Failed",
                "operation": "read",
            }
        )

    def test_success_e(self):
        self.assert_message_from_info(
            "Unable to write pcsd SSL key '/var/lib/pcsd.key': Failed",
            {
                "file_role": "PCSD_SSL_KEY",
                "file_path": "/var/lib/pcsd.key",
                "reason": "Failed",
                "operation": "write",
            }
        )

class UsingDefaultWatchdog(NameBuildTest):
    code = codes.USING_DEFAULT_WATCHDOG
    def test_success(self):
        self.assert_message_from_info(
            (
                "No watchdog has been specified for node 'node1'. Using "
                "default watchdog '/dev/watchdog'"
            ),
            {
                "node": "node1",
                "watchdog": "/dev/watchdog",
            }
        )

class CorosyncQuorumAtbCannotBeDisabledDueToSbd(NameBuildTest):
    code = codes.COROSYNC_QUORUM_ATB_CANNOT_BE_DISABLED_DUE_TO_SBD
    def test_success(self):
        self.assert_message_from_info(
            (
                "Unable to disable auto_tie_breaker, SBD fencing would have no "
                "effect"
            ),
            {
            }
        )

class CorosyncQuorumAtbWillBeEnabledDueToSbd(NameBuildTest):
    code = codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD
    def test_success(self):
        self.assert_message_from_info(
            (
                "auto_tie_breaker quorum option will be enabled to make SBD "
                "fencing effective. Cluster has to be offline to be able to "
                "make this change."
            ),
            {
            }
        )


class CorosyncConfigReloaded(NameBuildTest):
    code = codes.COROSYNC_CONFIG_RELOADED
    def test_with_node(self):
        self.assert_message_from_report(
            "node1: Corosync configuration reloaded",
            reports.corosync_config_reloaded("node1"),
        )

    def test_without_node(self):
        self.assert_message_from_report(
            "Corosync configuration reloaded",
            reports.corosync_config_reloaded(),
        )


class CorosyncConfigReloadNotPossible(NameBuildTest):
    code = codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE
    def test_success(self):
        self.assert_message_from_report(
            (
                "node1: Corosync is not running, therefore reload of the "
                "corosync configuration is not possible"
            ),
            reports.corosync_config_reload_not_possible("node1")
        )


class CorosyncConfigReloadError(NameBuildTest):
    code = codes.COROSYNC_CONFIG_RELOAD_ERROR
    def test_with_node(self):
        self.assert_message_from_report(
            "node1: Unable to reload corosync configuration: a reason",
            reports.corosync_config_reload_error("a reason", "node1"),
        )

    def test_without_node(self):
        self.assert_message_from_report(
            "Unable to reload corosync configuration: different reason",
            reports.corosync_config_reload_error("different reason"),
        )

class CannotRemoveAllClusterNodes(NameBuildTest):
    code = codes.CANNOT_REMOVE_ALL_CLUSTER_NODES
    def test_success(self):
        self.assert_message_from_report(
            (
                "No nodes would be left in the cluster, if you intend to "
                "destroy the whole cluster, run 'pcs cluster destroy --all' "
                "instead"
            ),
            reports.cannot_remove_all_cluster_nodes()
        )

class NodeUsedAsTieBreaker(NameBuildTest):
    code = codes.NODE_USED_AS_TIE_BREAKER
    def test_success(self):
        self.assert_message_from_report(
            (
                "Node 'node2' with id '2' is used as a tie breaker for a "
                "qdevice, run 'pcs quorum device update model "
                "tie_breaker=<node id>' to change it"
            ),
            reports.node_used_as_tie_breaker("node2", 2)
        )

class UnableToConnectToAllRemainingNode(NameBuildTest):
    code = codes.UNABLE_TO_CONNECT_TO_ALL_REMAINING_NODE
    def test_success(self):
        self.assert_message_from_report(
            (
                "Remaining cluster nodes 'node0', 'node1', 'node2' are "
                "unreachable, run 'pcs cluster sync' on some now online node "
                "once they become available"
            ),
            reports.unable_to_connect_to_all_remaining_node(
                ["node1", "node0", "node2"]
            )
        )

class NodesToRemoveUnreachable(NameBuildTest):
    code = codes.NODES_TO_REMOVE_UNREACHABLE
    def test_success(self):
        self.assert_message_from_report(
            (
                "Removed nodes 'node0', 'node1', 'node2' are unreachable, "
                "therefore it is not possible to deconfigure them. Run 'pcs "
                "cluster destroy' on them when available."
            ),
            reports.nodes_to_remove_unreachable(["node1", "node0", "node2"])
        )

class CorosyncQuorumGetStatusError(NameBuildTest):
    code = codes.COROSYNC_QUORUM_GET_STATUS_ERROR
    def test_success(self):
        self.assert_message_from_report(
            "Unable to get quorum status: a reason",
            reports.corosync_quorum_get_status_error("a reason")
        )

    def test_success_with_node(self):
        self.assert_message_from_report(
            "node1: Unable to get quorum status: a reason",
            reports.corosync_quorum_get_status_error("a reason", "node1")
        )


class SbdListWatchdogError(NameBuildTest):
    code = codes.SBD_LIST_WATCHDOG_ERROR
    def test_success(self):
        self.assert_message_from_report(
            "Unable to query available watchdogs from sbd: this is a reason",
            reports.sbd_list_watchdog_error("this is a reason"),
        )


class SbdWatchdogNotSupported(NameBuildTest):
    code = codes.SBD_WATCHDOG_NOT_SUPPORTED
    def test_success(self):
        self.assert_message_from_report(
            (
                "node1: Watchdog '/dev/watchdog' is not supported (it may be a "
                "software watchdog)"
            ),
            reports.sbd_watchdog_not_supported("node1", "/dev/watchdog"),
        )


class SbdWatchdogTestError(NameBuildTest):
    code = codes.SBD_WATCHDOG_TEST_ERROR
    def test_success(self):
        self.assert_message_from_report(
            "Unable to initialize test of the watchdog: some reason",
            reports.sbd_watchdog_test_error("some reason"),
        )


class ResourceBundleUnsupportedContainerType(NameBuildTest):
    code = codes.RESOURCE_BUNDLE_UNSUPPORTED_CONTAINER_TYPE
    def test_success(self):
        self.assert_message_from_report(
            (
                "Bundle 'bundle id' uses unsupported container type, therefore "
                "it is not possible to set its container options. Supported "
                "container types are: 'a', 'b', 'c'"
            ),
            reports.resource_bundle_unsupported_container_type(
                "bundle id", ["b", "a", "c"]
            ),
        )

class FenceHistoryCommandError(NameBuildTest):
    code = codes.FENCE_HISTORY_COMMAND_ERROR
    def test_success(self):
        self.assert_message_from_report(
            "Unable to show fence history: reason",
            reports.fence_history_command_error("reason", "show")
        )

class FenceHistoryNotSupported(NameBuildTest):
    code = codes.FENCE_HISTORY_NOT_SUPPORTED
    def test_success(self):
        self.assert_message_from_report(
            "Fence history is not supported, please upgrade pacemaker",
            reports.fence_history_not_supported()
        )

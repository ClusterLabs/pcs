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
            "Fencing level for 'node-\d+' at level '1' with device(s) "
                "'device1,device2' already exists",
            {
                "level": "1",
                "target_type": TARGET_TYPE_REGEXP,
                "target_value": "node-\d+",
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
            "'ID' is not a clone/master/resource",
            {
                "id": "ID",
                "expected_types": ["primitive", "master", "clone"],
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
                "roles_with_nodes": {"Started": ["node1","node2"]},
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
                    "Started": ["node1","node2"],
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

class NodeIsInCluster(NameBuildTest):
    code = codes.CANNOT_ADD_NODE_IS_IN_CLUSTER
    def test_build_message(self):
        self.assert_message_from_info(
            "cannot add the node 'N1' because it is in a cluster",
            {
                "node": "N1",
            }
        )

class NodeIsRunningPacemakerRemote(NameBuildTest):
    code = codes.CANNOT_ADD_NODE_IS_RUNNING_SERVICE
    def test_build_message(self):
        self.assert_message_from_info(
            "cannot add the node 'N1' because it is running service"
                " 'pacemaker_remote' (is not the node already in a cluster?)"
            ,
            {
                "node": "N1",
                "service": "pacemaker_remote",
            }
        )
    def test_build_message_with_unknown_service(self):
        self.assert_message_from_info(
            "cannot add the node 'N1' because it is running service 'unknown'",
            {
                "node": "N1",
                "service": "unknown",
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


class SbdNoDEviceForNode(NameBuildTest):
    code = codes.SBD_NO_DEVICE_FOR_NODE
    def test_build_message(self):
        self.assert_message_from_info(
            "No device defined for node 'node1'",
            {
                "node": "node1",
            }
        )


class SbdTooManyDevicesForNode(NameBuildTest):
    code = codes.SBD_TOO_MANY_DEVICES_FOR_NODE
    def test_build_messages(self):
        self.assert_message_from_info(
            "More than 3 devices defined for node 'node1' (devices: /dev1, "
                "/dev2, /dev3)",
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
        self.assert_message_from_info(
            "Sending 'first', 'second'",
            {
                "file_list": ["first", "second"],
                "node_list": None,
                "description": None,
            }
        )

    def test_build_messages_with_nodes(self):
        self.assert_message_from_info(
            "Sending 'first', 'second' to 'node1', 'node2'",
            {
                "file_list": ["first", "second"],
                "node_list": ["node1", "node2"],
                "description": None,
            }
        )

    def test_build_messages_with_description(self):
        self.assert_message_from_info(
            "Sending configuration files to 'node1', 'node2'",
            {
                "file_list": ["first", "second"],
                "node_list": ["node1", "node2"],
                "description": "configuration files",
            }
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

class FileRemoveFromNodeStarted(NameBuildTest):
    code = codes.FILES_REMOVE_FROM_NODE_STARTED
    def test_build_messages(self):
        self.assert_message_from_info(
            "Requesting remove 'first', 'second' from 'node1', 'node2'",
            {
                "file_list": ["first", "second"],
                "node_list": ["node1", "node2"],
                "description": None,
            }
        )

    def test_build_messages_with_description(self):
        self.assert_message_from_info(
            "Requesting remove remote configuration files from 'node1',"
                " 'node2'"
            ,
            {
                "file_list": ["first", "second"],
                "node_list": ["node1", "node2"],
                "description": "remote configuration files",
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


class ActionsOnNodesStarted(NameBuildTest):
    code = codes.SERVICE_COMMANDS_ON_NODES_STARTED
    def test_build_messages(self):
        self.assert_message_from_info(
            "Requesting 'first', 'second'",
            {
                "action_list": ["first", "second"],
                "node_list": None,
                "description": None,
            }
        )

    def test_build_messages_with_nodes(self):
        self.assert_message_from_info(
            "Requesting 'first', 'second' on 'node1', 'node2'",
            {
                "action_list": ["first", "second"],
                "node_list": ["node1", "node2"],
                "description": None,
            }
        )

    def test_build_messages_with_description(self):
        self.assert_message_from_info(
            "Requesting running pacemaker_remote on 'node1', 'node2'",
            {
                "action_list": ["first", "second"],
                "node_list": ["node1", "node2"],
                "description": "running pacemaker_remote",
            }
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

class resource_is_guest_node_already(NameBuildTest):
    code = codes.RESOURCE_IS_GUEST_NODE_ALREADY
    def test_build_messages(self):
        self.assert_message_from_info(
            "the resource 'some-resource' is already a guest node",
            {"resource_id": "some-resource"}
        )

class live_environment_required(NameBuildTest):
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

class nolive_skip_files_distribution(NameBuildTest):
    code = codes.NOLIVE_SKIP_FILES_DISTRIBUTION
    def test_build_messages(self):
        self.assert_message_from_info(
            "the distribution of 'file1', 'file2' to 'node1', 'node2' was"
                " skipped because command"
                " does not run on live cluster (e.g. -f was used)."
                " You will have to do it manually."
            ,
            {
                "files_description": ["file1", 'file2'],
                "nodes": ["node1", "node2"],
            }
        )

class nolive_skip_files_remove(NameBuildTest):
    code = codes.NOLIVE_SKIP_FILES_REMOVE
    def test_build_messages(self):
        self.assert_message_from_info(
            "'file1', 'file2' remove from 'node1', 'node2'"
                " was skipped because command"
                " does not run on live cluster (e.g. -f was used)."
                " You will have to do it manually."
            ,
            {
                "files_description": ["file1", 'file2'],
                "nodes": ["node1", "node2"],
            }
        )

class nolive_skip_service_command_on_nodes(NameBuildTest):
    code = codes.NOLIVE_SKIP_SERVICE_COMMAND_ON_NODES
    def test_build_messages(self):
        self.assert_message_from_info(
            "running 'pacemaker_remote start' on 'node1', 'node2' was skipped"
                " because command does not run on live cluster (e.g. -f was"
                " used). You will have to run it manually."
            ,
            {
                "service": "pacemaker_remote",
                "command": "start",
                "nodes": ["node1", "node2"]
            }
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
    def test_build_messages(self):
        self.assert_message_from_info(
            "unable to remove node 'NODE' from pacemaker: reason",
            {
                "node_name": "NODE",
                "reason": "reason"
            }
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
                "node_id": 2,
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
                "node_id": 2,
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
                "node_id": 2,
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
                "node_id": 2,
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
                "node_id": 2,
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
                "node_id": 2,
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


class CorosyncNodeAddressDuplication(NameBuildTest):
    code = codes.COROSYNC_NODE_ADDRESS_DUPLICATION
    def test_message(self):
        self.assert_message_from_info(
            "Node addresses must be unique, duplicate addresses: "
                "'node1', 'node3'"
            ,
            {
                "address_list": ["node1", "node3"],
            }
        )


class CorosyncNodeNameDuplication(NameBuildTest):
    code = codes.COROSYNC_NODE_NAME_DUPLICATION
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
            "clone/master/resource 'ID' does not exist",
            {
                "id": "ID",
                "expected_types": ["primitive", "master", "clone"],
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
            "host: Cluster configuration files found. Is the host already in "
                "a cluster?"
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
                "'service3'. Is the host already in a cluster?"
            ),
            {
                "service_list": ["service1", "service3", "service2"],
                "host_name": "node1",
            }
        )

    def test_single_service(self):
        self.assert_message_from_info(
            "node1: Running cluster services: 'service'. Is the host already "
                "in a cluster?"
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
                "inside bundle 'bundleA'. At least one of bundle options "
                "'control-port' or 'ip-range-start' has to be specified."
            ),
            dict(
                bundle_id="bundleA",
                resource_id="resourceA",
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

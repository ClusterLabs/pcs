from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
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

    def assert_message_from_info(self, message, info):
        build = CODE_TO_MESSAGE_BUILDER_MAP[self.code]
        self.assertEqual(message, build(info))


class BuildInvalidOptionMessageTest(NameBuildTest):
    code = codes.INVALID_OPTION
    def test_build_message_with_type(self):
        self.assert_message_from_info(
            "invalid TYPE option 'NAME', allowed options are: FIRST, SECOND",
            {
                "option_names": ["NAME"],
                "option_type": "TYPE",
                "allowed": sorted(["FIRST", "SECOND"]),
            }
        )

    def test_build_message_without_type(self):
        self.assert_message_from_info(
            "invalid option 'NAME', allowed options are: FIRST, SECOND",
            {
                "option_names": ["NAME"],
                "option_type": "",
                "allowed": sorted(["FIRST", "SECOND"]),
            }
        )

    def test_build_message_with_multiple_names(self):
        self.assert_message_from_info(
            "invalid options: 'ANOTHER', 'NAME', allowed option is FIRST",
            {
                "option_names": ["NAME", "ANOTHER"],
                "option_type": "",
                "allowed": ["FIRST"],
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


class ResourceAlreadyDefinedInBundleTest(NameBuildTest):
    code = codes.RESOURCE_ALREADY_DEFINED_IN_BUNDLE
    def test_build_message_with_data(self):
        self.assert_message_from_info(
            "bundle 'test_bundle' already contains resource 'test_resource'",
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
        self.assert_message_from_info("'ID' is not primitive/master/clone", {
            "id": "ID",
            "expected_types": ["primitive", "master", "clone"],
            "current_type": "op",
        })

    def test_build_message_with_transformation(self):
        self.assert_message_from_info("'ID' is not a group", {
            "id": "ID",
            "expected_types": ["group"],
            "current_type": "op",
        })

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

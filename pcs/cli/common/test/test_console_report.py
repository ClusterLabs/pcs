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
                " Use standard:provider:type or standard:type."
                " List of standards and providers can be obtained by using"
                " commands 'pcs resource standards' and"
                " 'pcs resource providers'"
            ,
            {
                "name": ":name",
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


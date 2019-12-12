# pylint: disable=too-many-lines

from unittest import mock, TestCase

from pcs.cli.common.console_report import(
    format_optional,
    format_plural,
    _is_multiple,
    _add_s
)
from pcs.cli.common.reports import CODE_BUILDER_MAP
from pcs.common import file_type_codes
from pcs.common.fencing_topology import (
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
    TARGET_TYPE_ATTRIBUTE,
)
from pcs.common.file import RawFileError
from pcs.common.tools import indent
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


class BuildInvalidOptionsMessageTest(NameBuildTest):
    def test_build_message_with_type(self):
        self.assert_message_from_report(
            "invalid TYPE option 'NAME', allowed options are: 'FIRST', "
                "'SECOND'"
            ,
            reports.invalid_options(["NAME"], ["SECOND", "FIRST"], "TYPE")
        )

    def test_build_message_without_type(self):
        self.assert_message_from_report(
            "invalid option 'NAME', allowed options are: 'FIRST', 'SECOND'",
            reports.invalid_options(["NAME"], ["FIRST", "SECOND"], "")
        )

    def test_build_message_with_multiple_names(self):
        self.assert_message_from_report(
            "invalid options: 'ANOTHER', 'NAME', allowed option is 'FIRST'",
            reports.invalid_options(["NAME", "ANOTHER"], ["FIRST"], "")
        )

    def test_pattern(self):
        self.assert_message_from_report(
            (
                "invalid option 'NAME', allowed are options matching patterns: "
                "'exec_<name>'"
            ),
            reports.invalid_options(["NAME"], [], "", ["exec_<name>"])
        )

    def test_allowed_and_patterns(self):
        self.assert_message_from_report(
            (
                "invalid option 'NAME', allowed option is 'FIRST' and options "
                "matching patterns: 'exec_<name>'"
            ),
            reports.invalid_options(
                ["NAME"], ["FIRST"], "",
                allowed_option_patterns=["exec_<name>"])
        )

    def test_no_allowed_options(self):
        self.assert_message_from_report(
            "invalid options: 'ANOTHER', 'NAME', there are no options allowed",
            reports.invalid_options(["NAME", "ANOTHER"], [], "")
        )


class InvalidUserdefinedOptions(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            (
                "invalid option 'exec_NAME', options may contain "
                "a-z A-Z 0-9 /_- characters only"
            ),
            reports.invalid_userdefined_options(
                ["exec_NAME"], "", "a-z A-Z 0-9 /_-"
            )
        )

    def test_with_type(self):
        self.assert_message_from_report(
            (
                "invalid heuristics option 'exec_NAME', heuristics options may "
                "contain a-z A-Z 0-9 /_- characters only"
            ),
            reports.invalid_userdefined_options(
                ["exec_NAME"], "heuristics", "a-z A-Z 0-9 /_-"
            )
        )

    def test_more_options(self):
        self.assert_message_from_report(
            (
                "invalid TYPE options: 'ANOTHER', 'NAME', TYPE options may "
                "contain a-z A-Z 0-9 /_- characters only"
            ),
            reports.invalid_userdefined_options(
                ["NAME", "ANOTHER"], "TYPE", "a-z A-Z 0-9 /_-"
            )
        )


class RequiredOptionsAreMissing(NameBuildTest):
    def test_build_message_with_type(self):
        self.assert_message_from_report(
            "required TYPE option 'NAME' is missing",
            reports.required_options_are_missing(
                ["NAME"],
                option_type="TYPE"
            )
        )

    def test_build_message_without_type(self):
        self.assert_message_from_report(
            "required option 'NAME' is missing",
            reports.required_options_are_missing(["NAME"])
        )

    def test_build_message_with_multiple_names(self):
        self.assert_message_from_report(
            "required options 'ANOTHER', 'NAME' are missing",
            reports.required_options_are_missing(["NAME", "ANOTHER"])
        )

class BuildInvalidOptionValueMessageTest(NameBuildTest):
    def test_multiple_allowed_values(self):
        self.assert_message_from_report(
            "'VALUE' is not a valid NAME value, use 'FIRST', 'SECOND'",
            reports.invalid_option_value("NAME", "VALUE", ["SECOND", "FIRST"])
        )

    def test_textual_hint(self):
        self.assert_message_from_report(
            "'VALUE' is not a valid NAME value, use some hint",
            reports.invalid_option_value("NAME", "VALUE", "some hint")
        )

    def test_cannot_be_empty(self):
        self.assert_message_from_report(
            "NAME cannot be empty",
            reports.invalid_option_value(
                "NAME", "VALUE",
                allowed_values=None,
                cannot_be_empty=True
            )
        )

    def test_cannot_be_empty_with_hint(self):
        self.assert_message_from_report(
            "NAME cannot be empty, use 'FIRST', 'SECOND'",
            reports.invalid_option_value(
                "NAME", "VALUE", ["SECOND", "FIRST"],
                cannot_be_empty=True
            )
        )

    def test_forbidden_characters(self):
        self.assert_message_from_report(
            r"NAME cannot contain }{\r\n characters",
            reports.invalid_option_value(
                "NAME", "VALUE",
                allowed_values=None,
                forbidden_characters="}{\\r\\n"
            )
        )

    def test_forbidden_characters_with_hint(self):
        self.assert_message_from_report(
            r"NAME cannot contain }{\r\n characters, use 'FIRST', 'SECOND'",
            reports.invalid_option_value(
                "NAME", "VALUE", ["SECOND", "FIRST"],
                forbidden_characters="}{\\r\\n"
            )
        )

    def test_cannot_be_empty_and_forbidden_characters(self):
        self.assert_message_from_report(
            "NAME cannot be empty, use 'FIRST', 'SECOND'",
            reports.invalid_option_value(
                "NAME", "VALUE", ["SECOND", "FIRST"], True
            )
        )

class InvalidCibContent(NameBuildTest):
    def test_message_can_be_more_verbose(self):
        report = "no verbose\noutput\n"
        self.assert_message_from_report(
            "invalid cib:\n{0}\n\nUse --full for more details.".format(report),
            reports.invalid_cib_content(report, True)
        )

    def test_message_cannot_be_more_verbose(self):
        report = "some verbose\noutput"
        self.assert_message_from_report(
            "invalid cib:\n{0}".format(report),
            reports.invalid_cib_content(report, False)
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

class BuildInvalidIdTest(NameBuildTest):
    def test_build_message_with_first_char_invalid(self):
        self.assert_message_from_report(
            (
                "invalid ID_DESCRIPTION 'ID', 'INVALID_CHARACTER' is not a"
                " valid first character for a ID_DESCRIPTION"
            ),
            reports.invalid_id_bad_char(
                "ID", "ID_DESCRIPTION", "INVALID_CHARACTER",
                is_first_char=True
            )
        )
    def test_build_message_with_non_first_char_invalid(self):
        self.assert_message_from_report(
            (
                "invalid ID_DESCRIPTION 'ID', 'INVALID_CHARACTER' is not a"
                " valid character for a ID_DESCRIPTION"
            ),
            reports.invalid_id_bad_char(
                "ID", "ID_DESCRIPTION", "INVALID_CHARACTER",
                is_first_char=False
            )
        )

class InvalidIdIsEmpty(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "description cannot be empty",
            reports.invalid_id_is_empty("ID", "description")
        )

class InvalidScore(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "invalid score '1M', use integer or INFINITY or -INFINITY",
            reports.invalid_score("1M")
        )

class MultipleScoreOptions(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "multiple score options cannot be specified",
            reports.multiple_score_options()
        )

class InvalidTimeout(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "'24h' is not a valid number of seconds to wait",
            reports.invalid_timeout("24h")
        )


class BuildRunExternalStartedTest(NameBuildTest):

    def test_build_message_minimal(self):
        self.assert_message_from_report(
            "Running: COMMAND\nEnvironment:\n",
            reports.run_external_process_started(
                "COMMAND", "", dict()
            )
        )

    def test_build_message_with_stdin(self):
        self.assert_message_from_report(
            (
                "Running: COMMAND\nEnvironment:\n"
                "--Debug Input Start--\n"
                "STDIN\n"
                "--Debug Input End--\n"
            ),
            reports.run_external_process_started(
                "COMMAND", "STDIN", dict()
            )
        )

    def test_build_message_with_env(self):
        self.assert_message_from_report(
            (
                "Running: COMMAND\nEnvironment:\n"
                "  env_a=A\n"
                "  env_b=B\n"
            ),
            reports.run_external_process_started(
                "COMMAND", "", {"env_a": "A", "env_b": "B",}
            )
        )

    def test_build_message_maximal(self):
        self.assert_message_from_report(
            (
                "Running: COMMAND\nEnvironment:\n"
                "  env_a=A\n"
                "  env_b=B\n"
                "--Debug Input Start--\n"
                "STDIN\n"
                "--Debug Input End--\n"
            ),
            reports.run_external_process_started(
                "COMMAND", "STDIN", {"env_a": "A", "env_b": "B",}
            )
        )

class RunExternalProcessFinished(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Finished running: com-mand\n"
                "Return value: 0\n"
                "--Debug Stdout Start--\n"
                "STDOUT\n"
                "--Debug Stdout End--\n"
                "--Debug Stderr Start--\n"
                "STDERR\n"
                "--Debug Stderr End--\n"
            ),
            reports.run_external_process_finished(
                "com-mand", 0, "STDOUT", "STDERR"
            )
        )

class RunExternalProcessError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unable to run command com-mand: reason",
            reports.run_external_process_error("com-mand", "reason")
        )

    def test_insidious_environment(self):
        self.assert_message_from_report(
            (
                "Running: COMMAND\nEnvironment:\n"
                "  test=a:{green},b:{red}\n"
                "--Debug Input Start--\n"
                "STDIN\n"
                "--Debug Input End--\n"
            ),
            reports.run_external_process_started(
                "COMMAND", "STDIN", {"test": "a:{green},b:{red}",}
            )
        )


class BuildNodeCommunicationStartedTest(NameBuildTest):

    def test_build_message_with_data(self):
        self.assert_message_from_report(
            (
                "Sending HTTP Request to: TARGET\n"
                "--Debug Input Start--\n"
                "DATA\n"
                "--Debug Input End--\n"
            ),
            reports.node_communication_started(
                "TARGET", "DATA"
            )
        )

    def test_build_message_without_data(self):
        self.assert_message_from_report(
            "Sending HTTP Request to: TARGET\n",
            reports.node_communication_started(
                "TARGET", ""
            )
        )

class NodeCommunicationdDebugInfo(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Communication debug info for calling: node1\n"
                "--Debug Communication Info Start--\n"
                "DATA\n"
                "--Debug Communication Info End--\n"
            ),
            reports.node_communication_debug_info("node1", "DATA")
        )

class NodeCommunicationErrorTimedOut(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "node-1: Connection timeout, try setting higher timeout in "
                "--request-timeout option (Connection timed out after 60049 "
                "milliseconds)"
            ),
            reports.node_communication_error_timed_out(
                "node-1",
                "/remote/command",
                "Connection timed out after 60049 milliseconds"
            )
        )

class NodeCommunicationErrorPermissionDenied(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node3: Permission denied (reason)",
            reports.node_communication_error_permission_denied(
                "node3", "com-mand", "reason"
            )
        )

class NodeCommunicationErrorUnsupportedCommand(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Unsupported command (reason), try upgrading pcsd",
            reports.node_communication_error_unsupported_command(
                "node1", "com-mand", "reason"
            )
        )

class NodeCommunicationErrorUnableToConnect(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to connect to node1 (reason)",
            reports.node_communication_error_unable_to_connect(
                "node1", "com-mand", "reason"
            )
        )

class NodeCommunicationErrorOtherError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Error connecting to node1 (reason)",
            reports.node_communication_error_other_error(
                "node1", "com-mand", "reason"
            )
        )

class NodeCommunicationCommandUnsuccessful(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: reason",
            reports.node_communication_command_unsuccessful(
                "node1", "com-mand", "reason"
            )
        )

class InvalidResponseFormat(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Invalid format of response",
            reports.invalid_response_format("node1")
        )

class NodeCommunicationFinished(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Finished calling: node1\n"
                "Response Code: 0\n"
                "--Debug Response Start--\n"
                "DATA\n"
                "--Debug Response End--\n"
            ),
            reports.node_communication_finished("node1", 0, "DATA")
        )

class NodeCommunicationNotConnected(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to connect to node2 (this is reason)",
            reports.node_communication_not_connected("node2", "this is reason")
        )

class NodeCommunicationProxyIsSet(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Proxy is set in environment variables, try disabling it",
            reports.node_communication_proxy_is_set()
        )

    def test_with_node(self):
        self.assert_message_from_report(
            "Proxy is set in environment variables, try disabling it",
            reports.node_communication_proxy_is_set(node="node1")
        )

    def test_with_address(self):
        self.assert_message_from_report(
            "Proxy is set in environment variables, try disabling it",
            reports.node_communication_proxy_is_set(address="aaa")
        )

    def test_all(self):
        self.assert_message_from_report(
            "Proxy is set in environment variables, try disabling it",
            reports.node_communication_proxy_is_set(
                node="node1", address="aaa"
            )
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

@mock.patch("pcs.cli.common.console_report._add_s")
@mock.patch("pcs.cli.common.console_report._is_multiple")
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

class InvalidOptionType(NameBuildTest):
    def test_allowed_string(self):
        self.assert_message_from_report(
            "specified option name is not valid, use allowed types",
            reports.invalid_option_type("option name", "allowed types")
        )

    def test_allowed_list(self):
        self.assert_message_from_report(
            "specified option name is not valid, use 'allowed', 'types'",
            reports.invalid_option_type("option name", ["types", "allowed"])
        )


class DeprecatedOption(NameBuildTest):

    def test_no_desc_hint_array(self):
        self.assert_message_from_report(
            "option 'option name' is deprecated and should not be used,"
                " use new_a, new_b instead"
            ,
            reports.deprecated_option("option name", ["new_b", "new_a"], "")
        )

    def test_desc_hint_string(self):
        self.assert_message_from_report(
            "option type option 'option name' is deprecated and should not be"
                " used, use new option instead"
            ,
            reports.deprecated_option(
                "option name", ["new option"], "option type"
            )
        )


class StonithResourcesDoNotExist(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Stonith resource(s) 'device1', 'device2' do not exist",
            reports.stonith_resources_do_not_exist(["device2", "device1"])
        )

class FencingLevelAlreadyExists(NameBuildTest):
    def test_target_node(self):
        self.assert_message_from_report(
            "Fencing level for 'nodeA' at level '1' with device(s) "
                "'device1', 'device2' already exists",
            reports.fencing_level_already_exists(
                "1", TARGET_TYPE_NODE, "nodeA", ["device2", "device1"]
            )
        )

    def test_target_pattern(self):
        self.assert_message_from_report(
            "Fencing level for 'node-\\d+' at level '1' with device(s) "
                "'device1', 'device2' already exists",
            reports.fencing_level_already_exists(
                "1", TARGET_TYPE_REGEXP, "node-\\d+", ["device1", "device2"]
            )
        )

    def test_target_attribute(self):
        self.assert_message_from_report(
            "Fencing level for 'name=value' at level '1' with device(s) "
                "'device2' already exists",
            reports.fencing_level_already_exists(
                "1", TARGET_TYPE_ATTRIBUTE, ("name", "value"),
                ["device2"]
            )
        )

class FencingLevelDoesNotExist(NameBuildTest):
    def test_full_info(self):
        self.assert_message_from_report(
            "Fencing level for 'nodeA' at level '1' with device(s) "
                "'device1', 'device2' does not exist",
            reports.fencing_level_does_not_exist(
                "1", TARGET_TYPE_NODE, "nodeA", ["device2", "device1"]
            )
        )

    def test_only_level(self):
        self.assert_message_from_report(
            "Fencing level at level '1' does not exist",
            reports.fencing_level_does_not_exist("1", None, None, None)
        )

    def test_only_target(self):
        self.assert_message_from_report(
            "Fencing level for 'name=value' does not exist",
            reports.fencing_level_does_not_exist(
                None, TARGET_TYPE_ATTRIBUTE, ("name", "value"), None
            )
        )

    def test_only_devices(self):
        self.assert_message_from_report(
            "Fencing level with device(s) 'device1' does not exist",
            reports.fencing_level_does_not_exist(
                None, None, None, ["device1"]
            )
        )

    def test_no_info(self):
        self.assert_message_from_report(
            "Fencing level does not exist",
            reports.fencing_level_does_not_exist(None, None, None, None)
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

class MutuallyExclusiveOptions(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Only one of some options 'a' and 'b' can be used",
            reports.mutually_exclusive_options(["b", "a"], "some")
        )

class ResourceIsUnmanaged(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "'R' is unmanaged",
            reports.resource_is_unmanaged("R")
        )

class ResourceManagedNoMonitorEnabled(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Resource 'R' has no enabled monitor operations."
                " Re-run with '--monitor' to enable them."
            ,
            reports.resource_managed_no_monitor_enabled("R")
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


class SbdDevcePathNotAbsolute(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Device path '/dev' on node 'node1' is not absolute",
            reports.sbd_device_path_not_absolute("/dev", "node1")
        )

    def test_build_message_without_node(self):
        self.assert_message_from_report(
            "Device path '/dev' is not absolute",
            reports.sbd_device_path_not_absolute("/dev")
        )


class SbdDeviceDoesNotExist(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "node1: device '/dev' not found",
            reports.sbd_device_does_not_exist("/dev", "node1")
        )


class SbdDeviceISNotBlockDevice(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "node1: device '/dev' is not a block device",
            reports.sbd_device_is_not_block_device("/dev", "node1")
        )

class SbdNotUsedCannotSetSbdOptions(NameBuildTest):
    def test_single_option(self):
        self.assert_message_from_report(
            "Cluster is not configured to use SBD, cannot specify SBD option(s)"
            " 'device' for node 'node1'"
            ,
            reports.sbd_not_used_cannot_set_sbd_options(
                ["device"], "node1"
            )
        )

    def test_multiple_options(self):
        self.assert_message_from_report(
            "Cluster is not configured to use SBD, cannot specify SBD option(s)"
            " 'device', 'watchdog' for node 'node1'"
            ,
            reports.sbd_not_used_cannot_set_sbd_options(
                ["device", "watchdog"], "node1"
            )
        )

class SbdWithDevicesNotUsedCannotSetDevice(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Cluster is not configured to use SBD with shared storage, cannot "
                "specify SBD devices for node 'node1'"
            ,
            reports.sbd_with_devices_not_used_cannot_set_device("node1")
        )

class SbdNoDeviceForNode(NameBuildTest):
    def test_not_enabled(self):
        self.assert_message_from_report(
            "No SBD device specified for node 'node1'",
            reports.sbd_no_device_for_node("node1")
        )

    def test_enabled(self):
        self.assert_message_from_report(
            "Cluster uses SBD with shared storage so SBD devices must be "
                "specified for all nodes, no device specified for node 'node1'"
            ,
            reports.sbd_no_device_for_node(
                "node1",
                sbd_enabled_in_cluster=True
            )
        )


class SbdTooManyDevicesForNode(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "At most 3 SBD devices can be specified for a node, '/dev1', "
                "'/dev2', '/dev3' specified for node 'node1'"
            ,
            reports.sbd_too_many_devices_for_node(
                "node1", ["/dev1", "/dev3", "/dev2"], 3
            )
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

class SbdNotInstalled(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "SBD is not installed on node 'node1'",
            reports.sbd_not_installed("node1")
        )

class UnableToGetSbdStatus(NameBuildTest):
    def test_no_reason(self):
        self.assert_message_from_report(
            "Unable to get status of SBD from node 'node1'",
            reports.unable_to_get_sbd_status("node1", "")
        )

    def test_all(self):
        self.assert_message_from_report(
            "Unable to get status of SBD from node 'node2': reason",
            reports.unable_to_get_sbd_status("node2", "reason")
        )

class RequiredOptionOfAlternativesIsMissing(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            "option 'aAa' or 'bBb' or 'cCc' has to be specified",
            reports.required_option_of_alternatives_is_missing(
                ["aAa", "cCc", "bBb"]
            )
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "test option 'aAa' has to be specified",
            reports.required_option_of_alternatives_is_missing(
                ["aAa"], "test"
            )
        )


class PrerequisiteOptionMustNotBeSet(NameBuildTest):
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
                "a", "b",
                option_type="some",
                prerequisite_type="other",
            )
        )


class PrerequisiteOptionMustBeDisabled(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            "If option 'a' is enabled, option 'b' must be disabled",
            reports.prerequisite_option_must_be_disabled(
                "a", "b"
            )
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "If some option 'a' is enabled, other option 'b' must be disabled",
            reports.prerequisite_option_must_be_disabled(
                "a", "b", "some", "other"
            )
        )


class PrerequisiteOptionMustBeEnabledAsWell(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            "If option 'a' is enabled, option 'b' must be enabled as well",
            reports.prerequisite_option_must_be_enabled_as_well("a", "b")
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "If some option 'a' is enabled, "
                "other option 'b' must be enabled as well"
            ,
            reports.prerequisite_option_must_be_enabled_as_well(
                "a", "b", "some", "other"
            )
        )


class PrerequisiteOptionIsMissing(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            "If option 'a' is specified, option 'b' must be specified as well",
            reports.prerequisite_option_is_missing("a", "b")
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "If some option 'a' is specified, "
                "other option 'b' must be specified as well"
            ,
            reports.prerequisite_option_is_missing(
                "a", "b", "some", "other"
            )
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


class FileDistributionSuccess(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: successful distribution of the file 'some authfile'",
            reports.file_distribution_success("node1", "some authfile")
        )

class FileDistributionError(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: unable to distribute file 'file1': permission denied",
            reports.file_distribution_error(
                "node1", "file1", "permission denied"
            )
        )


class FileRemoveFromNodesStarted(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Requesting remove 'file'",
            reports.files_remove_from_nodes_started(["file"])
        )

    def test_with_single_node(self):
        self.assert_message_from_report(
            "Requesting remove 'first' from 'node1'",
            reports.files_remove_from_nodes_started(["first"], ["node1"])
        )

    def test_with_multiple_nodes(self):
        self.assert_message_from_report(
            "Requesting remove 'first', 'second' from 'node1', 'node2'",
            reports.files_remove_from_nodes_started(
                ["first", "second"],
                ["node1", "node2"],
            )
        )


class FileRemoveFromNodeSuccess(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: successful removal of the file 'some authfile'",
            reports.file_remove_from_node_success(
                "node1", "some authfile"
            )
        )

class FileRemoveFromNodeError(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: unable to remove file 'file1': permission denied",
            reports.file_remove_from_node_error(
                "node1", "file1", "permission denied"
            )
        )


class ServiceCommandsOnNodesStarted(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "Requesting 'action1', 'action2'",
            reports.service_commands_on_nodes_started(
                ["action1", "action2"]
            )
        )

    def test_build_messages_with_single_node(self):
        self.assert_message_from_report(
            "Requesting 'action1' on 'node1'",
            reports.service_commands_on_nodes_started(
                ["action1"],
                ["node1"],
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


class ServiceCommandOnNodeSuccess(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: successful run of 'service enable'",
            reports.service_command_on_node_success(
                "node1", "service enable"
            )
        )

class ServiceCommandOnNodeError(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: service command failed: service1 start: permission denied",
            reports.service_command_on_node_error(
                "node1", "service1 start", "permission denied"
            )
        )

class ResourceIsGuestNodeAlready(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "the resource 'some-resource' is already a guest node",
            reports.resource_is_guest_node_already("some-resource")
        )

class LiveEnvironmentNotConsistent(NameBuildTest):
    def test_one_one(self):
        self.assert_message_from_report(
            (
                "When '--booth-conf' is specified, "
                "'--booth-key' must be specified as well"
            ),
            reports.live_environment_not_consistent(
                [file_type_codes.BOOTH_CONFIG],
                [file_type_codes.BOOTH_KEY],
            )
        )

    def test_many_many(self):
        self.assert_message_from_report(
            (
                "When '--booth-conf', '-f' is specified, "
                "'--booth-key', '--corosync_conf' must be specified as well"
            ),
            reports.live_environment_not_consistent(
                [file_type_codes.CIB, file_type_codes.BOOTH_CONFIG],
                [file_type_codes.COROSYNC_CONF, file_type_codes.BOOTH_KEY],
            )
        )

class LiveEnvironmentRequired(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "This command does not support '--corosync_conf'",
            reports.live_environment_required(["--corosync_conf"])
        )

    def test_build_messages_transformable_codes(self):
        self.assert_message_from_report(
            "This command does not support '--corosync_conf', '-f'",
            reports.live_environment_required(["COROSYNC_CONF", "CIB"])
        )

class LiveEnvironmentRequiredForLocalNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Node(s) must be specified if -f is used",
            reports.live_environment_required_for_local_node()
        )

class CorosyncNodeConflictCheckSkipped(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to check if there is a conflict with nodes set in corosync "
                "because the command does not run on a live cluster (e.g. -f "
                "was used)"
            ,
            reports.corosync_node_conflict_check_skipped("not_live_cib")
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


class FilesRemoveFromNodesSkipped(NameBuildTest):
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
    def test_one_address(self):
        self.assert_message_from_report(
            "Unable to resolve addresses: 'node1'",
            reports.node_addresses_unresolvable(["node1"])
        )

    def test_more_address(self):
        self.assert_message_from_report(
            "Unable to resolve addresses: 'node1', 'node2', 'node3'",
            reports.node_addresses_unresolvable(["node2", "node1", "node3"])
        )

class UnableToPerformOperationOnAnyNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Unable to perform operation on any available node/host, "
                "therefore it is not possible to continue"
            ),
            reports.unable_to_perform_operation_on_any_node()
        )


class NodeNotFound(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "Node 'SOME_NODE' does not appear to exist in configuration",
            reports.node_not_found("SOME_NODE")
        )

    def test_build_messages_with_one_search_types(self):
        self.assert_message_from_report(
            "remote node 'SOME_NODE' does not appear to exist in configuration",
            reports.node_not_found("SOME_NODE", ["remote"])
        )

    def test_build_messages_with_string_search_types(self):
        self.assert_message_from_report(
            "remote node 'SOME_NODE' does not appear to exist in configuration",
            reports.node_not_found("SOME_NODE", "remote")
        )

    def test_build_messages_with_multiple_search_types(self):
        self.assert_message_from_report(
            "nor remote node or guest node 'SOME_NODE' does not appear to exist"
                " in configuration"
            ,
            reports.node_not_found("SOME_NODE", ["remote", "guest"])
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

class UseCommandNodeAddRemote(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "this command is not sufficient for creating a remote connection,"
                " use 'pcs cluster node add-remote'"
            ,
            reports.use_command_node_add_remote()
        )

class UseCommandNodeAddGuest(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "this command is not sufficient for creating a guest node, use "
            "'pcs cluster node add-guest'",
            reports.use_command_node_add_guest()
        )

class UseCommandNodeRemoveGuest(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "this command is not sufficient for removing a guest node, use "
            "'pcs cluster node remove-guest'",
            reports.use_command_node_remove_guest()
        )

class PaceMakerLocalNodeNotFound(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unable to get local node name from pacemaker: reason",
            reports.pacemaker_local_node_name_not_found("reason")
        )

class NodeRemoveInPacemakerFailed(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            (
                "Unable to remove node(s) 'NODE1', 'NODE2' from "
                "pacemaker"
            ),
            reports.node_remove_in_pacemaker_failed(
                ["NODE2", "NODE1"]
            )
        )

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
    def test_build_messages(self):
        self.assert_message_from_report(
            "node 'node1' seems to be still in the cluster"
                "; this command should be used only with nodes that have been"
                " removed from the cluster"
            ,
            reports.node_to_clear_is_still_in_cluster("node1")
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


class CibAlertRecipientAlreadyExists(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Recipient 'recipient' in alert 'alert-id' already exists",
            reports.cib_alert_recipient_already_exists("alert-id", "recipient")
        )


class CibAlertRecipientInvalidValue(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Recipient value 'recipient' is not valid.",
            reports.cib_alert_recipient_invalid_value("recipient")
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


class TmpFileWrite(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Writing to a temporary file /tmp/pcs/test.tmp:\n"
                "--Debug Content Start--\n"
                "test file\ncontent\n\n"
                "--Debug Content End--\n"
            ),
            reports.tmp_file_write(
                "/tmp/pcs/test.tmp", "test file\ncontent\n"
            )
        )


class DefaultsCanBeOverriden(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "Defaults do not apply to resources which override them with "
                "their own defined values"
            ),
            reports.defaults_can_be_overriden()
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

class CorosyncAddressIpVersionWrongForLink(NameBuildTest):
    def test_without_links(self):
        self.assert_message_from_report(
            "Address '192.168.100.42' cannot be used in the link because "
                "the link uses IPv6 addresses"
            ,
            reports.corosync_address_ip_version_wrong_for_link(
                "192.168.100.42", "IPv6",
            )
        )

    def test_with_links(self):
        self.assert_message_from_report(
            "Address '192.168.100.42' cannot be used in link '3' because "
                "the link uses IPv6 addresses"
            ,
            reports.corosync_address_ip_version_wrong_for_link(
                "192.168.100.42", "IPv6", 3,
            )
        )

class CorosyncOptionsIncompatibleWithQdevice(NameBuildTest):
    def test_single_option(self):
        self.assert_message_from_report(
            "These options cannot be set when the cluster uses a quorum "
            "device: option1",
            reports.corosync_options_incompatible_with_qdevice(["option1"])
        )

    def test_multiple_options(self):
        self.assert_message_from_report(
            "These options cannot be set when the cluster uses a quorum "
            "device: option1, option2, option3",
            reports.corosync_options_incompatible_with_qdevice(
                ["option3", "option1", "option2"]
            )
        )

class CorosyncBadNodeAddressesCount(NameBuildTest):
    def test_no_node_info(self):
        self.assert_message_from_report(
            "At least 1 and at most 4 addresses must be specified for a node, "
            "5 addresses specified",
            reports.corosync_bad_node_addresses_count(5, 1, 4)
        )

    def test_node_name(self):
        self.assert_message_from_report(
            "At least 1 and at most 4 addresses must be specified for a node, "
            "5 addresses specified for node 'node1'",
            reports.corosync_bad_node_addresses_count(5, 1, 4, "node1")
        )

    def test_node_id(self):
        self.assert_message_from_report(
            "At least 1 and at most 4 addresses must be specified for a node, "
            "5 addresses specified for node '2'",
            reports.corosync_bad_node_addresses_count(
                5, 1, 4,
                node_index=2
            )
        )

    def test_node_name_and_id(self):
        self.assert_message_from_report(
            "At least 1 and at most 4 addresses must be specified for a node, "
            "5 addresses specified for node 'node2'",
            reports.corosync_bad_node_addresses_count(5, 1, 4, "node2", 2)
        )

    def test_one_address_allowed(self):
        self.assert_message_from_report(
            "At least 0 and at most 1 address must be specified for a node, "
            "2 addresses specified for node 'node2'",
            reports.corosync_bad_node_addresses_count(2, 0, 1, "node2", 2)
        )

    def test_one_address_specified(self):
        self.assert_message_from_report(
            "At least 2 and at most 4 addresses must be specified for a node, "
            "1 address specified for node 'node2'",
            reports.corosync_bad_node_addresses_count(1, 2, 4, "node2", 2)
        )

    def test_exactly_one_address_allowed(self):
        self.assert_message_from_report(
            "1 address must be specified for a node, "
            "2 addresses specified for node 'node2'",
            reports.corosync_bad_node_addresses_count(2, 1, 1, "node2", 2)
        )

    def test_exactly_two_addresses_allowed(self):
        self.assert_message_from_report(
            "2 addresses must be specified for a node, "
            "1 address specified for node 'node2'",
            reports.corosync_bad_node_addresses_count(1, 2, 2, "node2", 2)
        )


class CorosyncIpVersionMismatchInLinks(NameBuildTest):
    def test_without_links(self):
        self.assert_message_from_report(
            "Using both IPv4 and IPv6 on one link is not allowed; please, use "
                "either IPv4 or IPv6"
            ,
            reports.corosync_ip_version_mismatch_in_links()
        )

    def test_with_single_link(self):
        self.assert_message_from_report(
            "Using both IPv4 and IPv6 on one link is not allowed; please, use "
                "either IPv4 or IPv6 on link(s): '3'"
            ,
            reports.corosync_ip_version_mismatch_in_links(["3"])
        )

    def test_with_links(self):
        self.assert_message_from_report(
            "Using both IPv4 and IPv6 on one link is not allowed; please, use "
                "either IPv4 or IPv6 on link(s): '0', '3', '4'"
            ,
            reports.corosync_ip_version_mismatch_in_links(["3", "0", "4"])
        )


class CorosyncNodeAddressCountMismatch(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "All nodes must have the same number of addresses; "
                "nodes 'node3', 'node4', 'node6' have 1 address; "
                "nodes 'node2', 'node5' have 3 addresses; "
                "node 'node1' has 2 addresses"
            ,
            reports.corosync_node_address_count_mismatch(
                {
                    "node1": 2,
                    "node2": 3,
                    "node3": 1,
                    "node4": 1,
                    "node5": 3,
                    "node6": 1,
                }
            )
        )


class CorosyncLinkNumberDuplication(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Link numbers must be unique, duplicate link numbers: '1', '3'",
            reports.corosync_link_number_duplication(["1", "3"])
        )

class NodeAddressesAlreadyExist(NameBuildTest):
    def test_one_address(self):
        self.assert_message_from_report(
            "Node address 'node1' is already used by existing nodes; please, "
            "use other address",
            reports.node_addresses_already_exist(["node1"])
        )

    def test_more_addresses(self):
        self.assert_message_from_report(
            "Node addresses 'node1', 'node3' are already used by existing "
            "nodes; please, use other addresses",
            reports.node_addresses_already_exist(["node1", "node3"])
        )

class NodeAddressesCannotBeEmpty(NameBuildTest):
    def test_one_node(self):
        self.assert_message_from_report(
            (
                "Empty address set for node 'node2', "
                "an address cannot be empty"
            ),
            reports.node_addresses_cannot_be_empty(["node2"])
        )

    def test_more_nodes(self):
        self.assert_message_from_report(
            (
                "Empty address set for nodes 'node1', 'node2', "
                "an address cannot be empty"
            ),
            reports.node_addresses_cannot_be_empty(["node2", "node1"])
        )

class NodeAddressesDuplication(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Node addresses must be unique, duplicate addresses: "
                "'node1', 'node3'"
            ,
            reports.node_addresses_duplication(["node1", "node3"])
        )

class NodeNamesAlreadyExist(NameBuildTest):
    def test_one_address(self):
        self.assert_message_from_report(
            "Node name 'node1' is already used by existing nodes; please, "
            "use other name",
            reports.node_names_already_exist(["node1"])
        )

    def test_more_addresses(self):
        self.assert_message_from_report(
            "Node names 'node1', 'node3' are already used by existing "
            "nodes; please, use other names",
            reports.node_names_already_exist(["node1", "node3"])
        )

class NodeNamesDuplication(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Node names must be unique, duplicate names: 'node1', 'node3'",
            reports.node_names_duplication(["node1", "node3"])
        )


class CorosyncNotRunningCheckStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Checking corosync is not running on nodes...",
            reports.corosync_not_running_check_started()
        )

class CorosyncNotRunningCheckNodeError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Unable to check if corosync is not running",
            reports.corosync_not_running_check_node_error("node1")
        )

class CorosyncNotRunningOnNodeOk(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node2: corosync is not running",
            reports.corosync_not_running_on_node_ok("node2")
        )

class CorosyncRunningOnNodeFail(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node3: corosync is running",
            reports.corosync_running_on_node_fail("node3")
        )

class CorosyncNodesMissing(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "No nodes have been specified",
            reports.corosync_nodes_missing()
        )


class CorosyncQuorumHeuristicsEnabledWithNoExec(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "No exec_NAME options are specified, so heuristics are effectively "
                "disabled",
            reports.corosync_quorum_heuristics_enabled_with_no_exec()
        )


class CorosyncQuorumSetExpectedVotesError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to set expected votes: reason",
            reports.corosync_quorum_set_expected_votes_error("reason")
        )

class CorosyncQuorumWillBeLost(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "This action will cause a loss of the quorum",
            reports.corosync_quorum_will_be_lost()
        )

class CorosyncQuorumLossUnableToCheck(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Unable to determine whether this action will cause "
                "a loss of the quorum"
            ),
            reports.corosync_quorum_loss_unable_to_check()
        )

class CorosyncTooManyLinksOptions(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "Cannot specify options for more links (7) than how many is "
                "defined by number of addresses per node (3)"
            ),
            reports.corosync_too_many_links_options(7, 3),
        )

class CorosyncCannotAddRemoveLinksBadTransport(NameBuildTest):
    def test_add(self):
        self.assert_message_from_report(
            (
                "Cluster is using udp transport which does not support "
                "adding links"
            ),
            reports.corosync_cannot_add_remove_links_bad_transport(
                "udp",
                ["knet1", "knet2"],
                add_or_not_remove=True
            )
        )

    def test_remove(self):
        self.assert_message_from_report(
            (
                "Cluster is using udpu transport which does not support "
                "removing links"
            ),
            reports.corosync_cannot_add_remove_links_bad_transport(
                "udpu",
                ["knet"],
                add_or_not_remove=False
            )
        )

class CorosyncCannotAddRemoveLinksNoLinksSpecified(NameBuildTest):
    def test_add(self):
        self.assert_message_from_report(
            "Cannot add links, no links to add specified",
            reports.corosync_cannot_add_remove_links_no_links_specified(
                add_or_not_remove=True
            )
        )

    def test_remove(self):
        self.assert_message_from_report(
            "Cannot remove links, no links to remove specified",
            reports.corosync_cannot_add_remove_links_no_links_specified(
                add_or_not_remove=False
            )
        )

class CorosyncCannotAddRemoveLinksTooManyFewLinks(NameBuildTest):
    def test_add(self):
        self.assert_message_from_report(
            (
                "Cannot add 1 link, there would be 1 link defined which is "
                "more than allowed number of 1 link"
            ),
            reports.corosync_cannot_add_remove_links_too_many_few_links(
                1, 1, 1,
                add_or_not_remove=True
            )
        )

    def test_add_s(self):
        self.assert_message_from_report(
            (
                "Cannot add 2 links, there would be 4 links defined which is "
                "more than allowed number of 3 links"
            ),
            reports.corosync_cannot_add_remove_links_too_many_few_links(
                2, 4, 3,
                add_or_not_remove=True
            )
        )

    def test_remove(self):
        self.assert_message_from_report(
            (
                "Cannot remove 1 link, there would be 1 link defined which is "
                "less than allowed number of 1 link"
            ),
            reports.corosync_cannot_add_remove_links_too_many_few_links(
                1, 1, 1,
                add_or_not_remove=False
            )
        )

    def test_remove_s(self):
        self.assert_message_from_report(
            (
                "Cannot remove 3 links, there would be 0 links defined which "
                "is less than allowed number of 2 links"
            ),
            reports.corosync_cannot_add_remove_links_too_many_few_links(
                3, 0, 2,
                add_or_not_remove=False
            )
        )

class CorosyncLinkAlreadyExistsCannotAdd(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot add link '2', it already exists",
            reports.corosync_link_already_exists_cannot_add("2")
        )

class CorosyncLinkDoesNotExistCannotRemove(NameBuildTest):
    def test_single_link(self):
        self.assert_message_from_report(
            (
                "Cannot remove non-existent link 'abc', existing "
                "links: '5'"
            ),
            reports.corosync_link_does_not_exist_cannot_remove(
                ["abc"], ["5"]
            )
        )

    def test_multiple_links(self):
        self.assert_message_from_report(
            (
                "Cannot remove non-existent links '0', '1', 'abc', existing "
                "links: '2', '3', '5'"
            ),
            reports.corosync_link_does_not_exist_cannot_remove(
                ["1", "0", "abc"], ["3", "2", "5"]
            )
        )

class CorosyncLinkDoesNotExistCannotUpdate(NameBuildTest):
    def test_link_list_several(self):
        self.assert_message_from_report(
            (
                "Cannot set options for non-existent link '3'"
                ", existing links: '0', '1', '2', '6', '7'"
            ),
            reports.corosync_link_does_not_exist_cannot_update(
                3, ["6", "7", "0", "1", "2"]
            )
        )

    def test_link_list_one(self):
        self.assert_message_from_report(
            (
                "Cannot set options for non-existent link '3'"
                ", existing links: '0'"
            ),
            reports.corosync_link_does_not_exist_cannot_update(
                3, ["0"]
            )
        )


class CorosyncTransportUnsupportedOptions(NameBuildTest):
    def test_udp(self):
        self.assert_message_from_report(
            "The udp/udpu transport does not support 'crypto' options, use "
                "'knet' transport"
            ,
            reports.corosync_transport_unsupported_options(
                "crypto", "udp/udpu", ["knet"]
            )
        )

    def test_multiple_supported_transports(self):
        self.assert_message_from_report(
            "The udp/udpu transport does not support 'crypto' options, use "
            "'knet', 'knet2' transport"
            ,
            reports.corosync_transport_unsupported_options(
                "crypto", "udp/udpu", ["knet", "knet2"]
            )
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

class CibUpgradeSuccessful(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "CIB has been upgraded to the latest schema version.",
            reports.cib_upgrade_successful()
        )

class CibUpgradeFailed(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Upgrading of CIB to the latest schema failed: reason",
            reports.cib_upgrade_failed("reason")
        )

class UnableToUpgradeCibToRequiredVersion(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Unable to upgrade CIB to required schema version"
                " 1.1 or higher. Current version is"
                " 0.8. Newer version of pacemaker is needed."
            ),
            reports.unable_to_upgrade_cib_to_required_version("0.8", "1.1")
        )

class NodeCommunicationRetrying(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Unable to connect to 'node_name' via address 'failed.address' "
                "and port '2224'. Retrying request 'my/request' via address "
                "'next.address' and port '2225'"
            ),
            reports.node_communication_retrying(
                "node_name", "failed.address", "2224", "next.address", "2225",
                "my/request",
            )
        )

class NodeCommunicationNoMoreAddresses(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to connect to 'node_name' via any of its addresses",
            reports.node_communication_no_more_addresses(
                "node_name",
                "my/request",
            )
        )

class HostNotFound(NameBuildTest):
    def test_single_host(self):
        self.assert_message_from_report(
            (
                "Host 'unknown_host' is not known to pcs, try to authenticate "
                "the host using 'pcs host auth unknown_host' command"
            ),
            reports.host_not_found(["unknown_host"])
        )

    def test_multiple_hosts(self):
        self.assert_message_from_report(
            (
                "Hosts 'another_one', 'unknown_host' are not known to pcs, try "
                "to authenticate the hosts using 'pcs host auth another_one "
                "unknown_host' command"
            ),
            reports.host_not_found(["unknown_host", "another_one"])
        )

class NoneHostFound(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "None of hosts is known to pcs.",
            reports.none_host_found()
        )

class HostAlreadyAuthorized(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "host: Already authorized",
            reports.host_already_authorized("host")
        )

class NodeCommunicationErrorNotAuthorized(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Unable to authenticate to node1 (some error), try running "
                "'pcs host auth node1'"
            ),
            reports.node_communication_error_not_authorized(
                "node1", "some-command", "some error"
            )
        )

class ClusterWillBeDestroyed(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Some nodes are already in a cluster. Enforcing this will "
                "destroy existing cluster on those nodes. You should remove "
                "the nodes from their clusters instead to keep the clusters "
                "working properly"
            ),
            reports.cluster_will_be_destroyed()
        )

class ClusterDestroyStarted(NameBuildTest):
    def test_multiple_hosts(self):
        self.assert_message_from_report(
            "Destroying cluster on hosts: 'node1', 'node2', 'node3'...",
            reports.cluster_destroy_started(["node1", "node3", "node2"])
        )

    def test_single_host(self):
        self.assert_message_from_report(
            "Destroying cluster on hosts: 'node1'...",
            reports.cluster_destroy_started(["node1"])
        )

class ClusterDestroySuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "node1: Successfully destroyed cluster",
            reports.cluster_destroy_success("node1")
        )

class ClusterEnableStarted(NameBuildTest):
    def test_multiple_hosts(self):
        self.assert_message_from_report(
            "Enabling cluster on hosts: 'node1', 'node2', 'node3'...",
            reports.cluster_enable_started(["node1", "node3", "node2"])
        )

    def test_single_host(self):
        self.assert_message_from_report(
            "Enabling cluster on hosts: 'node1'...",
            reports.cluster_enable_started(["node1"])
        )

class ClusterEnableSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "node1: Cluster enabled",
            reports.cluster_enable_success("node1")
        )

class ClusterStartStarted(NameBuildTest):
    def test_multiple_hosts(self):
        self.assert_message_from_report(
            "Starting cluster on hosts: 'node1', 'node2', 'node3'...",
            reports.cluster_start_started(["node1", "node3", "node2"])
        )

    def test_single_host(self):
        self.assert_message_from_report(
            "Starting cluster on hosts: 'node1'...",
            reports.cluster_start_started(["node1"])
        )

class ClusterStartSuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Cluster started",
            reports.cluster_start_success("node1")
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

class ClusterRestartRequiredToApplyChanges(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Cluster restart is required in order to apply these changes.",
            reports.cluster_restart_required_to_apply_changes()
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

class ServiceNotInstalled(NameBuildTest):
    def test_multiple_services(self):
        self.assert_message_from_report(
            "node1: Required cluster services not installed: 'service1', "
                "'service2', 'service3'"
            ,
            reports.service_not_installed(
                "node1", ["service1", "service3", "service2"]
            )
        )

    def test_single_service(self):
        self.assert_message_from_report(
            "node1: Required cluster services not installed: 'service'",
            reports.service_not_installed(
                "node1", ["service"]
            )
        )


class HostAlreadyInClusterConfig(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "host: Cluster configuration files found, the host seems to be in "
                "a cluster already"
            ,
            reports.host_already_in_cluster_config("host")
        )


class HostAlreadyInClusterServices(NameBuildTest):
    def test_multiple_services(self):
        self.assert_message_from_report(
            (
                "node1: Running cluster services: 'service1', 'service2', "
                "'service3', the host seems to be in a cluster already"
            ),
            reports.host_already_in_cluster_services(
                "node1", ["service1", "service3", "service2"]
            )
        )

    def test_single_service(self):
        self.assert_message_from_report(
            "node1: Running cluster services: 'service', the host seems to be "
                "in a cluster already"
            ,
            reports.host_already_in_cluster_services(
                "node1", ["service"]
            )
        )


class ServiceVersionMismatch(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Hosts do not have the same version of 'service'; "
                "hosts 'host4', 'host5', 'host6' have version 2.0; "
                "hosts 'host1', 'host3' have version 1.0; "
                "host 'host2' has version 1.2"
            ,
            reports.service_version_mismatch(
                "service",
                {
                    "host1": 1.0,
                    "host2": 1.2,
                    "host3": 1.0,
                    "host4": 2.0,
                    "host5": 2.0,
                    "host6": 2.0,
                }
            )
        )

class WaitForNodeStartupStarted(NameBuildTest):
    def test_single_node(self):
        self.assert_message_from_report(
            "Waiting for node(s) to start: 'node1'...",
            reports.wait_for_node_startup_started(["node1"])
        )

    def test_multiple_nodes(self):
        self.assert_message_from_report(
            "Waiting for node(s) to start: 'node1', 'node2', 'node3'...",
            reports.wait_for_node_startup_started(["node3", "node2", "node1"])
        )

class WaitForNodeStartupTimedOut(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Node(s) startup timed out",
            reports.wait_for_node_startup_timed_out()
        )

class WaitForNodeStartupError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to verify all nodes have started",
            reports.wait_for_node_startup_error()
        )

class WaitForNodeStartupWithoutStart(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Cannot specify '--wait' without specifying '--start'",
            reports.wait_for_node_startup_without_start()
        )

class PcsdVersionTooOld(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "node1: Old version of pcsd is running on the node, therefore "
                "it is unable to perform the action"
            ),
            reports.pcsd_version_too_old("node1")
        )

class PcsdSslCertAndKeyDistributionStarted(NameBuildTest):
    def test_multiple_nodes(self):
        self.assert_message_from_report(
            "Synchronizing pcsd SSL certificates on node(s) 'node1', 'node2', "
                "'node3'..."
            ,
            reports.pcsd_ssl_cert_and_key_distribution_started(
                ["node1", "node3", "node2"]
            )
        )

    def test_single_node(self):
        self.assert_message_from_report(
            "Synchronizing pcsd SSL certificates on node(s) 'node3'..."
            ,
            reports.pcsd_ssl_cert_and_key_distribution_started(
                ["node3"]
            )
        )

class PcsdSslCertAndKeySetSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "node1: Success",
            reports.pcsd_ssl_cert_and_key_set_success("node1")
        )

class UsingKnownHostAddressForHost(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "No addresses specified for host 'node-name', using 'node-addr'",
            reports.using_known_host_address_for_host("node-name", "node-addr")
        )

class ResourceInBundleNotAccessible(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Resource 'resourceA' will not be accessible by the cluster "
                "inside bundle 'bundleA', at least one of bundle options "
                "'control-port' or 'ip-range-start' has to be specified"
            ),
            reports.resource_in_bundle_not_accessible("bundleA", "resourceA")
        )

class FileAlreadyExists(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Corosync authkey file '/etc/corosync/key' already exists",
            reports.file_already_exists("COROSYNC_AUTHKEY", "/etc/corosync/key")
        )

    def test_with_node(self):
        self.assert_message_from_report(
            "node1: pcs configuration file '/var/lib/pcsd/conf' already exists",
            reports.file_already_exists(
                "PCS_SETTINGS_CONF", "/var/lib/pcsd/conf",
                node="node1"
            )
        )

class FileIoError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to read Booth configuration: ",
            reports.file_io_error(
                file_type_codes.BOOTH_CONFIG,
                RawFileError.ACTION_READ,
                ""
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "Unable to read pcsd SSL certificate '/var/lib/pcsd.crt': Failed",
            reports.file_io_error(
                file_type_codes.PCSD_SSL_CERT,
                RawFileError.ACTION_READ,
                "Failed",
                file_path="/var/lib/pcsd.crt",
            )
        )

    def test_role_translation_a(self):
        self.assert_message_from_report(
            "Unable to write pcsd SSL key '/var/lib/pcsd.key': Failed",
            reports.file_io_error(
                file_type_codes.PCSD_SSL_KEY,
                RawFileError.ACTION_WRITE,
                "Failed",
                file_path="/var/lib/pcsd.key",
            )
        )

    def test_role_translation_b(self):
        self.assert_message_from_report(
            (
                "Unable to change ownership of pcsd configuration "
                "'/etc/sysconfig/pcsd': Failed"
            ),
            reports.file_io_error(
                file_type_codes.PCSD_ENVIRONMENT_CONFIG,
                RawFileError.ACTION_CHOWN,
                "Failed",
                file_path="/etc/sysconfig/pcsd",
            )
        )

    def test_role_translation_c(self):
        self.assert_message_from_report(
            "Unable to change permissions of Corosync authkey: Failed",
            reports.file_io_error(
                file_type_codes.COROSYNC_AUTHKEY,
                RawFileError.ACTION_CHMOD,
                "Failed",
            )
        )

    def test_role_translation_d(self):
        self.assert_message_from_report(
            (
                "Unable to change ownership of pcs configuration: "
                "Permission denied"
            ),
            reports.file_io_error(
                file_type_codes.PCS_SETTINGS_CONF,
                RawFileError.ACTION_CHOWN,
                "Permission denied",
            )
        )

class UsingDefaultWatchdog(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "No watchdog has been specified for node 'node1'. Using "
                "default watchdog '/dev/watchdog'"
            ),
            reports.using_default_watchdog("/dev/watchdog", "node1")
        )

class WatchdogNotFound(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Watchdog 'watchdog-name' does not exist on node 'node1'",
            reports.watchdog_not_found("node1", "watchdog-name")
        )

class InvalidWatchdogName(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Watchdog path '/dev/wdog' is invalid.",
            reports.invalid_watchdog_path("/dev/wdog")
        )

class CorosyncQuorumAtbCannotBeDisabledDueToSbd(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Unable to disable auto_tie_breaker, SBD fencing would have no "
                "effect"
            ),
            reports.corosync_quorum_atb_cannot_be_disabled_due_to_sbd()
        )

class CorosyncQuorumAtbWillBeEnabledDueToSbd(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "auto_tie_breaker quorum option will be enabled to make SBD "
                "fencing effective. Cluster has to be offline to be able to "
                "make this change."
            ),
            reports.corosync_quorum_atb_will_be_enabled_due_to_sbd()
        )


class CorosyncConfigDistributionStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Sending updated corosync.conf to nodes...",
            reports.corosync_config_distribution_started()
        )

class CorosyncConfigAcceptedByNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Succeeded",
            reports.corosync_config_accepted_by_node("node1")
        )

class CorosyncConfigDistributionNodeError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Unable to set corosync config",
            reports.corosync_config_distribution_node_error("node1")
        )

class CorosyncConfigReloaded(NameBuildTest):
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
    def test_success(self):
        self.assert_message_from_report(
            (
                "node1: Corosync is not running, therefore reload of the "
                "corosync configuration is not possible"
            ),
            reports.corosync_config_reload_not_possible("node1")
        )


class CorosyncConfigReloadError(NameBuildTest):
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

class CorosyncConfigMissingNamesOfNodes(NameBuildTest):
    def test_non_fatal(self):
        self.assert_message_from_report(
            "Some nodes are missing names in corosync.conf, "
                "those nodes were omitted",
            reports.corosync_config_missing_names_of_nodes()
        )

    def test_fatal(self):
        self.assert_message_from_report(
            "Some nodes are missing names in corosync.conf, "
                "unable to continue",
            reports.corosync_config_missing_names_of_nodes(
                fatal=True
            )
        )

class CorosyncConfigNoNodesDefined(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "No nodes found in corosync.conf",
            reports.corosync_config_no_nodes_defined()
        )

class CorosyncConfigReadError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to read /dev/path: this is reason",
            reports.corosync_config_read_error("/dev/path", "this is reason")
        )

class CorosyncConfigParserMissingClosingBrace(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config: missing closing brace",
            reports.corosync_config_parser_missing_closing_brace()
        )

class CorosyncConfigParserUnexpectedClosingBrace(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config: unexpected closing brace",
            reports.corosync_config_parser_unexpected_closing_brace()
        )

class CorosyncConfigParserMissingSectionNameBeforeOpeningBrace(NameBuildTest):
    def test_all(self):
        # pylint: disable=line-too-long
        self.assert_message_from_report(
            "Unable to parse corosync config: missing a section name before {",
            reports.corosync_config_parser_missing_section_name_before_opening_brace()
        )

class CorosyncConfigParserExtraCharactersAfterOpeningBrace(NameBuildTest):
    def test_all(self):
        # pylint: disable=line-too-long
        self.assert_message_from_report(
            "Unable to parse corosync config: extra characters after {",
            reports.corosync_config_parser_extra_characters_after_opening_brace()
        )

class CorosyncConfigParserExtraCharsBeforeOrAfterClosingBrace(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            # pylint: disable=line-too-long
            (
                "Unable to parse corosync config: extra characters before "
                "or after }"
            ),
            reports.corosync_config_parser_extra_characters_before_or_after_closing_brace()
        )

class CorosyncConfigParserLineIsNotSectionNorKeyValue(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config: a line is not opening or closing "
            "a section or key: value",
            reports.corosync_config_parser_line_is_not_section_nor_key_value()
        )

class CorosyncConfigParserOtherError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config",
            reports.corosync_config_parser_other_error()
        )

class CannotRemoveAllClusterNodes(NameBuildTest):
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
    def test_success(self):
        self.assert_message_from_report(
            (
                "Node 'node2' with id '2' is used as a tie breaker for a "
                "qdevice, run 'pcs quorum device update model "
                "tie_breaker=<node id>' to change it"
            ),
            reports.node_used_as_tie_breaker("node2", 2)
        )

class UnableToConnectToAnyRemainingNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to connect to any remaining cluster node",
            reports.unable_to_connect_to_any_remaining_node()
        )

class UnableToConnectToAllRemainingNodes(NameBuildTest):
    def test_single_node(self):
        self.assert_message_from_report(
            (
                "Remaining cluster node 'node1' could not be reached, run "
                "'pcs cluster sync' on any currently online node "
                "once the unreachable one become available"
            ),
            reports.unable_to_connect_to_all_remaining_node(["node1"])
        )

    def test_multiple_nodes(self):
        self.assert_message_from_report(
            (
                "Remaining cluster nodes 'node0', 'node1', 'node2' could not "
                "be reached, run 'pcs cluster sync' on any currently online "
                "node once the unreachable ones become available"
            ),
            reports.unable_to_connect_to_all_remaining_node(
                ["node1", "node0", "node2"]
            )
        )

class NodesToRemoveUnreachable(NameBuildTest):
    def test_single_node(self):
        self.assert_message_from_report(
            (
                "Removed node 'node0' could not be reached and subsequently "
                "deconfigured. Run 'pcs cluster destroy' on the unreachable "
                "node."
            ),
            reports.nodes_to_remove_unreachable(["node0"])
        )

    def test_multiple_nodes(self):
        self.assert_message_from_report(
            (
                "Removed nodes 'node0', 'node1', 'node2' could not be reached "
                "and subsequently deconfigured. Run 'pcs cluster destroy' "
                "on the unreachable nodes."
            ),
            reports.nodes_to_remove_unreachable(["node1", "node0", "node2"])
        )

class CorosyncQuorumGetStatusError(NameBuildTest):
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
    def test_success(self):
        self.assert_message_from_report(
            "Unable to query available watchdogs from sbd: this is a reason",
            reports.sbd_list_watchdog_error("this is a reason"),
        )


class SbdWatchdogNotSupported(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "node1: Watchdog '/dev/watchdog' is not supported (it may be a "
                "software watchdog)"
            ),
            reports.sbd_watchdog_not_supported("node1", "/dev/watchdog"),
        )

class SbdWatchdogValidationInactive(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Not validating the watchdog",
            reports.sbd_watchdog_validation_inactive()
        )


class SbdWatchdogTestError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to initialize test of the watchdog: some reason",
            reports.sbd_watchdog_test_error("some reason"),
        )


class SbdWatchdogTestMultipleDevices(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Multiple watchdog devices available, therefore, watchdog "
                "which should be tested has to be specified. To list available "
                "watchdog devices use command 'pcs stonith sbd watchdog list'"
            ),
            reports.sbd_watchdog_test_multiple_devices()
        )


class SbdWatchdogTestFailed(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "System should have been reset already",
            reports.sbd_watchdog_test_failed()
        )


class ResourceBundleUnsupportedContainerType(NameBuildTest):
    def test_single_type(self):
        self.assert_message_from_report(
            (
                "Bundle 'bundle id' uses unsupported container type, therefore "
                "it is not possible to set its container options. Supported "
                "container types are: 'b'"
            ),
            reports.resource_bundle_unsupported_container_type(
                "bundle id", ["b"]
            ),
        )

    def test_multiple_types(self):
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
    def test_success(self):
        self.assert_message_from_report(
            "Unable to show fence history: reason",
            reports.fence_history_command_error("reason", "show")
        )

class FenceHistoryNotSupported(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Fence history is not supported, please upgrade pacemaker",
            reports.fence_history_not_supported()
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

class ResourceForConstraintIsMultiinstance(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "resource1 is a bundle resource, you should use the "
                "bundle id: parent1 when adding constraints"
            ),
            reports.resource_for_constraint_is_multiinstance(
                "resource1", "bundle", "parent1"
            )
        )

class ResourceInstanceAttrValueNotUnique(NameBuildTest):
    def test_one_resource(self):
        self.assert_message_from_report(
            (
                "Value 'val' of option 'attr' is not unique across 'agent' "
                "resources. Following resources are configured with the same "
                "value of the instance attribute: 'A'"
            ),
            reports.resource_instance_attr_value_not_unique(
                "attr", "val", "agent", ["A"]
            )
        )

    def test_multiple_resources(self):
        self.assert_message_from_report(
            (
                "Value 'val' of option 'attr' is not unique across 'agent' "
                "resources. Following resources are configured with the same "
                "value of the instance attribute: 'A', 'B', 'C'"
            ),
            reports.resource_instance_attr_value_not_unique(
                "attr", "val", "agent", ["B", "C", "A"]
            )
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

class CannotMoveResourceBundle(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "cannot move bundle resources",
            reports.cannot_move_resource_bundle("R")
        )

class CannotMoveResourceClone(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "cannot move cloned resources",
            reports.cannot_move_resource_clone("R")
        )

class CannotMoveResourceMasterResourceNotPromotable(NameBuildTest):
    def test_without_promotable(self):
        self.assert_message_from_report(
            "when specifying --master you must use the promotable clone id",
            reports.cannot_move_resource_master_resource_not_promotable("R")
        )

    def test_with_promotable(self):
        self.assert_message_from_report(
            "when specifying --master you must use the promotable clone id (P)",
            reports.cannot_move_resource_master_resource_not_promotable(
                "R",
                promotable_id="P"
            )
        )

class CannotMoveResourcePromotableNotMaster(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "to move promotable clone resources you must use --master and "
                "the promotable clone id (P)"
            ),
            reports.cannot_move_resource_promotable_not_master("R", "P")
        )

class CannotMoveResourceStoppedNoNodeSpecified(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "You must specify a node when moving/banning a stopped resource",
            reports.cannot_move_resource_stopped_no_node_specified("R")
        )

class EmptyResourceSetList(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Resource set list is empty",
            reports.empty_resource_set_list()
        )

class ResourceMovePcmkEerror(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "cannot move resource 'R'\nstdout1\n  stdout2\nstderr1\n  stderr2",
            reports.resource_move_pcmk_error(
                "R",
                "stdout1\n\n  stdout2\n",
                "stderr1\n\n  stderr2\n"
            )
        )

class ResourceMovePcmkSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "stdout1\n  stdout2\nstderr1\n  stderr2",
            reports.resource_move_pcmk_success(
                "R",
                "stdout1\n\n  stdout2\n",
                "stderr1\n\n  stderr2\n"
            )
        )

    def test_translate(self):
        self.assert_message_from_report(
            (
                "Warning: Creating location constraint "
                    "'cli-ban-dummy-on-node1' with a score of -INFINITY "
                    "for resource dummy on node1.\n"
                "	This will prevent dummy from running on node1 until the "
                    "constraint is removed\n"
                "	This will be the case even if node1 is the last node in "
                    "the cluster"
            ),
            reports.resource_move_pcmk_success(
                "dummy",
                "",
                (
                    "WARNING: Creating rsc_location constraint "
                        "'cli-ban-dummy-on-node1' with a score of -INFINITY "
                        "for resource dummy on node1.\n"
                    "	This will prevent dummy from running on node1 until "
                        "the constraint is removed using the clear option or "
                        "by editing the CIB with an appropriate tool\n"
                    "	This will be the case even if node1 is the last node "
                        "in the cluster\n"
                )
            )
        )

class CannotBanResourceMasterResourceNotPromotable(NameBuildTest):
    def test_without_promotable(self):
        self.assert_message_from_report(
            "when specifying --master you must use the promotable clone id",
            reports.cannot_ban_resource_master_resource_not_promotable("R")
        )

    def test_with_promotable(self):
        self.assert_message_from_report(
            "when specifying --master you must use the promotable clone id (P)",
            reports.cannot_ban_resource_master_resource_not_promotable(
                "R",
                promotable_id="P"
            )
        )

class CannotBanResourceStoppedNoNodeSpecified(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "You must specify a node when moving/banning a stopped resource",
            reports.cannot_ban_resource_stopped_no_node_specified("R")
        )

class ResourceBanPcmkEerror(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "cannot ban resource 'R'\nstdout1\n  stdout2\nstderr1\n  stderr2",
            reports.resource_ban_pcmk_error(
                "R",
                "stdout1\n\n  stdout2\n",
                "stderr1\n\n  stderr2\n"
            )
        )

class ResourceBanPcmkSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "stdout1\n  stdout2\nstderr1\n  stderr2",
            reports.resource_ban_pcmk_success(
                "R",
                "stdout1\n\n  stdout2\n",
                "stderr1\n\n  stderr2\n"
            )
        )

    def test_translate(self):
        self.assert_message_from_report(
            (
                "Warning: Creating location constraint "
                    "'cli-ban-dummy-on-node1' with a score of -INFINITY "
                    "for resource dummy on node1.\n"
                "	This will prevent dummy from running on node1 until the "
                    "constraint is removed\n"
                "	This will be the case even if node1 is the last node in "
                    "the cluster"
            ),
            reports.resource_ban_pcmk_success(
                "dummy",
                "",
                (
                    "WARNING: Creating rsc_location constraint "
                        "'cli-ban-dummy-on-node1' with a score of -INFINITY "
                        "for resource dummy on node1.\n"
                    "	This will prevent dummy from running on node1 until "
                        "the constraint is removed using the clear option or "
                        "by editing the CIB with an appropriate tool\n"
                    "	This will be the case even if node1 is the last node "
                        "in the cluster\n"
                )
            )
        )

class CannotUnmoveUnbanResourceMasterResourceNotPromotable(NameBuildTest):
    def test_without_promotable(self):
        self.assert_message_from_report(
            "when specifying --master you must use the promotable clone id",
            reports.cannot_unmove_unban_resource_master_resource_not_promotable(
                "R"
            )
        )

    def test_with_promotable(self):
        self.assert_message_from_report(
            "when specifying --master you must use the promotable clone id (P)",
            reports.cannot_unmove_unban_resource_master_resource_not_promotable(
                "R",
                promotable_id="P"
            )
        )

class ResourceUnmoveUnbanPcmkEerror(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "cannot clear resource 'R'\nstdout1\n  stdout2\nstderr1\n  stderr2",
            reports.resource_unmove_unban_pcmk_error(
                "R",
                "stdout1\n\n  stdout2\n",
                "stderr1\n\n  stderr2\n"
            )
        )

class ResourceUnmoveUnbanPcmkSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "stdout1\n  stdout2\nstderr1\n  stderr2",
            reports.resource_unmove_unban_pcmk_success(
                "R",
                "stdout1\n\n  stdout2\n",
                "stderr1\n\n  stderr2\n"
            )
        )

class ResourceUnmoveUnbanPcmkExpiredNotSupported(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "--expired is not supported, please upgrade pacemaker",
            reports.resource_unmove_unban_pcmk_expired_not_supported()
        )

class CorosyncConfigCannotSaveInvalidNamesValues(NameBuildTest):
    def test_empty(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing invalid section names, "
                "option names or option values"
            ,
            reports.corosync_config_cannot_save_invalid_names_values([], [], [])
        )

    def test_one_section(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
                "invalid section name(s): 'SECTION'"
            ,
            reports.corosync_config_cannot_save_invalid_names_values(
                ["SECTION"], [], []
            )
        )

    def test_more_sections(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
                "invalid section name(s): 'SECTION1', 'SECTION2'"
            ,
            reports.corosync_config_cannot_save_invalid_names_values(
                ["SECTION1", "SECTION2"], [], []
            )
        )

    def test_one_attr_name(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
                "invalid option name(s): 'ATTR'"
            ,
            reports.corosync_config_cannot_save_invalid_names_values(
                [], ["ATTR"], []
            )
        )

    def test_more_attr_names(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
                "invalid option name(s): 'ATTR1', 'ATTR2'"
            ,
            reports.corosync_config_cannot_save_invalid_names_values(
                [], ["ATTR1", "ATTR2"], []
            )
        )

    def test_one_attr_value(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
                "invalid option value(s): 'VALUE' (option 'ATTR')"
            ,
            reports.corosync_config_cannot_save_invalid_names_values(
                [], [], [("ATTR", "VALUE")]
            )
        )

    def test_more_attr_values(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
                "invalid option value(s): 'VALUE1' (option 'ATTR1'), "
                "'VALUE2' (option 'ATTR2')"
            ,
            reports.corosync_config_cannot_save_invalid_names_values(
                [], [], [("ATTR1", "VALUE1"), ("ATTR2", "VALUE2")]
            )
        )

    def test_all(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
                "invalid section name(s): 'SECTION1', 'SECTION2'; "
                "invalid option name(s): 'ATTR1', 'ATTR2'; "
                "invalid option value(s): 'VALUE3' (option 'ATTR3'), "
                "'VALUE4' (option 'ATTR4')"
            ,
            reports.corosync_config_cannot_save_invalid_names_values(
                ["SECTION1", "SECTION2"],
                ["ATTR1", "ATTR2"],
                [("ATTR3", "VALUE3"), ("ATTR4", "VALUE4")]
            )
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

class UnableToDetermineUserUid(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to determine uid of user 'username'",
            reports.unable_to_determine_user_uid("username")
        )

class UnableToDetermineGroupGid(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to determine gid of group 'group'",
            reports.unable_to_determine_group_gid("group")
        )

class UnsupportedOperationOnNonSystemdSystems(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unsupported operation on non systemd systems",
            reports.unsupported_operation_on_non_systemd_systems()
        )

class AclRoleIsAlreadyAssignedToTarget(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Role 'role_id' is already assigned to 'target_id'",
            reports.acl_role_is_already_assigned_to_target(
                "role_id", "target_id"
            )
        )

class AclRoleIsNotAssignedToTarget(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Role 'role_id' is not assigned to 'target_id'",
            reports.acl_role_is_not_assigned_to_target("role_id", "target_id")
        )

class AclTargetAlreadyExists(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "'target_id' already exists",
            reports.acl_target_already_exists("target_id")
        )

class ClusterSetupSuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Cluster has been successfully set up.",
            reports.cluster_setup_success()
        )

class SystemWillReset(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "System will reset shortly",
            reports.system_will_reset()
        )

class ParseErrorJsonFile(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to parse known-hosts file '/tmp/known-hosts': "
                "some reason: line 15 column 5 (char 100)"
            ,
            reports.parse_error_json_file(
                file_type_codes.PCS_KNOWN_HOSTS,
                15,
                5,
                100,
                "some reason",
                "some reason: line 15 column 5 (char 100)",
                file_path="/tmp/known-hosts",
            )
        )

class ResourceDisableAffectsOtherResources(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Disabling specified resources would have an effect on other "
                "resources\n\ncrm_simulate output"
            ),
            reports.resource_disable_affects_other_resources(
                ["D2", "D1"],
                ["O2", "O1"],
                "crm_simulate output",
            )
        )


class DrConfigAlreadyExist(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Disaster-recovery already configured",
            reports.dr_config_already_exist()
        )


class DrConfigDoesNotExist(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Disaster-recovery is not configured",
            reports.dr_config_does_not_exist()
        )


class NodeInLocalCluster(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Node 'node-name' is part of local cluster",
            reports.node_in_local_cluster("node-name")
        )

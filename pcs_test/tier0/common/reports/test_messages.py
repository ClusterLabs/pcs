import inspect
from unittest import TestCase

from pcs.common import file_type_codes
from pcs.common.fencing_topology import (
    TARGET_TYPE_ATTRIBUTE,
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
)
from pcs.common.file import RawFileError
from pcs.common.reports import const
from pcs.common.reports import messages as reports
from pcs.common.resource_agent.dto import ResourceAgentNameDto
from pcs.common.types import CibRuleExpressionType

# pylint: disable=too-many-lines


class AllClassesTested(TestCase):
    def test_success(self):
        self.maxDiff = None
        message_classes = frozenset(
            name
            for name, member in inspect.getmembers(reports, inspect.isclass)
            if issubclass(member, reports.ReportItemMessage)
            and member
            not in {reports.ReportItemMessage, reports.LegacyCommonMessage}
        )
        test_classes = frozenset(
            name
            for name, member in inspect.getmembers(
                inspect.getmodule(self), inspect.isclass
            )
            if issubclass(member, NameBuildTest)
        )
        untested = sorted(message_classes - test_classes)
        self.assertEqual(
            untested,
            [],
            f"It seems {len(untested)} subclass(es) of 'ReportItemMessage' are "
            "missing tests. Make sure the test classes have the same name as "
            "the code classes.",
        )


class NameBuildTest(TestCase):
    """
    Base class for the testing of message building.
    """

    def assert_message_from_report(self, message, report):
        self.maxDiff = None
        self.assertEqual(message, report.message)


class ResourceForConstraintIsMultiinstance(NameBuildTest):
    def test_success(self):
        self.assertEqual(
            (
                "resource1 is a bundle resource, you should use the "
                "bundle id: parent1 when adding constraints"
            ),
            reports.ResourceForConstraintIsMultiinstance(
                "resource1", "bundle", "parent1"
            ).message,
        )


class DuplicateConstraintsExist(NameBuildTest):
    def test_build_singular(self):
        self.assert_message_from_report(
            "Duplicate constraint already exists",
            reports.DuplicateConstraintsExist(["c1"]),
        )

    def test_build_plural(self):
        self.assert_message_from_report(
            "Duplicate constraints already exist",
            reports.DuplicateConstraintsExist(["c1", "c3", "c0"]),
        )


class EmptyResourceSetList(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Resource set list is empty",
            reports.EmptyResourceSetList(),
        )


class CannotSetOrderConstraintsForResourcesInTheSameGroup(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Cannot create an order constraint for resources in the same group",
            reports.CannotSetOrderConstraintsForResourcesInTheSameGroup(),
        )


class RequiredOptionsAreMissing(NameBuildTest):
    def test_build_message_with_type(self):
        self.assert_message_from_report(
            "required TYPE option 'NAME' is missing",
            reports.RequiredOptionsAreMissing(["NAME"], option_type="TYPE"),
        )

    def test_build_message_without_type(self):
        self.assert_message_from_report(
            "required option 'NAME' is missing",
            reports.RequiredOptionsAreMissing(["NAME"]),
        )

    def test_build_message_with_multiple_names(self):
        self.assert_message_from_report(
            "required options 'ANOTHER', 'NAME' are missing",
            reports.RequiredOptionsAreMissing(["NAME", "ANOTHER"]),
        )


class PrerequisiteOptionIsMissing(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            "If option 'a' is specified, option 'b' must be specified as well",
            reports.PrerequisiteOptionIsMissing("a", "b"),
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "If some option 'a' is specified, "
            "other option 'b' must be specified as well",
            reports.PrerequisiteOptionIsMissing("a", "b", "some", "other"),
        )


class PrerequisiteOptionMustBeEnabledAsWell(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            "If option 'a' is enabled, option 'b' must be enabled as well",
            reports.PrerequisiteOptionMustBeEnabledAsWell("a", "b"),
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "If some option 'a' is enabled, "
            "other option 'b' must be enabled as well",
            reports.PrerequisiteOptionMustBeEnabledAsWell(
                "a", "b", "some", "other"
            ),
        )


class PrerequisiteOptionMustBeDisabled(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            "If option 'a' is enabled, option 'b' must be disabled",
            reports.PrerequisiteOptionMustBeDisabled("a", "b"),
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "If some option 'a' is enabled, other option 'b' must be disabled",
            reports.PrerequisiteOptionMustBeDisabled("a", "b", "some", "other"),
        )


class PrerequisiteOptionMustNotBeSet(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            "Cannot set option 'a' because option 'b' is already set",
            reports.PrerequisiteOptionMustNotBeSet(
                "a",
                "b",
            ),
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "Cannot set some option 'a' because other option 'b' is "
            "already set",
            reports.PrerequisiteOptionMustNotBeSet(
                "a",
                "b",
                option_type="some",
                prerequisite_type="other",
            ),
        )


class RequiredOptionOfAlternativesIsMissing(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "option 'aAa', 'bBb' or 'cCc' has to be specified",
            reports.RequiredOptionOfAlternativesIsMissing(
                ["aAa", "cCc", "bBb"]
            ),
        )

    def test_with_type(self):
        self.assert_message_from_report(
            "test option 'aAa' has to be specified",
            reports.RequiredOptionOfAlternativesIsMissing(
                ["aAa"], option_type="test"
            ),
        )

    def test_with_deprecated(self):
        self.assert_message_from_report(
            (
                "option 'bBb', 'aAa' (deprecated) or 'cCc' (deprecated) has "
                "to be specified"
            ),
            reports.RequiredOptionOfAlternativesIsMissing(
                ["aAa", "cCc", "bBb"], deprecated_names=["cCc", "aAa"]
            ),
        )


class InvalidOptions(NameBuildTest):
    def test_build_message_with_type(self):
        self.assert_message_from_report(
            "invalid TYPE option 'NAME', allowed options are: 'FIRST', "
            "'SECOND'",
            reports.InvalidOptions(["NAME"], ["SECOND", "FIRST"], "TYPE"),
        )

    def test_build_message_without_type(self):
        self.assert_message_from_report(
            "invalid option 'NAME', allowed options are: 'FIRST', 'SECOND'",
            reports.InvalidOptions(["NAME"], ["FIRST", "SECOND"], ""),
        )

    def test_build_message_with_multiple_names(self):
        self.assert_message_from_report(
            "invalid options: 'ANOTHER', 'NAME', allowed option is 'FIRST'",
            reports.InvalidOptions(["NAME", "ANOTHER"], ["FIRST"], ""),
        )

    def test_pattern(self):
        self.assert_message_from_report(
            (
                "invalid option 'NAME', allowed are options matching patterns: "
                "'exec_<name>'"
            ),
            reports.InvalidOptions(["NAME"], [], "", ["exec_<name>"]),
        )

    def test_allowed_and_patterns(self):
        self.assert_message_from_report(
            (
                "invalid option 'NAME', allowed option is 'FIRST' and options "
                "matching patterns: 'exec_<name>'"
            ),
            reports.InvalidOptions(
                ["NAME"], ["FIRST"], "", allowed_patterns=["exec_<name>"]
            ),
        )

    def test_no_allowed_options(self):
        self.assert_message_from_report(
            "invalid options: 'ANOTHER', 'NAME', there are no options allowed",
            reports.InvalidOptions(["NAME", "ANOTHER"], [], ""),
        )


class InvalidUserdefinedOptions(NameBuildTest):
    def test_without_type(self):
        self.assert_message_from_report(
            (
                "invalid option 'exec_NAME', options may contain "
                "a-z A-Z 0-9 /_- characters only"
            ),
            reports.InvalidUserdefinedOptions(["exec_NAME"], "a-z A-Z 0-9 /_-"),
        )

    def test_with_type(self):
        self.assert_message_from_report(
            (
                "invalid heuristics option 'exec_NAME', heuristics options may "
                "contain a-z A-Z 0-9 /_- characters only"
            ),
            reports.InvalidUserdefinedOptions(
                ["exec_NAME"], "a-z A-Z 0-9 /_-", "heuristics"
            ),
        )

    def test_more_options(self):
        self.assert_message_from_report(
            (
                "invalid TYPE options: 'ANOTHER', 'NAME', TYPE options may "
                "contain a-z A-Z 0-9 /_- characters only"
            ),
            reports.InvalidUserdefinedOptions(
                ["NAME", "ANOTHER"], "a-z A-Z 0-9 /_-", "TYPE"
            ),
        )


class InvalidOptionType(NameBuildTest):
    def test_allowed_string(self):
        self.assert_message_from_report(
            "specified option name is not valid, use allowed types",
            reports.InvalidOptionType("option name", "allowed types"),
        )

    def test_allowed_list(self):
        self.assert_message_from_report(
            "specified option name is not valid, use 'allowed', 'types'",
            reports.InvalidOptionType("option name", ["types", "allowed"]),
        )


class InvalidOptionValue(NameBuildTest):
    def test_multiple_allowed_values(self):
        self.assert_message_from_report(
            "'VALUE' is not a valid NAME value, use 'FIRST', 'SECOND'",
            reports.InvalidOptionValue("NAME", "VALUE", ["SECOND", "FIRST"]),
        )

    def test_textual_hint(self):
        self.assert_message_from_report(
            "'VALUE' is not a valid NAME value, use some hint",
            reports.InvalidOptionValue("NAME", "VALUE", "some hint"),
        )

    def test_cannot_be_empty(self):
        self.assert_message_from_report(
            "NAME cannot be empty",
            reports.InvalidOptionValue(
                "NAME", "VALUE", allowed_values=None, cannot_be_empty=True
            ),
        )

    def test_cannot_be_empty_with_hint(self):
        self.assert_message_from_report(
            "NAME cannot be empty, use 'FIRST', 'SECOND'",
            reports.InvalidOptionValue(
                "NAME", "VALUE", ["SECOND", "FIRST"], cannot_be_empty=True
            ),
        )

    def test_forbidden_characters(self):
        self.assert_message_from_report(
            r"NAME cannot contain }{\r\n characters",
            reports.InvalidOptionValue(
                "NAME",
                "VALUE",
                allowed_values=None,
                forbidden_characters="}{\\r\\n",
            ),
        )

    def test_forbidden_characters_with_hint(self):
        self.assert_message_from_report(
            r"NAME cannot contain }{\r\n characters, use 'FIRST', 'SECOND'",
            reports.InvalidOptionValue(
                "NAME",
                "VALUE",
                ["SECOND", "FIRST"],
                forbidden_characters="}{\\r\\n",
            ),
        )

    def test_cannot_be_empty_and_forbidden_characters(self):
        self.assert_message_from_report(
            "NAME cannot be empty, use 'FIRST', 'SECOND'",
            reports.InvalidOptionValue(
                "NAME", "VALUE", ["SECOND", "FIRST"], True
            ),
        )


class DeprecatedOption(NameBuildTest):
    def test_no_desc_hint_array(self):
        self.assert_message_from_report(
            (
                "option 'option name' is deprecated and might be removed in a "
                "future release, therefore it should not be used, use 'new_a', "
                "'new_b' instead"
            ),
            reports.DeprecatedOption("option name", ["new_b", "new_a"], ""),
        )

    def test_desc_hint_string(self):
        self.assert_message_from_report(
            (
                "option type option 'option name' is deprecated and might be "
                "removed in a future release, therefore it should not be used, "
                "use 'new option' instead"
            ),
            reports.DeprecatedOption(
                "option name", ["new option"], "option type"
            ),
        )

    def test_empty_hint(self):
        self.assert_message_from_report(
            (
                "option 'option name' is deprecated and might be removed in a "
                "future release, therefore it should not be used"
            ),
            reports.DeprecatedOption("option name", [], ""),
        )


class DeprecatedOptionValue(NameBuildTest):
    def test_replaced_by(self):
        self.assert_message_from_report(
            (
                "Value 'deprecatedValue' of option optionA is deprecated and "
                "might be removed in a future release, therefore it should not "
                "be used, use 'newValue' value instead"
            ),
            reports.DeprecatedOptionValue(
                "optionA", "deprecatedValue", "newValue"
            ),
        )

    def test_no_replacement(self):
        self.assert_message_from_report(
            (
                "Value 'deprecatedValue' of option optionA is deprecated and "
                "might be removed in a future release, therefore it should not "
                "be used"
            ),
            reports.DeprecatedOptionValue("optionA", "deprecatedValue"),
        )


class MutuallyExclusiveOptions(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Only one of some options 'a' and 'b' can be used",
            reports.MutuallyExclusiveOptions(["b", "a"], "some"),
        )


class InvalidCibContent(NameBuildTest):
    def test_message_can_be_more_verbose(self):
        report = "no verbose\noutput\n"
        self.assert_message_from_report(
            "invalid cib:\n{0}".format(report),
            reports.InvalidCibContent(report, True),
        )

    def test_message_cannot_be_more_verbose(self):
        report = "some verbose\noutput"
        self.assert_message_from_report(
            "invalid cib:\n{0}".format(report),
            reports.InvalidCibContent(report, False),
        )


class InvalidIdIsEmpty(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "description cannot be empty",
            reports.InvalidIdIsEmpty("description"),
        )


class InvalidIdBadChar(NameBuildTest):
    def test_build_message_with_first_char_invalid(self):
        self.assert_message_from_report(
            (
                "invalid ID_DESCRIPTION 'ID', 'INVALID_CHARACTER' is not a"
                " valid first character for a ID_DESCRIPTION"
            ),
            reports.InvalidIdBadChar(
                "ID", "ID_DESCRIPTION", "INVALID_CHARACTER", is_first_char=True
            ),
        )

    def test_build_message_with_non_first_char_invalid(self):
        self.assert_message_from_report(
            (
                "invalid ID_DESCRIPTION 'ID', 'INVALID_CHARACTER' is not a"
                " valid character for a ID_DESCRIPTION"
            ),
            reports.InvalidIdBadChar(
                "ID", "ID_DESCRIPTION", "INVALID_CHARACTER", is_first_char=False
            ),
        )


class InvalidIdType(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "'entered' is not a valid type of ID specification, "
                "use 'expected1', 'expected2'"
            ),
            reports.InvalidIdType("entered", ["expected1", "expected2"]),
        )


class InvalidTimeoutValue(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "'24h' is not a valid number of seconds to wait",
            reports.InvalidTimeoutValue("24h"),
        )


class InvalidScore(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "invalid score '1M', use integer or INFINITY or -INFINITY",
            reports.InvalidScore("1M"),
        )


class RunExternalProcessStarted(NameBuildTest):
    def test_build_message_minimal(self):
        self.assert_message_from_report(
            "Running: COMMAND\nEnvironment:\n",
            reports.RunExternalProcessStarted("COMMAND", "", {}),
        )

    def test_build_message_with_stdin(self):
        self.assert_message_from_report(
            (
                "Running: COMMAND\nEnvironment:\n"
                "--Debug Input Start--\n"
                "STDIN\n"
                "--Debug Input End--\n"
            ),
            reports.RunExternalProcessStarted("COMMAND", "STDIN", {}),
        )

    def test_build_message_with_env(self):
        self.assert_message_from_report(
            ("Running: COMMAND\nEnvironment:\n  env_a=A\n  env_b=B\n"),
            reports.RunExternalProcessStarted(
                "COMMAND",
                "",
                {
                    "env_a": "A",
                    "env_b": "B",
                },
            ),
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
            reports.RunExternalProcessStarted(
                "COMMAND",
                "STDIN",
                {
                    "env_a": "A",
                    "env_b": "B",
                },
            ),
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
            reports.RunExternalProcessStarted(
                "COMMAND",
                "STDIN",
                {
                    "test": "a:{green},b:{red}",
                },
            ),
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
            reports.RunExternalProcessFinished(
                "com-mand", 0, "STDOUT", "STDERR"
            ),
        )


class RunExternalProcessError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unable to run command com-mand: reason",
            reports.RunExternalProcessError("com-mand", "reason"),
        )


class NoActionNecessary(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "No action necessary, requested change would have no effect",
            reports.NoActionNecessary(),
        )


class NodeCommunicationStarted(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            (
                "Sending HTTP Request to: TARGET\n"
                "--Debug Input Start--\n"
                "DATA\n"
                "--Debug Input End--\n"
            ),
            reports.NodeCommunicationStarted("TARGET", "DATA"),
        )

    def test_build_message_without_data(self):
        self.assert_message_from_report(
            "Sending HTTP Request to: TARGET\n",
            reports.NodeCommunicationStarted("TARGET", ""),
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
            reports.NodeCommunicationFinished("node1", 0, "DATA"),
        )


class NodeCommunicationDebugInfo(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Communication debug info for calling: node1\n"
                "--Debug Communication Info Start--\n"
                "DATA\n"
                "--Debug Communication Info End--\n"
            ),
            reports.NodeCommunicationDebugInfo("node1", "DATA"),
        )


class NodeCommunicationNotConnected(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to connect to node2 (this is reason)",
            reports.NodeCommunicationNotConnected("node2", "this is reason"),
        )


class NodeCommunicationNoMoreAddresses(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to connect to 'node_name' via any of its addresses",
            reports.NodeCommunicationNoMoreAddresses(
                "node_name",
                "my/request",
            ),
        )


class NodeCommunicationErrorNotAuthorized(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to authenticate to node1 (some error)",
            reports.NodeCommunicationErrorNotAuthorized(
                "node1", "some-command", "some error"
            ),
        )


class NodeCommunicationErrorPermissionDenied(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node3: Permission denied (reason)",
            reports.NodeCommunicationErrorPermissionDenied(
                "node3", "com-mand", "reason"
            ),
        )


class NodeCommunicationErrorUnsupportedCommand(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Unsupported command (reason), try upgrading pcsd",
            reports.NodeCommunicationErrorUnsupportedCommand(
                "node1", "com-mand", "reason"
            ),
        )


class NodeCommunicationCommandUnsuccessful(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: reason",
            reports.NodeCommunicationCommandUnsuccessful(
                "node1", "com-mand", "reason"
            ),
        )


class NodeCommunicationError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Error connecting to node1 (reason)",
            reports.NodeCommunicationError("node1", "com-mand", "reason"),
        )


class NodeCommunicationErrorUnableToConnect(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to connect to node1 (reason)",
            reports.NodeCommunicationErrorUnableToConnect(
                "node1", "com-mand", "reason"
            ),
        )


class NodeCommunicationErrorTimedOut(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "node-1: Connection timeout (Connection timed out after 60049 "
                "milliseconds)"
            ),
            reports.NodeCommunicationErrorTimedOut(
                "node-1",
                "/remote/command",
                "Connection timed out after 60049 milliseconds",
            ),
        )


class NodeCommunicationProxyIsSet(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Proxy is set in environment variables, try disabling it",
            reports.NodeCommunicationProxyIsSet(),
        )

    def test_with_node(self):
        self.assert_message_from_report(
            "Proxy is set in environment variables, try disabling it",
            reports.NodeCommunicationProxyIsSet(node="node1"),
        )

    def test_with_address(self):
        self.assert_message_from_report(
            "Proxy is set in environment variables, try disabling it",
            reports.NodeCommunicationProxyIsSet(address="aaa"),
        )

    def test_all(self):
        self.assert_message_from_report(
            "Proxy is set in environment variables, try disabling it",
            reports.NodeCommunicationProxyIsSet(node="node1", address="aaa"),
        )


class NodeCommunicationRetrying(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Unable to connect to 'node_name' via address 'failed.address' "
                "and port '2224'. Retrying request 'my/request' via address "
                "'next.address' and port '2225'"
            ),
            reports.NodeCommunicationRetrying(
                "node_name",
                "failed.address",
                "2224",
                "next.address",
                "2225",
                "my/request",
            ),
        )


class DefaultsCanBeOverridden(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "Defaults do not apply to resources which override them with "
                "their own defined values"
            ),
            reports.DefaultsCanBeOverridden(),
        )


class CorosyncAuthkeyWrongLength(NameBuildTest):
    def test_at_most_allowed_singular_provided_plural(self):
        self.assert_message_from_report(
            (
                "At least 0 and at most 1 byte key must be provided for "
                "a corosync authkey, 2 bytes key provided"
            ),
            reports.CorosyncAuthkeyWrongLength(2, 0, 1),
        )

    def test_at_most_allowed_plural_provided_singular(self):
        self.assert_message_from_report(
            (
                "At least 2 and at most 3 bytes key must be provided for "
                "a corosync authkey, 1 byte key provided"
            ),
            reports.CorosyncAuthkeyWrongLength(1, 2, 3),
        )

    def test_exactly_allowed_singular_provided_plural(self):
        self.assert_message_from_report(
            (
                "1 byte key must be provided for a corosync authkey, 2 bytes "
                "key provided"
            ),
            reports.CorosyncAuthkeyWrongLength(2, 1, 1),
        )

    def test_exactly_allowed_plural_provided_singular(self):
        self.assert_message_from_report(
            (
                "2 bytes key must be provided for a corosync authkey, 1 byte "
                "key provided"
            ),
            reports.CorosyncAuthkeyWrongLength(1, 2, 2),
        )


class CorosyncConfigDistributionStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Sending updated corosync.conf to nodes...",
            reports.CorosyncConfigDistributionStarted(),
        )


# TODO: consider generalizing
class CorosyncConfigAcceptedByNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Succeeded", reports.CorosyncConfigAcceptedByNode("node1")
        )


class CorosyncConfigDistributionNodeError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Unable to set corosync config",
            reports.CorosyncConfigDistributionNodeError("node1"),
        )


class CorosyncNotRunningCheckStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Checking that corosync is not running on nodes...",
            reports.CorosyncNotRunningCheckStarted(),
        )


class CorosyncNotRunningCheckFinishedRunning(NameBuildTest):
    def test_one_node(self):
        self.assert_message_from_report(
            (
                "Corosync is running on node 'node1'. Requested change can "
                "only be made if the cluster is stopped. In order to proceed, "
                "stop the cluster."
            ),
            reports.CorosyncNotRunningCheckFinishedRunning(["node1"]),
        )

    def test_more_nodes(self):
        self.assert_message_from_report(
            (
                "Corosync is running on nodes 'node1', 'node2', 'node3'. "
                "Requested change can only be made if the cluster is stopped. "
                "In order to proceed, stop the cluster."
            ),
            reports.CorosyncNotRunningCheckFinishedRunning(
                ["node2", "node1", "node3"]
            ),
        )


class CorosyncNotRunningCheckNodeError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to check if corosync is not running on node 'node1'",
            reports.CorosyncNotRunningCheckNodeError("node1"),
        )


class CorosyncNotRunningCheckNodeStopped(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Corosync is not running on node 'node2'",
            reports.CorosyncNotRunningCheckNodeStopped("node2"),
        )


class CorosyncNotRunningCheckNodeRunning(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Corosync is running on node 'node3'",
            reports.CorosyncNotRunningCheckNodeRunning("node3"),
        )


class CorosyncQuorumGetStatusError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to get quorum status: a reason",
            reports.CorosyncQuorumGetStatusError("a reason"),
        )

    def test_success_with_node(self):
        self.assert_message_from_report(
            "node1: Unable to get quorum status: a reason",
            reports.CorosyncQuorumGetStatusError("a reason", "node1"),
        )


class CorosyncQuorumHeuristicsEnabledWithNoExec(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "No exec_NAME options are specified, so heuristics are "
                "effectively disabled"
            ),
            reports.CorosyncQuorumHeuristicsEnabledWithNoExec(),
        )


class CorosyncQuorumSetExpectedVotesError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to set expected votes: reason",
            reports.CorosyncQuorumSetExpectedVotesError("reason"),
        )


class CorosyncConfigReloaded(NameBuildTest):
    def test_with_node(self):
        self.assert_message_from_report(
            "node1: Corosync configuration reloaded",
            reports.CorosyncConfigReloaded("node1"),
        )

    def test_without_node(self):
        self.assert_message_from_report(
            "Corosync configuration reloaded",
            reports.CorosyncConfigReloaded(),
        )


class CorosyncConfigReloadError(NameBuildTest):
    def test_with_node(self):
        self.assert_message_from_report(
            "node1: Unable to reload corosync configuration: a reason",
            reports.CorosyncConfigReloadError("a reason", "node1"),
        )

    def test_without_node(self):
        self.assert_message_from_report(
            "Unable to reload corosync configuration: different reason",
            reports.CorosyncConfigReloadError("different reason"),
        )


class CorosyncConfigReloadNotPossible(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "node1: Corosync is not running, therefore reload of the "
                "corosync configuration is not possible"
            ),
            reports.CorosyncConfigReloadNotPossible("node1"),
        )


class CorosyncConfigUnsupportedTransport(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Transport 'netk' currently configured in corosync.conf is "
                "unsupported. Supported transport types are: 'knet', 'udp', "
                "'udpu'"
            ),
            reports.CorosyncConfigUnsupportedTransport(
                "netk", ["udp", "knet", "udpu"]
            ),
        )


class ParseErrorCorosyncConfMissingClosingBrace(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config: missing closing brace",
            reports.ParseErrorCorosyncConfMissingClosingBrace(),
        )


class ParseErrorCorosyncConfUnexpectedClosingBrace(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config: unexpected closing brace",
            reports.ParseErrorCorosyncConfUnexpectedClosingBrace(),
        )


class ParseErrorCorosyncConfMissingSectionNameBeforeOpeningBrace(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config: missing a section name before {",
            reports.ParseErrorCorosyncConfMissingSectionNameBeforeOpeningBrace(),
        )


class ParseErrorCorosyncConfExtraCharactersAfterOpeningBrace(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config: extra characters after {",
            reports.ParseErrorCorosyncConfExtraCharactersAfterOpeningBrace(),
        )


class ParseErrorCorosyncConfExtraCharactersBeforeOrAfterClosingBrace(
    NameBuildTest
):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Unable to parse corosync config: extra characters before "
                "or after }"
            ),
            reports.ParseErrorCorosyncConfExtraCharactersBeforeOrAfterClosingBrace(),
        )


class ParseErrorCorosyncConfLineIsNotSectionNorKeyValue(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config: a line is not opening or closing "
            "a section or key: value",
            reports.ParseErrorCorosyncConfLineIsNotSectionNorKeyValue(),
        )


class ParseErrorCorosyncConf(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse corosync config", reports.ParseErrorCorosyncConf()
        )


class CorosyncConfigCannotSaveInvalidNamesValues(NameBuildTest):
    def test_empty(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing invalid section names, "
            "option names or option values",
            reports.CorosyncConfigCannotSaveInvalidNamesValues([], [], []),
        )

    def test_one_section(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
            "invalid section name(s): 'SECTION'",
            reports.CorosyncConfigCannotSaveInvalidNamesValues(
                ["SECTION"], [], []
            ),
        )

    def test_more_sections(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
            "invalid section name(s): 'SECTION1', 'SECTION2'",
            reports.CorosyncConfigCannotSaveInvalidNamesValues(
                ["SECTION1", "SECTION2"], [], []
            ),
        )

    def test_one_attr_name(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
            "invalid option name(s): 'ATTR'",
            reports.CorosyncConfigCannotSaveInvalidNamesValues(
                [], ["ATTR"], []
            ),
        )

    def test_more_attr_names(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
            "invalid option name(s): 'ATTR1', 'ATTR2'",
            reports.CorosyncConfigCannotSaveInvalidNamesValues(
                [], ["ATTR1", "ATTR2"], []
            ),
        )

    def test_one_attr_value(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
            "invalid option value(s): 'VALUE' (option 'ATTR')",
            reports.CorosyncConfigCannotSaveInvalidNamesValues(
                [], [], [("ATTR", "VALUE")]
            ),
        )

    def test_more_attr_values(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
            "invalid option value(s): 'VALUE1' (option 'ATTR1'), "
            "'VALUE2' (option 'ATTR2')",
            reports.CorosyncConfigCannotSaveInvalidNamesValues(
                [], [], [("ATTR1", "VALUE1"), ("ATTR2", "VALUE2")]
            ),
        )

    def test_all(self):
        self.assert_message_from_report(
            "Cannot save corosync.conf containing "
            "invalid section name(s): 'SECTION1', 'SECTION2'; "
            "invalid option name(s): 'ATTR1', 'ATTR2'; "
            "invalid option value(s): 'VALUE3' (option 'ATTR3'), "
            "'VALUE4' (option 'ATTR4')",
            reports.CorosyncConfigCannotSaveInvalidNamesValues(
                ["SECTION1", "SECTION2"],
                ["ATTR1", "ATTR2"],
                [("ATTR3", "VALUE3"), ("ATTR4", "VALUE4")],
            ),
        )


class CorosyncConfigMissingNamesOfNodes(NameBuildTest):
    def test_non_fatal(self):
        self.assert_message_from_report(
            "Some nodes are missing names in corosync.conf, "
            "those nodes were omitted. "
            "Edit corosync.conf and make sure all nodes have their name set.",
            reports.CorosyncConfigMissingNamesOfNodes(),
        )

    def test_fatal(self):
        self.assert_message_from_report(
            "Some nodes are missing names in corosync.conf, "
            "unable to continue. "
            "Edit corosync.conf and make sure all nodes have their name set.",
            reports.CorosyncConfigMissingNamesOfNodes(fatal=True),
        )


class CorosyncConfigMissingIdsOfNodes(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Some nodes are missing IDs in corosync.conf. "
            "Edit corosync.conf and make sure all nodes have their nodeid set.",
            reports.CorosyncConfigMissingIdsOfNodes(),
        )


class CorosyncConfigNoNodesDefined(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "No nodes found in corosync.conf",
            reports.CorosyncConfigNoNodesDefined(),
        )


class CorosyncOptionsIncompatibleWithQdevice(NameBuildTest):
    def test_single_option(self):
        self.assert_message_from_report(
            "These options cannot be set when the cluster uses a quorum "
            "device: 'option1'",
            reports.CorosyncOptionsIncompatibleWithQdevice(["option1"]),
        )

    def test_multiple_options(self):
        self.assert_message_from_report(
            "These options cannot be set when the cluster uses a quorum "
            "device: 'option1', 'option2', 'option3'",
            reports.CorosyncOptionsIncompatibleWithQdevice(
                ["option3", "option1", "option2"]
            ),
        )


class CorosyncClusterNameInvalidForGfs2(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Chosen cluster name 'cluster name' will prevent mounting GFS2 "
            "volumes in the cluster, use at most 16 of a-z A-Z characters; "
            "you may safely override this if you do not intend to use GFS2",
            reports.CorosyncClusterNameInvalidForGfs2(
                cluster_name="cluster name",
                max_length=16,
                allowed_characters="a-z A-Z",
            ),
        )


class CorosyncBadNodeAddressesCount(NameBuildTest):
    def test_no_node_info(self):
        self.assert_message_from_report(
            "At least 1 and at most 4 addresses must be specified for a node, "
            "5 addresses specified",
            reports.CorosyncBadNodeAddressesCount(5, 1, 4),
        )

    def test_node_name(self):
        self.assert_message_from_report(
            "At least 1 and at most 4 addresses must be specified for a node, "
            "5 addresses specified for node 'node1'",
            reports.CorosyncBadNodeAddressesCount(5, 1, 4, "node1"),
        )

    def test_node_id(self):
        self.assert_message_from_report(
            "At least 1 and at most 4 addresses must be specified for a node, "
            "5 addresses specified for node '2'",
            reports.CorosyncBadNodeAddressesCount(5, 1, 4, node_index=2),
        )

    def test_node_name_and_id(self):
        self.assert_message_from_report(
            "At least 1 and at most 4 addresses must be specified for a node, "
            "5 addresses specified for node 'node2'",
            reports.CorosyncBadNodeAddressesCount(5, 1, 4, "node2", 2),
        )

    def test_one_address_allowed(self):
        self.assert_message_from_report(
            "At least 0 and at most 1 address must be specified for a node, "
            "2 addresses specified for node 'node2'",
            reports.CorosyncBadNodeAddressesCount(2, 0, 1, "node2", 2),
        )

    def test_one_address_specified(self):
        self.assert_message_from_report(
            "At least 2 and at most 4 addresses must be specified for a node, "
            "1 address specified for node 'node2'",
            reports.CorosyncBadNodeAddressesCount(1, 2, 4, "node2", 2),
        )

    def test_exactly_one_address_allowed(self):
        self.assert_message_from_report(
            "1 address must be specified for a node, "
            "2 addresses specified for node 'node2'",
            reports.CorosyncBadNodeAddressesCount(2, 1, 1, "node2", 2),
        )

    def test_exactly_two_addresses_allowed(self):
        self.assert_message_from_report(
            "2 addresses must be specified for a node, "
            "1 address specified for node 'node2'",
            reports.CorosyncBadNodeAddressesCount(1, 2, 2, "node2", 2),
        )


class CorosyncIpVersionMismatchInLinks(NameBuildTest):
    def test_without_links(self):
        self.assert_message_from_report(
            "Using both IPv4 and IPv6 on one link is not allowed; please, use "
            "either IPv4 or IPv6",
            reports.CorosyncIpVersionMismatchInLinks(),
        )

    def test_with_single_link(self):
        self.assert_message_from_report(
            "Using both IPv4 and IPv6 on one link is not allowed; please, use "
            "either IPv4 or IPv6 on link(s): '3'",
            reports.CorosyncIpVersionMismatchInLinks(["3"]),
        )

    def test_with_links(self):
        self.assert_message_from_report(
            "Using both IPv4 and IPv6 on one link is not allowed; please, use "
            "either IPv4 or IPv6 on link(s): '0', '3', '4'",
            reports.CorosyncIpVersionMismatchInLinks(["3", "0", "4"]),
        )


class CorosyncAddressIpVersionWrongForLink(NameBuildTest):
    def test_without_links(self):
        self.assert_message_from_report(
            "Address '192.168.100.42' cannot be used in the link because "
            "the link uses IPv6 addresses",
            reports.CorosyncAddressIpVersionWrongForLink(
                "192.168.100.42",
                "IPv6",
            ),
        )

    def test_with_links(self):
        self.assert_message_from_report(
            "Address '192.168.100.42' cannot be used in link '3' because "
            "the link uses IPv6 addresses",
            reports.CorosyncAddressIpVersionWrongForLink(
                "192.168.100.42",
                "IPv6",
                3,
            ),
        )


class CorosyncLinkNumberDuplication(NameBuildTest):
    _template = "Link numbers must be unique, duplicate link numbers: {values}"

    def test_message(self):
        self.assert_message_from_report(
            self._template.format(values="'1', '3'"),
            reports.CorosyncLinkNumberDuplication(["1", "3"]),
        )

    def test_sort(self):
        self.assert_message_from_report(
            self._template.format(values="'1', '3'"),
            reports.CorosyncLinkNumberDuplication(["3", "1"]),
        )

    def test_sort_not_int(self):
        self.assert_message_from_report(
            self._template.format(values="'-5', 'x3', '1', '3'"),
            reports.CorosyncLinkNumberDuplication(["3", "1", "x3", "-5"]),
        )


class CorosyncNodeAddressCountMismatch(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "All nodes must have the same number of addresses; "
            "nodes 'node3', 'node4', 'node6' have 1 address; "
            "nodes 'node2', 'node5' have 3 addresses; "
            "node 'node1' has 2 addresses",
            reports.CorosyncNodeAddressCountMismatch(
                {
                    "node1": 2,
                    "node2": 3,
                    "node3": 1,
                    "node4": 1,
                    "node5": 3,
                    "node6": 1,
                }
            ),
        )


class NodeAddressesAlreadyExist(NameBuildTest):
    def test_one_address(self):
        self.assert_message_from_report(
            "Node address 'node1' is already used by existing nodes; please, "
            "use other address",
            reports.NodeAddressesAlreadyExist(["node1"]),
        )

    def test_more_addresses(self):
        self.assert_message_from_report(
            "Node addresses 'node1', 'node3' are already used by existing "
            "nodes; please, use other addresses",
            reports.NodeAddressesAlreadyExist(["node1", "node3"]),
        )


class NodeAddressesCannotBeEmpty(NameBuildTest):
    def test_one_node(self):
        self.assert_message_from_report(
            ("Empty address set for node 'node2', an address cannot be empty"),
            reports.NodeAddressesCannotBeEmpty(["node2"]),
        )

    def test_more_nodes(self):
        self.assert_message_from_report(
            (
                "Empty address set for nodes 'node1', 'node2', "
                "an address cannot be empty"
            ),
            reports.NodeAddressesCannotBeEmpty(["node2", "node1"]),
        )


class NodeAddressesDuplication(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Node addresses must be unique, duplicate addresses: "
            "'node1', 'node3'",
            reports.NodeAddressesDuplication(["node1", "node3"]),
        )


class NodeNamesAlreadyExist(NameBuildTest):
    def test_one_address(self):
        self.assert_message_from_report(
            "Node name 'node1' is already used by existing nodes; please, "
            "use other name",
            reports.NodeNamesAlreadyExist(["node1"]),
        )

    def test_more_addresses(self):
        self.assert_message_from_report(
            "Node names 'node1', 'node3' are already used by existing "
            "nodes; please, use other names",
            reports.NodeNamesAlreadyExist(["node1", "node3"]),
        )


class NodeNamesDuplication(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Node names must be unique, duplicate names: 'node1', 'node3'",
            reports.NodeNamesDuplication(["node1", "node3"]),
        )


class CorosyncNodesMissing(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "No nodes have been specified", reports.CorosyncNodesMissing()
        )


class CorosyncTooManyLinksOptions(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "Cannot specify options for more links (7) than how many is "
                "defined by number of addresses per node (3)"
            ),
            reports.CorosyncTooManyLinksOptions(7, 3),
        )


class CorosyncCannotAddRemoveLinksBadTransport(NameBuildTest):
    def test_add(self):
        self.assert_message_from_report(
            (
                "Cluster is using udp transport which does not support "
                "adding links"
            ),
            reports.CorosyncCannotAddRemoveLinksBadTransport(
                "udp", ["knet1", "knet2"], add_or_not_remove=True
            ),
        )

    def test_remove(self):
        self.assert_message_from_report(
            (
                "Cluster is using udpu transport which does not support "
                "removing links"
            ),
            reports.CorosyncCannotAddRemoveLinksBadTransport(
                "udpu", ["knet"], add_or_not_remove=False
            ),
        )


class CorosyncCannotAddRemoveLinksNoLinksSpecified(NameBuildTest):
    def test_add(self):
        self.assert_message_from_report(
            "Cannot add links, no links to add specified",
            reports.CorosyncCannotAddRemoveLinksNoLinksSpecified(
                add_or_not_remove=True
            ),
        )

    def test_remove(self):
        self.assert_message_from_report(
            "Cannot remove links, no links to remove specified",
            reports.CorosyncCannotAddRemoveLinksNoLinksSpecified(
                add_or_not_remove=False
            ),
        )


class CorosyncCannotAddRemoveLinksTooManyFewLinks(NameBuildTest):
    def test_add(self):
        self.assert_message_from_report(
            (
                "Cannot add 1 link, there would be 1 link defined which is "
                "more than allowed number of 1 link"
            ),
            reports.CorosyncCannotAddRemoveLinksTooManyFewLinks(
                1, 1, 1, add_or_not_remove=True
            ),
        )

    def test_add_s(self):
        self.assert_message_from_report(
            (
                "Cannot add 2 links, there would be 4 links defined which is "
                "more than allowed number of 3 links"
            ),
            reports.CorosyncCannotAddRemoveLinksTooManyFewLinks(
                2, 4, 3, add_or_not_remove=True
            ),
        )

    def test_remove(self):
        self.assert_message_from_report(
            (
                "Cannot remove 1 link, there would be 1 link defined which is "
                "less than allowed number of 1 link"
            ),
            reports.CorosyncCannotAddRemoveLinksTooManyFewLinks(
                1, 1, 1, add_or_not_remove=False
            ),
        )

    def test_remove_s(self):
        self.assert_message_from_report(
            (
                "Cannot remove 3 links, there would be 0 links defined which "
                "is less than allowed number of 2 links"
            ),
            reports.CorosyncCannotAddRemoveLinksTooManyFewLinks(
                3, 0, 2, add_or_not_remove=False
            ),
        )


class CorosyncLinkAlreadyExistsCannotAdd(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot add link '2', it already exists",
            reports.CorosyncLinkAlreadyExistsCannotAdd("2"),
        )


class CorosyncLinkDoesNotExistCannotRemove(NameBuildTest):
    def test_single_link(self):
        self.assert_message_from_report(
            ("Cannot remove non-existent link 'abc', existing links: '5'"),
            reports.CorosyncLinkDoesNotExistCannotRemove(["abc"], ["5"]),
        )

    def test_multiple_links(self):
        self.assert_message_from_report(
            (
                "Cannot remove non-existent links '0', '1', 'abc', existing "
                "links: '2', '3', '5'"
            ),
            reports.CorosyncLinkDoesNotExistCannotRemove(
                ["1", "0", "abc"], ["3", "2", "5"]
            ),
        )


class CorosyncLinkDoesNotExistCannotUpdate(NameBuildTest):
    def test_link_list_several(self):
        self.assert_message_from_report(
            (
                "Cannot set options for non-existent link '3'"
                ", existing links: '0', '1', '2', '6', '7'"
            ),
            reports.CorosyncLinkDoesNotExistCannotUpdate(
                3, ["6", "7", "0", "1", "2"]
            ),
        )

    def test_link_list_one(self):
        self.assert_message_from_report(
            (
                "Cannot set options for non-existent link '3'"
                ", existing links: '0'"
            ),
            reports.CorosyncLinkDoesNotExistCannotUpdate(3, ["0"]),
        )


class CorosyncTransportUnsupportedOptions(NameBuildTest):
    def test_udp(self):
        self.assert_message_from_report(
            "The udp/udpu transport does not support 'crypto' options, use "
            "'knet' transport",
            reports.CorosyncTransportUnsupportedOptions(
                "crypto", "udp/udpu", ["knet"]
            ),
        )

    def test_multiple_supported_transports(self):
        self.assert_message_from_report(
            "The udp/udpu transport does not support 'crypto' options, use "
            "'knet', 'knet2' transport",
            reports.CorosyncTransportUnsupportedOptions(
                "crypto", "udp/udpu", ["knet", "knet2"]
            ),
        )


class ClusterUuidAlreadySet(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Cluster UUID has already been set", reports.ClusterUuidAlreadySet()
        )


class QdeviceAlreadyDefined(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "quorum device is already defined", reports.QdeviceAlreadyDefined()
        )


class QdeviceNotDefined(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "no quorum device is defined in this cluster",
            reports.QdeviceNotDefined(),
        )


class QdeviceClientReloadStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Reloading qdevice configuration on nodes...",
            reports.QdeviceClientReloadStarted(),
        )


class QdeviceAlreadyInitialized(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' has been already initialized",
            reports.QdeviceAlreadyInitialized("model"),
        )


class QdeviceNotInitialized(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' has not been initialized yet",
            reports.QdeviceNotInitialized("model"),
        )


class QdeviceInitializationSuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' initialized",
            reports.QdeviceInitializationSuccess("model"),
        )


class QdeviceInitializationError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to initialize quorum device 'model': reason",
            reports.QdeviceInitializationError("model", "reason"),
        )


class QdeviceCertificateDistributionStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Setting up qdevice certificates on nodes...",
            reports.QdeviceCertificateDistributionStarted(),
        )


class QdeviceCertificateAcceptedByNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Succeeded",
            reports.QdeviceCertificateAcceptedByNode("node1"),
        )


class QdeviceCertificateRemovalStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Removing qdevice certificates from nodes...",
            reports.QdeviceCertificateRemovalStarted(),
        )


class QdeviceCertificateRemovedFromNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node2: Succeeded",
            reports.QdeviceCertificateRemovedFromNode("node2"),
        )


class QdeviceCertificateImportError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to import quorum device certificate: reason",
            reports.QdeviceCertificateImportError("reason"),
        )


class QdeviceCertificateSignError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to sign quorum device certificate: reason",
            reports.QdeviceCertificateSignError("reason"),
        )


class QdeviceCertificateBadFormat(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to parse quorum device certificate",
            reports.QdeviceCertificateBadFormat(),
        )


class QdeviceCertificateReadError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to read quorum device certificate: reason",
            reports.QdeviceCertificateReadError("reason"),
        )


class QdeviceDestroySuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' configuration files removed",
            reports.QdeviceDestroySuccess("model"),
        )


class QdeviceDestroyError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to destroy quorum device 'model': reason",
            reports.QdeviceDestroyError("model", "reason"),
        )


class QdeviceNotRunning(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Quorum device 'model' is not running",
            reports.QdeviceNotRunning("model"),
        )


class QdeviceGetStatusError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to get status of quorum device 'model': reason",
            reports.QdeviceGetStatusError("model", "reason"),
        )


class QdeviceUsedByClusters(NameBuildTest):
    def test_single_cluster(self):
        self.assert_message_from_report(
            "Quorum device is currently being used by cluster(s): 'c1'",
            reports.QdeviceUsedByClusters(["c1"]),
        )

    def test_multiple_clusters(self):
        self.assert_message_from_report(
            "Quorum device is currently being used by cluster(s): 'c1', 'c2'",
            reports.QdeviceUsedByClusters(["c1", "c2"]),
        )


class IdAlreadyExists(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "'id' already exists", reports.IdAlreadyExists("id")
        )


class IdBelongsToUnexpectedType(NameBuildTest):
    def test_build_message_with_single_type(self):
        self.assert_message_from_report(
            "'ID' is not an ACL permission",
            reports.IdBelongsToUnexpectedType("ID", ["acl_permission"], "op"),
        )

    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "'ID' is not a clone/resource",
            reports.IdBelongsToUnexpectedType(
                "ID", ["primitive", "clone"], "op"
            ),
        )

    def test_build_message_with_transformation_and_article(self):
        self.assert_message_from_report(
            "'ID' is not an ACL group/ACL user",
            reports.IdBelongsToUnexpectedType(
                "ID",
                ["acl_target", "acl_group"],
                "op",
            ),
        )


class ObjectWithIdInUnexpectedContext(NameBuildTest):
    def test_with_context_id(self):
        self.assert_message_from_report(
            "resource 'R' exists but does not belong to group 'G'",
            reports.ObjectWithIdInUnexpectedContext(
                "primitive", "R", "group", "G"
            ),
        )

    def test_without_context_id(self):
        self.assert_message_from_report(
            "group 'G' exists but does not belong to 'resource'",
            reports.ObjectWithIdInUnexpectedContext(
                "group", "G", "primitive", ""
            ),
        )


class IdNotFound(NameBuildTest):
    def test_id(self):
        self.assert_message_from_report(
            "'ID' does not exist", reports.IdNotFound("ID", [])
        )

    def test_id_and_type(self):
        self.assert_message_from_report(
            "clone/resource 'ID' does not exist",
            reports.IdNotFound("ID", ["primitive", "clone"]),
        )

    def test_context(self):
        self.assert_message_from_report(
            "there is no 'ID' in the C_TYPE 'C_ID'",
            reports.IdNotFound(
                "ID", [], context_type="C_TYPE", context_id="C_ID"
            ),
        )

    def test_type_and_context(self):
        self.assert_message_from_report(
            "there is no ACL user 'ID' in the C_TYPE 'C_ID'",
            reports.IdNotFound(
                "ID", ["acl_target"], context_type="C_TYPE", context_id="C_ID"
            ),
        )


class ResourceBundleAlreadyContainsAResource(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            (
                "bundle 'test_bundle' already contains resource "
                "'test_resource', a bundle may contain at most one resource"
            ),
            reports.ResourceBundleAlreadyContainsAResource(
                "test_bundle", "test_resource"
            ),
        )


class CannotGroupResourceWrongType(NameBuildTest):
    def test_without_parent(self):
        self.assert_message_from_report(
            (
                "'R' is a clone resource, clone resources cannot be put into "
                "a group"
            ),
            reports.CannotGroupResourceWrongType("R", "master", None, None),
        )

    def test_with_parent(self):
        self.assert_message_from_report(
            (
                "'R' cannot be put into a group because its parent 'B' "
                "is a bundle resource"
            ),
            reports.CannotGroupResourceWrongType(
                "R", "primitive", "B", "bundle"
            ),
        )


class UnableToGetResourceOperationDigests(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "unable to get resource operation digests:\ncrm_resource output",
            reports.UnableToGetResourceOperationDigests("crm_resource output"),
        )


class StonithResourcesDoNotExist(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Stonith resource(s) 'device1', 'device2' do not exist",
            reports.StonithResourcesDoNotExist(["device2", "device1"]),
        )


class StonithRestartlessUpdateOfScsiDevicesNotSupported(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Restartless update of scsi devices is not supported, please "
                "upgrade pacemaker"
            ),
            reports.StonithRestartlessUpdateOfScsiDevicesNotSupported(),
        )


class StonithRestartlessUpdateUnsupportedAgent(NameBuildTest):
    def test_plural(self):
        self.assert_message_from_report(
            (
                "Resource 'fence_sbd' is not a stonith resource or its type "
                "'wrong_type' is not supported for devices update. Supported "
                "types: 'fence_mpath', 'fence_scsi'"
            ),
            reports.StonithRestartlessUpdateUnsupportedAgent(
                "fence_sbd", "wrong_type", ["fence_scsi", "fence_mpath"]
            ),
        )

    def test_singular(self):
        self.assert_message_from_report(
            (
                "Resource 'fence_sbd' is not a stonith resource or its type "
                "'wrong_type' is not supported for devices update. Supported "
                "type: 'fence_scsi'"
            ),
            reports.StonithRestartlessUpdateUnsupportedAgent(
                "fence_sbd", "wrong_type", ["fence_scsi"]
            ),
        )


class StonithUnfencingFailed(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            ("Unfencing failed:\nreason"),
            reports.StonithUnfencingFailed("reason"),
        )


class StonithUnfencingDeviceStatusFailed(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Unfencing failed, unable to check status of device 'dev1': reason",
            reports.StonithUnfencingDeviceStatusFailed("dev1", "reason"),
        )


class StonithUnfencingSkippedDevicesFenced(NameBuildTest):
    def test_one_device(self):
        self.assert_message_from_report(
            "Unfencing skipped, device 'dev1' is fenced",
            reports.StonithUnfencingSkippedDevicesFenced(["dev1"]),
        )

    def test_multiple_devices(self):
        self.assert_message_from_report(
            "Unfencing skipped, devices 'dev1', 'dev2', 'dev3' are fenced",
            reports.StonithUnfencingSkippedDevicesFenced(
                ["dev2", "dev1", "dev3"]
            ),
        )


class StonithRestartlessUpdateUnableToPerform(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Unable to perform restartless update of scsi devices: reason",
            reports.StonithRestartlessUpdateUnableToPerform("reason"),
        )

    def test_build_message_reason_type_specified(self):
        self.assert_message_from_report(
            "Unable to perform restartless update of scsi devices: reason",
            reports.StonithRestartlessUpdateUnableToPerform(
                "reason",
                const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_NOT_RUNNING,
            ),
        )


class StonithRestartlessUpdateMissingMpathKeys(NameBuildTest):
    def test_plural(self):
        self.assert_message_from_report(
            (
                "Missing mpath reservation keys for nodes: 'rh9-2', 'rh9-3', "
                "in 'pcmk_host_map' value: 'rh9-1:1'"
            ),
            reports.StonithRestartlessUpdateMissingMpathKeys(
                "rh9-1:1", ["rh9-2", "rh9-3"]
            ),
        )

    def test_singular(self):
        self.assert_message_from_report(
            (
                "Missing mpath reservation key for node: 'rh9-2', "
                "in 'pcmk_host_map' value: 'rh9-1:1'"
            ),
            reports.StonithRestartlessUpdateMissingMpathKeys(
                "rh9-1:1", ["rh9-2"]
            ),
        )

    def test_missing_map_and_empty_nodes(self):
        self.assert_message_from_report(
            "Missing mpath reservation keys, 'pcmk_host_map' not set",
            reports.StonithRestartlessUpdateMissingMpathKeys(None, []),
        )

    def test_missing_map_non_empty_nodes(self):
        self.assert_message_from_report(
            "Missing mpath reservation keys, 'pcmk_host_map' not set",
            reports.StonithRestartlessUpdateMissingMpathKeys(
                None, ["rh9-1", "rh9-2"]
            ),
        )

    def test_non_empty_map_empty_nodes(self):
        self.assert_message_from_report(
            (
                "Missing mpath reservation keys for nodes in 'pcmk_host_map' "
                "value: 'rh-1:1'"
            ),
            reports.StonithRestartlessUpdateMissingMpathKeys("rh-1:1", []),
        )


class ResourceRunningOnNodes(NameBuildTest):
    def test_one_node(self):
        self.assert_message_from_report(
            "resource 'R' is running on node 'node1'",
            reports.ResourceRunningOnNodes("R", {"Started": ["node1"]}),
        )

    def test_multiple_nodes(self):
        self.assert_message_from_report(
            "resource 'R' is running on nodes 'node1', 'node2'",
            reports.ResourceRunningOnNodes(
                "R", {"Started": ["node1", "node2"]}
            ),
        )

    def test_multiple_role_multiple_nodes(self):
        self.assert_message_from_report(
            "resource 'R' is promoted on node 'node3'"
            "; running on nodes 'node1', 'node2'",
            reports.ResourceRunningOnNodes(
                "R",
                {
                    "Started": ["node1", "node2"],
                    "Promoted": ["node3"],
                },
            ),
        )


class ResourceDoesNotRun(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "resource 'R' is not running on any node",
            reports.ResourceDoesNotRun("R"),
        )


class ResourceIsGuestNodeAlready(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "the resource 'some-resource' is already a guest node",
            reports.ResourceIsGuestNodeAlready("some-resource"),
        )


class ResourceIsUnmanaged(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "'R' is unmanaged", reports.ResourceIsUnmanaged("R")
        )


class ResourceManagedNoMonitorEnabled(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Resource 'R' has no enabled monitor operations",
            reports.ResourceManagedNoMonitorEnabled("R"),
        )


class CibLoadError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unable to get cib", reports.CibLoadError("reason")
        )


class CibLoadErrorGetNodesForValidation(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Unable to load CIB to get guest and remote nodes from it, "
                "those nodes cannot be considered in configuration validation"
            ),
            reports.CibLoadErrorGetNodesForValidation(),
        )


class CibLoadErrorScopeMissing(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unable to get cib, scope 'scope-name' not present in cib",
            reports.CibLoadErrorScopeMissing("scope-name", "reason"),
        )


class CibLoadErrorBadFormat(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "unable to get cib, something wrong",
            reports.CibLoadErrorBadFormat("something wrong"),
        )


class CibCannotFindMandatorySection(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to get 'section-name' section of cib",
            reports.CibCannotFindMandatorySection("section-name"),
        )


class CibPushError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to update cib\nreason\npushed-cib",
            reports.CibPushError("reason", "pushed-cib"),
        )


class CibSaveTmpError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to save CIB to a temporary file: reason",
            reports.CibSaveTmpError("reason"),
        )


class CibDiffError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to diff CIB: error message\n<cib-new />",
            reports.CibDiffError("error message", "<cib-old />", "<cib-new />"),
        )


class CibSimulateError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to simulate changes in CIB: error message",
            reports.CibSimulateError("error message"),
        )

    def test_empty_reason(self):
        self.assert_message_from_report(
            "Unable to simulate changes in CIB",
            reports.CibSimulateError(""),
        )


class CrmMonError(NameBuildTest):
    def test_without_reason(self):
        self.assert_message_from_report(
            "error running crm_mon, is pacemaker running?",
            reports.CrmMonError(""),
        )

    def test_with_reason(self):
        self.assert_message_from_report(
            (
                "error running crm_mon, is pacemaker running?"
                "\n  reason\n  spans several lines"
            ),
            reports.CrmMonError("reason\nspans several lines"),
        )


class BadClusterStateFormat(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "cannot load cluster status, xml does not conform to the schema",
            reports.BadClusterStateFormat(),
        )


class BadClusterStateData(NameBuildTest):
    def test_no_reason(self):
        self.assert_message_from_report(
            (
                "Cannot load cluster status, xml does not describe "
                "valid cluster status"
            ),
            reports.BadClusterStateData(),
        )

    def test_reason(self):
        self.assert_message_from_report(
            (
                "Cannot load cluster status, xml does not describe "
                "valid cluster status: sample reason"
            ),
            reports.BadClusterStateData("sample reason"),
        )


class WaitForIdleStarted(NameBuildTest):
    def test_timeout(self):
        timeout = 20
        self.assert_message_from_report(
            (
                "Waiting for the cluster to apply configuration changes "
                f"(timeout: {timeout} seconds)..."
            ),
            reports.WaitForIdleStarted(timeout),
        )

    def test_timeout_singular(self):
        timeout = 1
        self.assert_message_from_report(
            (
                "Waiting for the cluster to apply configuration changes "
                f"(timeout: {timeout} second)..."
            ),
            reports.WaitForIdleStarted(timeout),
        )

    def test_timeout_0(self):
        self.assert_message_from_report(
            "Waiting for the cluster to apply configuration changes...",
            reports.WaitForIdleStarted(0),
        )

    def test_timeout_negative(self):
        self.assert_message_from_report(
            "Waiting for the cluster to apply configuration changes...",
            reports.WaitForIdleStarted(-1),
        )


class WaitForIdleTimedOut(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "waiting timeout\n\nreason", reports.WaitForIdleTimedOut("reason")
        )


class WaitForIdleError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "reason", reports.WaitForIdleError("reason")
        )


class WaitForIdleNotLiveCluster(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Cannot use 'mocked CIB' together with 'wait'",
            reports.WaitForIdleNotLiveCluster(),
        )


class ResourceCleanupError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to forget failed operations of resources\nsomething wrong",
            reports.ResourceCleanupError("something wrong"),
        )

    def test_node(self):
        self.assert_message_from_report(
            "Unable to forget failed operations of resources\nsomething wrong",
            reports.ResourceCleanupError("something wrong", node="N1"),
        )

    def test_resource(self):
        self.assert_message_from_report(
            "Unable to forget failed operations of resource: R1\n"
            "something wrong",
            reports.ResourceCleanupError("something wrong", "R1"),
        )

    def test_resource_and_node(self):
        self.assert_message_from_report(
            "Unable to forget failed operations of resource: R1\n"
            "something wrong",
            reports.ResourceCleanupError("something wrong", "R1", "N1"),
        )


class ResourceRefreshError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to delete history of resources\nsomething wrong",
            reports.ResourceRefreshError("something wrong"),
        )

    def test_node(self):
        self.assert_message_from_report(
            "Unable to delete history of resources\nsomething wrong",
            reports.ResourceRefreshError(
                "something wrong",
                node="N1",
            ),
        )

    def test_resource(self):
        self.assert_message_from_report(
            "Unable to delete history of resource: R1\nsomething wrong",
            reports.ResourceRefreshError("something wrong", "R1"),
        )

    def test_resource_and_node(self):
        self.assert_message_from_report(
            "Unable to delete history of resource: R1\nsomething wrong",
            reports.ResourceRefreshError("something wrong", "R1", "N1"),
        )


class ResourceRefreshTooTimeConsuming(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Deleting history of all resources on all nodes will execute more "
            "than 25 operations in the cluster, which may negatively "
            "impact the responsiveness of the cluster. Consider specifying "
            "resource and/or node",
            reports.ResourceRefreshTooTimeConsuming(25),
        )


class ResourceOperationIntervalDuplication(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "multiple specification of the same operation with the same"
            " interval:"
            "\nmonitor with intervals 3600s, 60m, 1h"
            "\nmonitor with intervals 60s, 1m",
            reports.ResourceOperationIntervalDuplication(
                {
                    "monitor": [
                        ["3600s", "60m", "1h"],
                        ["60s", "1m"],
                    ],
                }
            ),
        )


class ResourceOperationIntervalAdapted(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "changing a monitor operation interval from 10 to 11 to make the"
            " operation unique",
            reports.ResourceOperationIntervalAdapted("monitor", "10", "11"),
        )


class NodeNotFound(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "Node 'SOME_NODE' does not appear to exist in configuration",
            reports.NodeNotFound("SOME_NODE"),
        )

    def test_build_messages_with_one_search_types(self):
        self.assert_message_from_report(
            "remote node 'SOME_NODE' does not appear to exist in configuration",
            reports.NodeNotFound("SOME_NODE", ["remote"]),
        )

    def test_build_messages_with_multiple_search_types(self):
        self.assert_message_from_report(
            "nor remote node or guest node 'SOME_NODE' does not appear to exist"
            " in configuration",
            reports.NodeNotFound("SOME_NODE", ["remote", "guest"]),
        )


class NodeToClearIsStillInCluster(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node 'node1' seems to be still in the cluster"
            "; this command should be used only with nodes that have been"
            " removed from the cluster",
            reports.NodeToClearIsStillInCluster("node1"),
        )


class NodeRemoveInPacemakerFailed(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            ("Unable to remove node(s) 'NODE1', 'NODE2' from pacemaker"),
            reports.NodeRemoveInPacemakerFailed(["NODE2", "NODE1"]),
        )

    def test_without_node(self):
        self.assert_message_from_report(
            "Unable to remove node(s) 'NODE' from pacemaker: reason",
            reports.NodeRemoveInPacemakerFailed(["NODE"], reason="reason"),
        )

    def test_with_node(self):
        self.assert_message_from_report(
            (
                "node-a: Unable to remove node(s) 'NODE1', 'NODE2' from "
                "pacemaker: reason"
            ),
            reports.NodeRemoveInPacemakerFailed(
                ["NODE1", "NODE2"], node="node-a", reason="reason"
            ),
        )


class MultipleResultsFound(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "more than one resource found: 'ID1', 'ID2'",
            reports.MultipleResultsFound("resource", ["ID2", "ID1"]),
        )

    def test_build_messages(self):
        self.assert_message_from_report(
            "more than one resource for 'NODE-NAME' found: 'ID1', 'ID2'",
            reports.MultipleResultsFound(
                "resource", ["ID2", "ID1"], "NODE-NAME"
            ),
        )


class PacemakerSimulationResult(NameBuildTest):
    def test_default(self):
        self.assert_message_from_report(
            "\nSimulation result:\ncrm_simulate output",
            reports.PacemakerSimulationResult("crm_simulate output"),
        )


class PacemakerLocalNodeNameNotFound(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unable to get local node name from pacemaker: reason",
            reports.PacemakerLocalNodeNameNotFound("reason"),
        )


class ServiceActionStarted(NameBuildTest):
    def test_start(self):
        self.assert_message_from_report(
            "Starting a_service...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_START, "a_service"
            ),
        )

    def test_start_instance(self):
        self.assert_message_from_report(
            "Starting a_service@an_instance...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_START, "a_service", "an_instance"
            ),
        )

    def test_stop(self):
        self.assert_message_from_report(
            "Stopping a_service...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_STOP, "a_service"
            ),
        )

    def test_stop_instance(self):
        self.assert_message_from_report(
            "Stopping a_service@an_instance...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_STOP, "a_service", "an_instance"
            ),
        )

    def test_enable(self):
        self.assert_message_from_report(
            "Enabling a_service...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_ENABLE, "a_service"
            ),
        )

    def test_enable_instance(self):
        self.assert_message_from_report(
            "Enabling a_service@an_instance...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_ENABLE, "a_service", "an_instance"
            ),
        )

    def test_disable(self):
        self.assert_message_from_report(
            "Disabling a_service...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_DISABLE, "a_service"
            ),
        )

    def test_disable_instance(self):
        self.assert_message_from_report(
            "Disabling a_service@an_instance...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_DISABLE, "a_service", "an_instance"
            ),
        )

    def test_kill(self):
        self.assert_message_from_report(
            "Killing a_service...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_KILL, "a_service"
            ),
        )

    def test_kill_instance(self):
        self.assert_message_from_report(
            "Killing a_service@an_instance...",
            reports.ServiceActionStarted(
                const.SERVICE_ACTION_KILL, "a_service", "an_instance"
            ),
        )


# TODO: add tests for node if needed
class ServiceActionFailed(NameBuildTest):
    def test_start(self):
        self.assert_message_from_report(
            "Unable to start a_service: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_START, "a_service", "a_reason"
            ),
        )

    def test_start_instance(self):
        self.assert_message_from_report(
            "Unable to start a_service@an_instance: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_START,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )

    def test_stop(self):
        self.assert_message_from_report(
            "Unable to stop a_service: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_STOP, "a_service", "a_reason"
            ),
        )

    def test_stop_instance(self):
        self.assert_message_from_report(
            "Unable to stop a_service@an_instance: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_STOP,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )

    def test_enable(self):
        self.assert_message_from_report(
            "Unable to enable a_service: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_ENABLE, "a_service", "a_reason"
            ),
        )

    def test_enable_instance(self):
        self.assert_message_from_report(
            "Unable to enable a_service@an_instance: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_ENABLE,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )

    def test_disable(self):
        self.assert_message_from_report(
            "Unable to disable a_service: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_DISABLE, "a_service", "a_reason"
            ),
        )

    def test_disable_instance(self):
        self.assert_message_from_report(
            "Unable to disable a_service@an_instance: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_DISABLE,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )

    def test_kill(self):
        self.assert_message_from_report(
            "Unable to kill a_service: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_KILL, "a_service", "a_reason"
            ),
        )

    def test_kill_instance(self):
        self.assert_message_from_report(
            "Unable to kill a_service@an_instance: a_reason",
            reports.ServiceActionFailed(
                const.SERVICE_ACTION_KILL,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )


# TODO: add tests for node if needed
class ServiceActionSucceeded(NameBuildTest):
    def test_start(self):
        self.assert_message_from_report(
            "a_service started",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_START, "a_service"
            ),
        )

    def test_start_instance(self):
        self.assert_message_from_report(
            "a_service@an_instance started",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_START, "a_service", instance="an_instance"
            ),
        )

    def test_stop(self):
        self.assert_message_from_report(
            "a_service stopped",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_STOP, "a_service"
            ),
        )

    def test_stop_instance(self):
        self.assert_message_from_report(
            "a_service@an_instance stopped",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_STOP, "a_service", instance="an_instance"
            ),
        )

    def test_enable(self):
        self.assert_message_from_report(
            "a_service enabled",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_ENABLE, "a_service"
            ),
        )

    def test_enable_instance(self):
        self.assert_message_from_report(
            "a_service@an_instance enabled",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_ENABLE, "a_service", instance="an_instance"
            ),
        )

    def test_disable(self):
        self.assert_message_from_report(
            "a_service disabled",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_DISABLE, "a_service"
            ),
        )

    def test_disable_instance(self):
        self.assert_message_from_report(
            "a_service@an_instance disabled",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_DISABLE,
                "a_service",
                instance="an_instance",
            ),
        )

    def test_kill(self):
        self.assert_message_from_report(
            "a_service killed",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_KILL, "a_service"
            ),
        )

    def test_kill_instance(self):
        self.assert_message_from_report(
            "a_service@an_instance killed",
            reports.ServiceActionSucceeded(
                const.SERVICE_ACTION_KILL, "a_service", instance="an_instance"
            ),
        )


class ServiceActionSkipped(NameBuildTest):
    def test_start(self):
        self.assert_message_from_report(
            "not starting a_service: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_START, "a_service", "a_reason"
            ),
        )

    def test_start_instance(self):
        self.assert_message_from_report(
            "not starting a_service@an_instance: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_START,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )

    def test_stop(self):
        self.assert_message_from_report(
            "not stopping a_service: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_STOP, "a_service", "a_reason"
            ),
        )

    def test_stop_instance(self):
        self.assert_message_from_report(
            "not stopping a_service@an_instance: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_STOP,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )

    def test_enable(self):
        self.assert_message_from_report(
            "not enabling a_service: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_ENABLE, "a_service", "a_reason"
            ),
        )

    def test_enable_instance(self):
        self.assert_message_from_report(
            "not enabling a_service@an_instance: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_ENABLE,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )

    def test_disable(self):
        self.assert_message_from_report(
            "not disabling a_service: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_DISABLE, "a_service", "a_reason"
            ),
        )

    def test_disable_instance(self):
        self.assert_message_from_report(
            "not disabling a_service@an_instance: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_DISABLE,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )

    def test_kill(self):
        self.assert_message_from_report(
            "not killing a_service: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_KILL, "a_service", "a_reason"
            ),
        )

    def test_kill_instance(self):
        self.assert_message_from_report(
            "not killing a_service@an_instance: a_reason",
            reports.ServiceActionSkipped(
                const.SERVICE_ACTION_KILL,
                "a_service",
                "a_reason",
                instance="an_instance",
            ),
        )


class ServiceUnableToDetectInitSystem(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Unable to detect init system. All actions related to system "
                "services will be skipped."
            ),
            reports.ServiceUnableToDetectInitSystem(),
        )


class UnableToGetAgentMetadata(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Agent 'agent-name' is not installed or does not provide valid "
                "metadata: reason"
            ),
            reports.UnableToGetAgentMetadata("agent-name", "reason"),
        )


class InvalidResourceAgentName(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "Invalid resource agent name ':name'. Use standard:provider:type "
            "when standard is 'ocf' or standard:type otherwise.",
            reports.InvalidResourceAgentName(":name"),
        )


class InvalidStonithAgentName(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "Invalid stonith agent name 'fence:name'. Agent name cannot contain "
            "the ':' character, do not use the 'stonith:' prefix.",
            reports.InvalidStonithAgentName("fence:name"),
        )


class AgentNameGuessed(NameBuildTest):
    def test_build_message_with_data(self):
        self.assert_message_from_report(
            "Assumed agent name 'ocf:heartbeat:Delay' (deduced from 'Delay')",
            reports.AgentNameGuessed("Delay", "ocf:heartbeat:Delay"),
        )


class AgentNameGuessFoundMoreThanOne(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Multiple agents match 'agent', please specify full name: "
                "'agent1', 'agent2' or 'agent3'"
            ),
            reports.AgentNameGuessFoundMoreThanOne(
                "agent", ["agent2", "agent1", "agent3"]
            ),
        )


class AgentNameGuessFoundNone(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to find agent 'agent-name', try specifying its full name",
            reports.AgentNameGuessFoundNone("agent-name"),
        )


class AgentImplementsUnsupportedOcfVersion(NameBuildTest):
    def test_singular(self):
        self.assert_message_from_report(
            "Unable to process agent 'agent-name' as it implements unsupported "
            "OCF version 'ocf-2.3', supported version is: 'v1'",
            reports.AgentImplementsUnsupportedOcfVersion(
                "agent-name", "ocf-2.3", ["v1"]
            ),
        )

    def test_plural(self):
        self.assert_message_from_report(
            "Unable to process agent 'agent-name' as it implements unsupported "
            "OCF version 'ocf-2.3', supported versions are: 'v1', 'v2', 'v3'",
            reports.AgentImplementsUnsupportedOcfVersion(
                "agent-name", "ocf-2.3", ["v1", "v2", "v3"]
            ),
        )


class AgentGenericError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to load agent 'agent-name'",
            reports.AgentGenericError("agent-name"),
        )


class OmittingNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Omitting node 'node1'", reports.OmittingNode("node1")
        )


class SbdCheckStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Running SBD pre-enabling checks...", reports.SbdCheckStarted()
        )


class SbdCheckSuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: SBD pre-enabling checks done",
            reports.SbdCheckSuccess("node1"),
        )


class SbdConfigDistributionStarted(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Distributing SBD config...", reports.SbdConfigDistributionStarted()
        )


class SbdConfigAcceptedByNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: SBD config saved", reports.SbdConfigAcceptedByNode("node1")
        )


class UnableToGetSbdConfig(NameBuildTest):
    def test_no_reason(self):
        self.assert_message_from_report(
            "Unable to get SBD configuration from node 'node1'",
            reports.UnableToGetSbdConfig("node1", ""),
        )

    def test_all(self):
        self.assert_message_from_report(
            "Unable to get SBD configuration from node 'node2': reason",
            reports.UnableToGetSbdConfig("node2", "reason"),
        )


class SbdDeviceInitializationStarted(NameBuildTest):
    def test_more_devices(self):
        self.assert_message_from_report(
            "Initializing devices '/dev1', '/dev2', '/dev3'...",
            reports.SbdDeviceInitializationStarted(["/dev3", "/dev2", "/dev1"]),
        )

    def test_one_device(self):
        self.assert_message_from_report(
            "Initializing device '/dev1'...",
            reports.SbdDeviceInitializationStarted(["/dev1"]),
        )


class SbdDeviceInitializationSuccess(NameBuildTest):
    def test_more_devices(self):
        self.assert_message_from_report(
            "Devices initialized successfully",
            reports.SbdDeviceInitializationSuccess(["/dev2", "/dev1"]),
        )

    def test_one_device(self):
        self.assert_message_from_report(
            "Device initialized successfully",
            reports.SbdDeviceInitializationSuccess(["/dev1"]),
        )


class SbdDeviceInitializationError(NameBuildTest):
    def test_more_devices(self):
        self.assert_message_from_report(
            "Initialization of devices '/dev1', '/dev2' failed: this is reason",
            reports.SbdDeviceInitializationError(
                ["/dev2", "/dev1"], "this is reason"
            ),
        )

    def test_one_device(self):
        self.assert_message_from_report(
            "Initialization of device '/dev2' failed: this is reason",
            reports.SbdDeviceInitializationError(["/dev2"], "this is reason"),
        )


class SbdDeviceListError(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Unable to get list of messages from device '/dev': this is reason",
            reports.SbdDeviceListError("/dev", "this is reason"),
        )


class SbdDeviceMessageError(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            (
                "Unable to set message 'test' for node 'node1' on device "
                "'/dev1': this is reason"
            ),
            reports.SbdDeviceMessageError(
                "/dev1", "node1", "test", "this is reason"
            ),
        )


class SbdDeviceDumpError(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Unable to get SBD headers from device '/dev1': this is reason",
            reports.SbdDeviceDumpError("/dev1", "this is reason"),
        )


class FilesDistributionStarted(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "Sending 'first', 'second'",
            reports.FilesDistributionStarted(["first", "second"]),
        )

    def test_build_messages_with_single_node(self):
        self.assert_message_from_report(
            "Sending 'first' to 'node1'",
            reports.FilesDistributionStarted(["first"], ["node1"]),
        )

    def test_build_messages_with_nodes(self):
        self.assert_message_from_report(
            "Sending 'first', 'second' to 'node1', 'node2'",
            reports.FilesDistributionStarted(
                ["first", "second"], ["node1", "node2"]
            ),
        )


class FilesDistributionSkipped(NameBuildTest):
    def test_not_live(self):
        self.assert_message_from_report(
            "Distribution of 'file1' to 'nodeA', 'nodeB' was skipped because "
            "the command does not run on a live cluster. "
            "Please, distribute the file(s) manually.",
            reports.FilesDistributionSkipped(
                const.REASON_NOT_LIVE_CIB, ["file1"], ["nodeA", "nodeB"]
            ),
        )

    def test_unreachable(self):
        self.assert_message_from_report(
            "Distribution of 'file1', 'file2' to 'nodeA' was skipped because "
            "pcs is unable to connect to the node(s). Please, distribute "
            "the file(s) manually.",
            reports.FilesDistributionSkipped(
                const.REASON_UNREACHABLE, ["file1", "file2"], ["nodeA"]
            ),
        )

    def test_unknown_reason(self):
        self.assert_message_from_report(
            "Distribution of 'file1', 'file2' to 'nodeA', 'nodeB' was skipped "
            "because some undefined reason. Please, distribute the file(s) "
            "manually.",
            reports.FilesDistributionSkipped(
                "some undefined reason", ["file1", "file2"], ["nodeA", "nodeB"]
            ),
        )


class FileDistributionSuccess(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: successful distribution of the file 'some authfile'",
            reports.FileDistributionSuccess("node1", "some authfile"),
        )


class FileDistributionError(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: unable to distribute file 'file1': permission denied",
            reports.FileDistributionError(
                "node1", "file1", "permission denied"
            ),
        )


class FilesRemoveFromNodesStarted(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Requesting remove 'file'",
            reports.FilesRemoveFromNodesStarted(["file"]),
        )

    def test_with_single_node(self):
        self.assert_message_from_report(
            "Requesting remove 'first' from 'node1'",
            reports.FilesRemoveFromNodesStarted(["first"], ["node1"]),
        )

    def test_with_multiple_nodes(self):
        self.assert_message_from_report(
            "Requesting remove 'first', 'second' from 'node1', 'node2'",
            reports.FilesRemoveFromNodesStarted(
                ["first", "second"],
                ["node1", "node2"],
            ),
        )


class FilesRemoveFromNodesSkipped(NameBuildTest):
    def test_not_live(self):
        self.assert_message_from_report(
            "Removing 'file1' from 'nodeA', 'nodeB' was skipped because the "
            "command does not run on a live cluster. "
            "Please, remove the file(s) manually.",
            reports.FilesRemoveFromNodesSkipped(
                const.REASON_NOT_LIVE_CIB, ["file1"], ["nodeA", "nodeB"]
            ),
        )

    def test_unreachable(self):
        self.assert_message_from_report(
            "Removing 'file1', 'file2' from 'nodeA' was skipped because pcs is "
            "unable to connect to the node(s). Please, remove the file(s) "
            "manually.",
            reports.FilesRemoveFromNodesSkipped(
                const.REASON_UNREACHABLE, ["file1", "file2"], ["nodeA"]
            ),
        )

    def test_unknown_reason(self):
        self.assert_message_from_report(
            "Removing 'file1', 'file2' from 'nodeA', 'nodeB' was skipped "
            "because some undefined reason. Please, remove the file(s) "
            "manually.",
            reports.FilesRemoveFromNodesSkipped(
                "some undefined reason", ["file1", "file2"], ["nodeA", "nodeB"]
            ),
        )


class FileRemoveFromNodeSuccess(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: successful removal of the file 'some authfile'",
            reports.FileRemoveFromNodeSuccess("node1", "some authfile"),
        )


class FileRemoveFromNodeError(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: unable to remove file 'file1': permission denied",
            reports.FileRemoveFromNodeError(
                "node1", "file1", "permission denied"
            ),
        )


class ServiceCommandsOnNodesStarted(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "Requesting 'action1', 'action2'",
            reports.ServiceCommandsOnNodesStarted(["action1", "action2"]),
        )

    def test_build_messages_with_single_node(self):
        self.assert_message_from_report(
            "Requesting 'action1' on 'node1'",
            reports.ServiceCommandsOnNodesStarted(
                ["action1"],
                ["node1"],
            ),
        )

    def test_build_messages_with_nodes(self):
        self.assert_message_from_report(
            "Requesting 'action1', 'action2' on 'node1', 'node2'",
            reports.ServiceCommandsOnNodesStarted(
                ["action1", "action2"],
                ["node1", "node2"],
            ),
        )


class ServiceCommandsOnNodesSkipped(NameBuildTest):
    def test_not_live(self):
        self.assert_message_from_report(
            "Running action(s) 'pacemaker_remote enable', 'pacemaker_remote "
            "start' on 'nodeA', 'nodeB' was skipped because the command "
            "does not run on a live cluster. Please, "
            "run the action(s) manually.",
            reports.ServiceCommandsOnNodesSkipped(
                const.REASON_NOT_LIVE_CIB,
                ["pacemaker_remote enable", "pacemaker_remote start"],
                ["nodeA", "nodeB"],
            ),
        )

    def test_unreachable(self):
        self.assert_message_from_report(
            "Running action(s) 'pacemaker_remote enable', 'pacemaker_remote "
            "start' on 'nodeA', 'nodeB' was skipped because pcs is unable "
            "to connect to the node(s). Please, run the action(s) manually.",
            reports.ServiceCommandsOnNodesSkipped(
                const.REASON_UNREACHABLE,
                ["pacemaker_remote enable", "pacemaker_remote start"],
                ["nodeA", "nodeB"],
            ),
        )

    def test_unknown_reason(self):
        self.assert_message_from_report(
            "Running action(s) 'pacemaker_remote enable', 'pacemaker_remote "
            "start' on 'nodeA', 'nodeB' was skipped because some undefined "
            "reason. Please, run the action(s) manually.",
            reports.ServiceCommandsOnNodesSkipped(
                "some undefined reason",
                ["pacemaker_remote enable", "pacemaker_remote start"],
                ["nodeA", "nodeB"],
            ),
        )


class ServiceCommandOnNodeSuccess(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: successful run of 'service enable'",
            reports.ServiceCommandOnNodeSuccess("node1", "service enable"),
        )


class ServiceCommandOnNodeError(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "node1: service command failed: service1 start: permission denied",
            reports.ServiceCommandOnNodeError(
                "node1", "service1 start", "permission denied"
            ),
        )


class InvalidResponseFormat(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Invalid format of response",
            reports.InvalidResponseFormat("node1"),
        )


class SbdNotUsedCannotSetSbdOptions(NameBuildTest):
    def test_single_option(self):
        self.assert_message_from_report(
            "Cluster is not configured to use SBD, cannot specify SBD option(s)"
            " 'device' for node 'node1'",
            reports.SbdNotUsedCannotSetSbdOptions(["device"], "node1"),
        )

    def test_multiple_options(self):
        self.assert_message_from_report(
            "Cluster is not configured to use SBD, cannot specify SBD option(s)"
            " 'device', 'watchdog' for node 'node1'",
            reports.SbdNotUsedCannotSetSbdOptions(
                ["device", "watchdog"], "node1"
            ),
        )


class SbdWithDevicesNotUsedCannotSetDevice(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Cluster is not configured to use SBD with shared storage, cannot "
            "specify SBD devices for node 'node1'",
            reports.SbdWithDevicesNotUsedCannotSetDevice("node1"),
        )


class SbdNoDeviceForNode(NameBuildTest):
    def test_not_enabled(self):
        self.assert_message_from_report(
            "No SBD device specified for node 'node1'",
            reports.SbdNoDeviceForNode("node1"),
        )

    def test_enabled(self):
        self.assert_message_from_report(
            "Cluster uses SBD with shared storage so SBD devices must be "
            "specified for all nodes, no device specified for node 'node1'",
            reports.SbdNoDeviceForNode("node1", sbd_enabled_in_cluster=True),
        )


class SbdTooManyDevicesForNode(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "At most 3 SBD devices can be specified for a node, '/dev1', "
            "'/dev2', '/dev3' specified for node 'node1'",
            reports.SbdTooManyDevicesForNode(
                "node1", ["/dev1", "/dev3", "/dev2"], 3
            ),
        )


class SbdDevicePathNotAbsolute(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "Device path '/dev' on node 'node1' is not absolute",
            reports.SbdDevicePathNotAbsolute("/dev", "node1"),
        )


class SbdDeviceDoesNotExist(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "node1: device '/dev' not found",
            reports.SbdDeviceDoesNotExist("/dev", "node1"),
        )


class SbdDeviceIsNotBlockDevice(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            "node1: device '/dev' is not a block device",
            reports.SbdDeviceIsNotBlockDevice("/dev", "node1"),
        )


class StonithWatchdogTimeoutCannotBeSet(NameBuildTest):
    def test_sbd_not_enabled(self):
        self.assert_message_from_report(
            "stonith-watchdog-timeout can only be unset or set to 0 while SBD "
            "is disabled",
            reports.StonithWatchdogTimeoutCannotBeSet(
                reports.const.SBD_NOT_SET_UP
            ),
        )

    def test_sbd_with_devices(self):
        self.assert_message_from_report(
            "stonith-watchdog-timeout can only be unset or set to 0 while SBD "
            "is enabled with devices",
            reports.StonithWatchdogTimeoutCannotBeSet(
                reports.const.SBD_SET_UP_WITH_DEVICES
            ),
        )


class StonithWatchdogTimeoutCannotBeUnset(NameBuildTest):
    def test_sbd_without_devices(self):
        self.assert_message_from_report(
            "stonith-watchdog-timeout cannot be unset or set to 0 while SBD "
            "is enabled without devices",
            reports.StonithWatchdogTimeoutCannotBeUnset(
                reports.const.SBD_SET_UP_WITHOUT_DEVICES
            ),
        )


class StonithWatchdogTimeoutTooSmall(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "The stonith-watchdog-timeout must be greater than SBD watchdog "
            "timeout '5', entered '4'",
            reports.StonithWatchdogTimeoutTooSmall(5, "4"),
        )


class WatchdogNotFound(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Watchdog 'watchdog-name' does not exist on node 'node1'",
            reports.WatchdogNotFound("node1", "watchdog-name"),
        )


class WatchdogInvalid(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Watchdog path '/dev/wdog' is invalid.",
            reports.WatchdogInvalid("/dev/wdog"),
        )


class UnableToGetSbdStatus(NameBuildTest):
    def test_no_reason(self):
        self.assert_message_from_report(
            "Unable to get status of SBD from node 'node1'",
            reports.UnableToGetSbdStatus("node1", ""),
        )

    def test_all(self):
        self.assert_message_from_report(
            "Unable to get status of SBD from node 'node2': reason",
            reports.UnableToGetSbdStatus("node2", "reason"),
        )


class ClusterRestartRequiredToApplyChanges(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Cluster restart is required in order to apply these changes.",
            reports.ClusterRestartRequiredToApplyChanges(),
        )


class CibAlertRecipientAlreadyExists(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Recipient 'recipient' in alert 'alert-id' already exists",
            reports.CibAlertRecipientAlreadyExists("alert-id", "recipient"),
        )


class CibAlertRecipientValueInvalid(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Recipient value 'recipient' is not valid.",
            reports.CibAlertRecipientValueInvalid("recipient"),
        )


class CibUpgradeSuccessful(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "CIB has been upgraded to the latest schema version.",
            reports.CibUpgradeSuccessful(),
        )


class CibUpgradeFailed(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Upgrading of CIB to the latest schema failed: reason",
            reports.CibUpgradeFailed("reason"),
        )


class CibUpgradeFailedToMinimalRequiredVersion(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Unable to upgrade CIB to required schema version"
                " 1.1 or higher. Current version is"
                " 0.8. Newer version of pacemaker is needed."
            ),
            reports.CibUpgradeFailedToMinimalRequiredVersion("0.8", "1.1"),
        )


class FileAlreadyExists(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Corosync authkey file '/corosync_conf/path' already exists",
            reports.FileAlreadyExists(
                "COROSYNC_AUTHKEY", "/corosync_conf/path"
            ),
        )

    def test_with_node(self):
        self.assert_message_from_report(
            "node1: pcs configuration file '/pcs/conf/file' already exists",
            reports.FileAlreadyExists(
                "PCS_SETTINGS_CONF", "/pcs/conf/file", node="node1"
            ),
        )


class FileIoError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "Unable to read Booth configuration: ",
            reports.FileIoError(
                file_type_codes.BOOTH_CONFIG, RawFileError.ACTION_READ, ""
            ),
        )

    def test_all(self):
        self.assert_message_from_report(
            "Unable to read pcsd SSL certificate '/ssl/cert/path': Failed",
            reports.FileIoError(
                file_type_codes.PCSD_SSL_CERT,
                RawFileError.ACTION_READ,
                "Failed",
                file_path="/ssl/cert/path",
            ),
        )

    def test_role_translation_a(self):
        self.assert_message_from_report(
            "Unable to write pcsd SSL key '/ssl/key/path': Failed",
            reports.FileIoError(
                file_type_codes.PCSD_SSL_KEY,
                RawFileError.ACTION_WRITE,
                "Failed",
                file_path="/ssl/key/path",
            ),
        )

    def test_role_translation_b(self):
        self.assert_message_from_report(
            (
                "Unable to change ownership of pcsd configuration "
                "'/pcsd/conf/path': Failed"
            ),
            reports.FileIoError(
                file_type_codes.PCSD_ENVIRONMENT_CONFIG,
                RawFileError.ACTION_CHOWN,
                "Failed",
                file_path="/pcsd/conf/path",
            ),
        )

    def test_role_translation_c(self):
        self.assert_message_from_report(
            "Unable to change permissions of Corosync authkey: Failed",
            reports.FileIoError(
                file_type_codes.COROSYNC_AUTHKEY,
                RawFileError.ACTION_CHMOD,
                "Failed",
            ),
        )

    def test_role_translation_d(self):
        self.assert_message_from_report(
            (
                "Unable to change ownership of pcs configuration: "
                "Permission denied"
            ),
            reports.FileIoError(
                file_type_codes.PCS_SETTINGS_CONF,
                RawFileError.ACTION_CHOWN,
                "Permission denied",
            ),
        )


class UnsupportedOperationOnNonSystemdSystems(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "unsupported operation on non systemd systems",
            reports.UnsupportedOperationOnNonSystemdSystems(),
        )


class LiveEnvironmentRequired(NameBuildTest):
    def test_build_messages_transformable_codes(self):
        self.assert_message_from_report(
            "This command does not support '{}', '{}'".format(
                str(file_type_codes.CIB),
                str(file_type_codes.COROSYNC_CONF),
            ),
            reports.LiveEnvironmentRequired(
                [file_type_codes.COROSYNC_CONF, file_type_codes.CIB]
            ),
        )


class LiveEnvironmentRequiredForLocalNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Node(s) must be specified if mocked CIB is used",
            reports.LiveEnvironmentRequiredForLocalNode(),
        )


class LiveEnvironmentNotConsistent(NameBuildTest):
    def test_one_one(self):
        self.assert_message_from_report(
            "When '{}' is specified, '{}' must be specified as well".format(
                str(file_type_codes.BOOTH_CONFIG),
                str(file_type_codes.BOOTH_KEY),
            ),
            reports.LiveEnvironmentNotConsistent(
                [file_type_codes.BOOTH_CONFIG],
                [file_type_codes.BOOTH_KEY],
            ),
        )

    def test_many_many(self):
        self.assert_message_from_report(
            (
                "When '{}', '{}' are specified, '{}', '{}' must be specified "
                "as well"
            ).format(
                str(file_type_codes.BOOTH_CONFIG),
                str(file_type_codes.CIB),
                str(file_type_codes.BOOTH_KEY),
                str(file_type_codes.COROSYNC_CONF),
            ),
            reports.LiveEnvironmentNotConsistent(
                [file_type_codes.CIB, file_type_codes.BOOTH_CONFIG],
                [file_type_codes.COROSYNC_CONF, file_type_codes.BOOTH_KEY],
            ),
        )


class CorosyncNodeConflictCheckSkipped(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster",
            reports.CorosyncNodeConflictCheckSkipped(const.REASON_NOT_LIVE_CIB),
        )


class CorosyncQuorumAtbCannotBeDisabledDueToSbd(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Unable to disable auto_tie_breaker, SBD fencing would have no "
                "effect"
            ),
            reports.CorosyncQuorumAtbCannotBeDisabledDueToSbd(),
        )


class CorosyncQuorumAtbWillBeEnabledDueToSbd(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "SBD fencing is enabled in the cluster. To keep it effective, "
                "auto_tie_breaker quorum option will be enabled."
            ),
            reports.CorosyncQuorumAtbWillBeEnabledDueToSbd(),
        )


class CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "SBD fencing is enabled in the cluster. To keep it effective, "
                "auto_tie_breaker quorum option needs to be enabled. This can "
                "only be done when the cluster is stopped. To proceed, stop the "
                "cluster, enable auto_tie_breaker, and start the cluster. Then, "
                "repeat the requested action."
            ),
            reports.CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning(),
        )


class CibAclRoleIsAlreadyAssignedToTarget(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Role 'role_id' is already assigned to 'target_id'",
            reports.CibAclRoleIsAlreadyAssignedToTarget("role_id", "target_id"),
        )


class CibAclRoleIsNotAssignedToTarget(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Role 'role_id' is not assigned to 'target_id'",
            reports.CibAclRoleIsNotAssignedToTarget("role_id", "target_id"),
        )


class CibAclTargetAlreadyExists(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "'target_id' already exists",
            reports.CibAclTargetAlreadyExists("target_id"),
        )


class CibFencingLevelAlreadyExists(NameBuildTest):
    def test_target_node(self):
        self.assert_message_from_report(
            "Fencing level for 'nodeA' at level '1' with device(s) "
            "'device1', 'device2' already exists",
            reports.CibFencingLevelAlreadyExists(
                "1", TARGET_TYPE_NODE, "nodeA", ["device2", "device1"]
            ),
        )

    def test_target_pattern(self):
        self.assert_message_from_report(
            "Fencing level for 'node-\\d+' at level '1' with device(s) "
            "'device1', 'device2' already exists",
            reports.CibFencingLevelAlreadyExists(
                "1", TARGET_TYPE_REGEXP, "node-\\d+", ["device1", "device2"]
            ),
        )

    def test_target_attribute(self):
        self.assert_message_from_report(
            "Fencing level for 'name=value' at level '1' with device(s) "
            "'device2' already exists",
            reports.CibFencingLevelAlreadyExists(
                "1", TARGET_TYPE_ATTRIBUTE, ("name", "value"), ["device2"]
            ),
        )


class CibFencingLevelDoesNotExist(NameBuildTest):
    def test_full_info(self):
        self.assert_message_from_report(
            "Fencing level for 'nodeA' at level '1' with device(s) "
            "'device1', 'device2' does not exist",
            reports.CibFencingLevelDoesNotExist(
                "1", TARGET_TYPE_NODE, "nodeA", ["device2", "device1"]
            ),
        )

    def test_only_level(self):
        self.assert_message_from_report(
            "Fencing level at level '1' does not exist",
            reports.CibFencingLevelDoesNotExist("1"),
        )

    def test_only_target(self):
        self.assert_message_from_report(
            "Fencing level for 'name=value' does not exist",
            reports.CibFencingLevelDoesNotExist(
                target_type=TARGET_TYPE_ATTRIBUTE,
                target_value=("name", "value"),
            ),
        )

    def test_only_devices(self):
        self.assert_message_from_report(
            "Fencing level with device(s) 'device1' does not exist",
            reports.CibFencingLevelDoesNotExist(devices=["device1"]),
        )

    def test_no_info(self):
        self.assert_message_from_report(
            "Fencing level does not exist",
            reports.CibFencingLevelDoesNotExist(),
        )


class CibRemoveResources(NameBuildTest):
    def test_single_id(self):
        self.assert_message_from_report(
            "Removing resource: 'id1'", reports.CibRemoveResources(["id1"])
        )

    def test_multiple_ids(self):
        self.assert_message_from_report(
            "Removing resources: 'id1', 'id2', 'id3'",
            reports.CibRemoveResources(["id1", "id2", "id3"]),
        )


class CibRemoveDependantElements(NameBuildTest):
    def test_single_element_type_with_single_id(self):
        self.assert_message_from_report(
            "Removing dependant element:\n  Location constraint: 'id1'",
            reports.CibRemoveDependantElements({"id1": "rsc_location"}),
        )

    def test_single_element_type_with_multiple_ids(self):
        self.assert_message_from_report(
            (
                "Removing dependant elements:\n"
                "  Location constraints: 'id1', 'id2'"
            ),
            reports.CibRemoveDependantElements(
                {"id1": "rsc_location", "id2": "rsc_location"}
            ),
        )

    def test_multiple_element_types_with_single_id(self):
        self.assert_message_from_report(
            (
                "Removing dependant elements:\n"
                "  Clone: 'id2'\n"
                "  Location constraint: 'id1'"
            ),
            reports.CibRemoveDependantElements(
                {"id1": "rsc_location", "id2": "clone"}
            ),
        )

    def test_multiple_element_types_with_multiple_ids(self):
        self.assert_message_from_report(
            (
                "Removing dependant elements:\n"
                "  Another_elements: 'id5', 'id6'\n"
                "  Clones: 'id3', 'id4'\n"
                "  Location constraints: 'id1', 'id2'"
            ),
            reports.CibRemoveDependantElements(
                {
                    "id1": "rsc_location",
                    "id2": "rsc_location",
                    "id3": "clone",
                    "id4": "clone",
                    "id5": "another_element",
                    "id6": "another_element",
                }
            ),
        )


class CibRemoveReferences(NameBuildTest):
    def test_one_element_single_reference(self):
        self.assert_message_from_report(
            ("Removing references:\n  Resource 'id1' from:\n    Tag: 'id2'"),
            reports.CibRemoveReferences(
                {"id1": "primitive", "id2": "tag"}, {"id1": ["id2"]}
            ),
        )

    def test_missing_tag_mapping(self):
        self.assert_message_from_report(
            ("Removing references:\n  Element 'id1' from:\n    Element: 'id2'"),
            reports.CibRemoveReferences({}, {"id1": ["id2"]}),
        )

    def test_one_element_multiple_references_same_type(self):
        self.assert_message_from_report(
            (
                "Removing references:\n"
                "  Resource 'id1' from:\n"
                "    Tags: 'id2', 'id3'"
            ),
            reports.CibRemoveReferences(
                {"id1": "primitive", "id2": "tag", "id3": "tag"},
                {"id1": ["id2", "id3"]},
            ),
        )

    def test_one_element_multiple_references_multiple_types(self):
        self.assert_message_from_report(
            (
                "Removing references:\n"
                "  Resource 'id1' from:\n"
                "    Group: 'id3'\n"
                "    Tag: 'id2'"
            ),
            reports.CibRemoveReferences(
                {"id1": "primitive", "id2": "tag", "id3": "group"},
                {"id1": ["id2", "id3"]},
            ),
        )

    def test_multiple_elements_single_reference(self):
        self.assert_message_from_report(
            (
                "Removing references:\n"
                "  Resource 'id1' from:\n"
                "    Tag: 'id2'\n"
                "  Resource 'id3' from:\n"
                "    Tag: 'id4'"
            ),
            reports.CibRemoveReferences(
                {
                    "id1": "primitive",
                    "id2": "tag",
                    "id3": "primitive",
                    "id4": "tag",
                },
                {"id1": ["id2"], "id3": ["id4"]},
            ),
        )


class UseCommandNodeAddRemote(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "this command is not sufficient for creating a remote connection",
            reports.UseCommandNodeAddRemote(),
        )


class UseCommandNodeAddGuest(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "this command is not sufficient for creating a guest node",
            reports.UseCommandNodeAddGuest(),
        )


class UseCommandNodeRemoveRemote(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "this command is not sufficient for removing a remote node",
            reports.UseCommandNodeRemoveRemote(),
        )


class UseCommandNodeRemoveGuest(NameBuildTest):
    def test_build_messages(self):
        self.assert_message_from_report(
            "this command is not sufficient for removing a guest node",
            reports.UseCommandNodeRemoveGuest(),
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
            reports.TmpFileWrite("/tmp/pcs/test.tmp", "test file\ncontent\n"),
        )


class NodeAddressesUnresolvable(NameBuildTest):
    def test_one_address(self):
        self.assert_message_from_report(
            "Unable to resolve addresses: 'node1'",
            reports.NodeAddressesUnresolvable(["node1"]),
        )

    def test_more_address(self):
        self.assert_message_from_report(
            "Unable to resolve addresses: 'node1', 'node2', 'node3'",
            reports.NodeAddressesUnresolvable(["node2", "node1", "node3"]),
        )


class UnableToPerformOperationOnAnyNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Unable to perform operation on any available node/host, "
                "therefore it is not possible to continue"
            ),
            reports.UnableToPerformOperationOnAnyNode(),
        )


class HostNotFound(NameBuildTest):
    def test_single_host(self):
        self.assert_message_from_report(
            "Host 'unknown_host' is not known to pcs",
            reports.HostNotFound(["unknown_host"]),
        )

    def test_multiple_hosts(self):
        self.assert_message_from_report(
            "Hosts 'another_one', 'unknown_host' are not known to pcs",
            reports.HostNotFound(["unknown_host", "another_one"]),
        )


class NoneHostFound(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "None of hosts is known to pcs.", reports.NoneHostFound()
        )


class HostAlreadyAuthorized(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "host: Already authorized", reports.HostAlreadyAuthorized("host")
        )


class ClusterDestroyStarted(NameBuildTest):
    def test_multiple_hosts(self):
        self.assert_message_from_report(
            "Destroying cluster on hosts: 'node1', 'node2', 'node3'...",
            reports.ClusterDestroyStarted(["node1", "node3", "node2"]),
        )

    def test_single_host(self):
        self.assert_message_from_report(
            "Destroying cluster on hosts: 'node1'...",
            reports.ClusterDestroyStarted(["node1"]),
        )


class ClusterDestroySuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "node1: Successfully destroyed cluster",
            reports.ClusterDestroySuccess("node1"),
        )


class ClusterEnableStarted(NameBuildTest):
    def test_multiple_hosts(self):
        self.assert_message_from_report(
            "Enabling cluster on hosts: 'node1', 'node2', 'node3'...",
            reports.ClusterEnableStarted(["node1", "node3", "node2"]),
        )

    def test_single_host(self):
        self.assert_message_from_report(
            "Enabling cluster on hosts: 'node1'...",
            reports.ClusterEnableStarted(["node1"]),
        )


class ClusterEnableSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "node1: Cluster enabled", reports.ClusterEnableSuccess("node1")
        )


class ClusterStartStarted(NameBuildTest):
    def test_multiple_hosts(self):
        self.assert_message_from_report(
            "Starting cluster on hosts: 'node1', 'node2', 'node3'...",
            reports.ClusterStartStarted(["node1", "node3", "node2"]),
        )

    def test_single_host(self):
        self.assert_message_from_report(
            "Starting cluster on hosts: 'node1'...",
            reports.ClusterStartStarted(["node1"]),
        )


class ClusterStartSuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "node1: Cluster started", reports.ClusterStartSuccess("node1")
        )


class ServiceNotInstalled(NameBuildTest):
    def test_multiple_services(self):
        self.assert_message_from_report(
            "node1: Required cluster services not installed: 'service1', "
            "'service2', 'service3'",
            reports.ServiceNotInstalled(
                "node1", ["service1", "service3", "service2"]
            ),
        )

    def test_single_service(self):
        self.assert_message_from_report(
            "node1: Required cluster services not installed: 'service'",
            reports.ServiceNotInstalled("node1", ["service"]),
        )


class HostAlreadyInClusterConfig(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "host: The host seems to be in a cluster already as cluster "
            "configuration files have been found on the host",
            reports.HostAlreadyInClusterConfig("host"),
        )


class HostAlreadyInClusterServices(NameBuildTest):
    def test_multiple_services(self):
        self.assert_message_from_report(
            "node1: The host seems to be in a cluster already as the following "
            "services are found to be running: 'service1', 'service2', "
            "'service3'. If the host is not part of a cluster, stop the "
            "services and retry",
            reports.HostAlreadyInClusterServices(
                "node1", ["service1", "service3", "service2"]
            ),
        )

    def test_single_service(self):
        self.assert_message_from_report(
            "node1: The host seems to be in a cluster already as the following "
            "service is found to be running: 'service'. If the host is not "
            "part of a cluster, stop the service and retry",
            reports.HostAlreadyInClusterServices("node1", ["service"]),
        )


class ServiceVersionMismatch(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Hosts do not have the same version of 'service'; "
            "hosts 'host4', 'host5', 'host6' have version 2.0; "
            "hosts 'host1', 'host3' have version 1.0; "
            "host 'host2' has version 1.2",
            reports.ServiceVersionMismatch(
                "service",
                {
                    "host1": "1.0",
                    "host2": "1.2",
                    "host3": "1.0",
                    "host4": "2.0",
                    "host5": "2.0",
                    "host6": "2.0",
                },
            ),
        )


class WaitForNodeStartupStarted(NameBuildTest):
    def test_single_node(self):
        self.assert_message_from_report(
            "Waiting for node(s) to start: 'node1'...",
            reports.WaitForNodeStartupStarted(["node1"]),
        )

    def test_multiple_nodes(self):
        self.assert_message_from_report(
            "Waiting for node(s) to start: 'node1', 'node2', 'node3'...",
            reports.WaitForNodeStartupStarted(["node3", "node2", "node1"]),
        )


class WaitForNodeStartupTimedOut(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Node(s) startup timed out", reports.WaitForNodeStartupTimedOut()
        )


class WaitForNodeStartupError(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to verify all nodes have started",
            reports.WaitForNodeStartupError(),
        )


class WaitForNodeStartupWithoutStart(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Cannot specify 'wait' without specifying 'start'",
            reports.WaitForNodeStartupWithoutStart(),
        )


class PcsdVersionTooOld(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "node1: Old version of pcsd is running on the node, therefore "
                "it is unable to perform the action"
            ),
            reports.PcsdVersionTooOld("node1"),
        )


class PcsdSslCertAndKeyDistributionStarted(NameBuildTest):
    def test_multiple_nodes(self):
        self.assert_message_from_report(
            "Synchronizing pcsd SSL certificates on node(s) 'node1', 'node2', "
            "'node3'...",
            reports.PcsdSslCertAndKeyDistributionStarted(
                ["node1", "node3", "node2"]
            ),
        )

    def test_single_node(self):
        self.assert_message_from_report(
            "Synchronizing pcsd SSL certificates on node(s) 'node3'...",
            reports.PcsdSslCertAndKeyDistributionStarted(["node3"]),
        )


class PcsdSslCertAndKeySetSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "node1: Success", reports.PcsdSslCertAndKeySetSuccess("node1")
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
            reports.ClusterWillBeDestroyed(),
        )


class ClusterSetupSuccess(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Cluster has been successfully set up.",
            reports.ClusterSetupSuccess(),
        )


class UsingDefaultAddressForHost(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "No addresses specified for host 'node-name', using 'node-addr'",
            reports.UsingDefaultAddressForHost(
                "node-name",
                "node-addr",
                const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS,
            ),
        )


class ResourceInBundleNotAccessible(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Resource 'resourceA' will not be accessible by the cluster "
                "inside bundle 'bundleA', at least one of bundle options "
                "'control-port' or 'ip-range-start' has to be specified"
            ),
            reports.ResourceInBundleNotAccessible("bundleA", "resourceA"),
        )


class UsingDefaultWatchdog(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "No watchdog has been specified for node 'node1'. Using "
                "default watchdog '/dev/watchdog'"
            ),
            reports.UsingDefaultWatchdog("/dev/watchdog", "node1"),
        )


class CannotRemoveAllClusterNodes(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "No nodes would be left in the cluster",
            reports.CannotRemoveAllClusterNodes(),
        )


class UnableToConnectToAnyRemainingNode(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Unable to connect to any remaining cluster node",
            reports.UnableToConnectToAnyRemainingNode(),
        )


class UnableToConnectToAllRemainingNodes(NameBuildTest):
    def test_single_node(self):
        self.assert_message_from_report(
            ("Remaining cluster node 'node1' could not be reached"),
            reports.UnableToConnectToAllRemainingNodes(["node1"]),
        )

    def test_multiple_nodes(self):
        self.assert_message_from_report(
            (
                "Remaining cluster nodes 'node0', 'node1', 'node2' could not "
                "be reached"
            ),
            reports.UnableToConnectToAllRemainingNodes(
                ["node1", "node0", "node2"]
            ),
        )


class NodesToRemoveUnreachable(NameBuildTest):
    def test_single_node(self):
        self.assert_message_from_report(
            (
                "Removed node 'node0' could not be reached and subsequently "
                "deconfigured"
            ),
            reports.NodesToRemoveUnreachable(["node0"]),
        )

    def test_multiple_nodes(self):
        self.assert_message_from_report(
            (
                "Removed nodes 'node0', 'node1', 'node2' could not be reached "
                "and subsequently deconfigured"
            ),
            reports.NodesToRemoveUnreachable(["node1", "node0", "node2"]),
        )


class NodeUsedAsTieBreaker(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Node 'node2' with id '2' is used as a tie breaker for a "
                "qdevice and therefore cannot be removed"
            ),
            reports.NodeUsedAsTieBreaker("node2", 2),
        )


class CorosyncQuorumWillBeLost(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "This action will cause a loss of the quorum",
            reports.CorosyncQuorumWillBeLost(),
        )


class CorosyncQuorumLossUnableToCheck(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Unable to determine whether this action will cause "
                "a loss of the quorum"
            ),
            reports.CorosyncQuorumLossUnableToCheck(),
        )


class SbdListWatchdogError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to query available watchdogs from sbd: this is a reason",
            reports.SbdListWatchdogError("this is a reason"),
        )


class SbdWatchdogNotSupported(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "node1: Watchdog '/dev/watchdog' is not supported (it may be a "
                "software watchdog)"
            ),
            reports.SbdWatchdogNotSupported("node1", "/dev/watchdog"),
        )


class SbdWatchdogValidationInactive(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Not validating the watchdog",
            reports.SbdWatchdogValidationInactive(),
        )


class SbdWatchdogTestError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to initialize test of the watchdog: some reason",
            reports.SbdWatchdogTestError("some reason"),
        )


class SbdWatchdogTestMultipleDevices(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Multiple watchdog devices available, therefore, watchdog "
                "which should be tested has to be specified."
            ),
            reports.SbdWatchdogTestMultipleDevices(),
        )


class SbdWatchdogTestFailed(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "System should have been reset already",
            reports.SbdWatchdogTestFailed(),
        )


class SystemWillReset(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "System will reset shortly", reports.SystemWillReset()
        )


class ResourceBundleUnsupportedContainerType(NameBuildTest):
    def test_single_type(self):
        self.assert_message_from_report(
            (
                "Bundle 'bundle id' uses unsupported container type, therefore "
                "it is not possible to set its container options. Supported "
                "container types are: 'b'"
            ),
            reports.ResourceBundleUnsupportedContainerType("bundle id", ["b"]),
        )

    def test_multiple_types(self):
        self.assert_message_from_report(
            (
                "Bundle 'bundle id' uses unsupported container type, therefore "
                "it is not possible to set its container options. Supported "
                "container types are: 'a', 'b', 'c'"
            ),
            reports.ResourceBundleUnsupportedContainerType(
                "bundle id", ["b", "a", "c"]
            ),
        )

    def test_no_update(self):
        self.assert_message_from_report(
            (
                "Bundle 'bundle id' uses unsupported container type. Supported "
                "container types are: 'a', 'b', 'c'"
            ),
            reports.ResourceBundleUnsupportedContainerType(
                "bundle id", ["b", "a", "c"], updating_options=False
            ),
        )


class FenceHistoryCommandError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to show fence history: reason",
            reports.FenceHistoryCommandError(
                "reason", reports.const.FENCE_HISTORY_COMMAND_SHOW
            ),
        )


class FenceHistoryNotSupported(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Fence history is not supported, please upgrade pacemaker",
            reports.FenceHistoryNotSupported(),
        )


class ResourceInstanceAttrValueNotUnique(NameBuildTest):
    def test_one_resource(self):
        self.assert_message_from_report(
            (
                "Value 'val' of option 'attr' is not unique across 'agent' "
                "resources. Following resources are configured with the same "
                "value of the instance attribute: 'A'"
            ),
            reports.ResourceInstanceAttrValueNotUnique(
                "attr", "val", "agent", ["A"]
            ),
        )

    def test_multiple_resources(self):
        self.assert_message_from_report(
            (
                "Value 'val' of option 'attr' is not unique across 'agent' "
                "resources. Following resources are configured with the same "
                "value of the instance attribute: 'A', 'B', 'C'"
            ),
            reports.ResourceInstanceAttrValueNotUnique(
                "attr", "val", "agent", ["B", "C", "A"]
            ),
        )


class ResourceInstanceAttrGroupValueNotUnique(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "Value '127.0.0.1', '12345' of options 'ip', 'port' (group "
                "'address') is not unique across 'agent' resources. Following "
                "resources are configured with the same values of the instance "
                "attributes: 'A', 'B'"
            ),
            reports.ResourceInstanceAttrGroupValueNotUnique(
                "address",
                {
                    "port": "12345",
                    "ip": "127.0.0.1",
                },
                "agent",
                ["B", "A"],
            ),
        )


class CannotLeaveGroupEmptyAfterMove(NameBuildTest):
    def test_single_resource(self):
        self.assert_message_from_report(
            "Unable to move resource 'R' as it would leave group 'gr1' empty.",
            reports.CannotLeaveGroupEmptyAfterMove("gr1", ["R"]),
        )

    def test_multiple_resources(self):
        self.assert_message_from_report(
            "Unable to move resources 'R1', 'R2', 'R3' as it would leave "
            "group 'gr1' empty.",
            reports.CannotLeaveGroupEmptyAfterMove("gr1", ["R3", "R1", "R2"]),
        )


class CannotMoveResourceBundleInner(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Resources cannot be moved out of their bundles. If you want "
                "to move a bundle, use the bundle id (B)"
            ),
            reports.CannotMoveResourceBundleInner("R", "B"),
        )


class CannotMoveResourceCloneInner(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "to move clone resources you must use the clone id (C)",
            reports.CannotMoveResourceCloneInner("R", "C"),
        )


class CannotMoveResourceMultipleInstances(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "more than one instance of resource 'R' is running, "
                "thus the resource cannot be moved"
            ),
            reports.CannotMoveResourceMultipleInstances("R"),
        )


class CannotMoveResourceMultipleInstancesNoNodeSpecified(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "more than one instance of resource 'R' is running, "
                "thus the resource cannot be moved, "
                "unless a destination node is specified"
            ),
            reports.CannotMoveResourceMultipleInstancesNoNodeSpecified("R"),
        )


class CannotMoveResourcePromotableInner(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "to move promotable clone resources you must use "
                "the promotable clone id (P)"
            ),
            reports.CannotMoveResourcePromotableInner("R", "P"),
        )


class CannotMoveResourceMasterResourceNotPromotable(NameBuildTest):
    def test_without_promotable(self):
        self.assert_message_from_report(
            "when specifying promoted you must use the promotable clone id",
            reports.CannotMoveResourceMasterResourceNotPromotable("R"),
        )

    def test_with_promotable(self):
        self.assert_message_from_report(
            "when specifying promoted you must use the promotable clone id (P)",
            reports.CannotMoveResourceMasterResourceNotPromotable(
                "R", promotable_id="P"
            ),
        )


class CannotMoveResourceNotRunning(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "It is not possible to move resource 'R' as it is not running "
                "at the moment"
            ),
            reports.CannotMoveResourceNotRunning("R"),
        )


class CannotMoveResourceStoppedNoNodeSpecified(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "You must specify a node when moving/banning a stopped resource",
            reports.CannotMoveResourceStoppedNoNodeSpecified("R"),
        )


class ResourceMovePcmkError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "cannot move resource 'R'\nstdout1\n  stdout2\nstderr1\n  stderr2",
            reports.ResourceMovePcmkError(
                "R", "stdout1\n\n  stdout2\n", "stderr1\n\n  stderr2\n"
            ),
        )


class ResourceMovePcmkSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "stdout1\n  stdout2\nstderr1\n  stderr2",
            reports.ResourceMovePcmkSuccess(
                "R", "stdout1\n\n  stdout2\n", "stderr1\n\n  stderr2\n"
            ),
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
            reports.ResourceMovePcmkSuccess(
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
                ),
            ),
        )


class CannotBanResourceBundleInner(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Resource 'R' is in a bundle and cannot be banned. If you want "
                "to ban the bundle, use the bundle id (B)"
            ),
            reports.CannotBanResourceBundleInner("R", "B"),
        )


class CannotBanResourceMasterResourceNotPromotable(NameBuildTest):
    def test_without_promotable(self):
        self.assert_message_from_report(
            "when specifying promoted you must use the promotable clone id",
            reports.CannotBanResourceMasterResourceNotPromotable("R"),
        )

    def test_with_promotable(self):
        self.assert_message_from_report(
            "when specifying promoted you must use the promotable clone id (P)",
            reports.CannotBanResourceMasterResourceNotPromotable(
                "R", promotable_id="P"
            ),
        )


class CannotBanResourceMultipleInstancesNoNodeSpecified(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "more than one instance of resource 'R' is running, "
                "thus the resource cannot be banned, "
                "unless a destination node is specified"
            ),
            reports.CannotBanResourceMultipleInstancesNoNodeSpecified("R"),
        )


class CannotBanResourceStoppedNoNodeSpecified(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "You must specify a node when moving/banning a stopped resource",
            reports.CannotBanResourceStoppedNoNodeSpecified("R"),
        )


class ResourceBanPcmkError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "cannot ban resource 'R'\nstdout1\n  stdout2\nstderr1\n  stderr2",
            reports.ResourceBanPcmkError(
                "R", "stdout1\n\n  stdout2\n", "stderr1\n\n  stderr2\n"
            ),
        )


class ResourceBanPcmkSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "stdout1\n  stdout2\nstderr1\n  stderr2",
            reports.ResourceBanPcmkSuccess(
                "R", "stdout1\n\n  stdout2\n", "stderr1\n\n  stderr2\n"
            ),
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
            reports.ResourceBanPcmkSuccess(
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
                ),
            ),
        )


class CannotUnmoveUnbanResourceMasterResourceNotPromotable(NameBuildTest):
    def test_without_promotable(self):
        self.assert_message_from_report(
            "when specifying promoted you must use the promotable clone id",
            reports.CannotUnmoveUnbanResourceMasterResourceNotPromotable("R"),
        )

    def test_with_promotable(self):
        self.assert_message_from_report(
            "when specifying promoted you must use the promotable clone id (P)",
            reports.CannotUnmoveUnbanResourceMasterResourceNotPromotable(
                "R", promotable_id="P"
            ),
        )


class ResourceUnmoveUnbanPcmkExpiredNotSupported(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "expired is not supported, please upgrade pacemaker",
            reports.ResourceUnmoveUnbanPcmkExpiredNotSupported(),
        )


class ResourceUnmoveUnbanPcmkError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "cannot clear resource 'R'\nstdout1\n  stdout2\nstderr1\n  stderr2",
            reports.ResourceUnmoveUnbanPcmkError(
                "R", "stdout1\n\n  stdout2\n", "stderr1\n\n  stderr2\n"
            ),
        )


class ResourceUnmoveUnbanPcmkSuccess(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "stdout1\n  stdout2\nstderr1\n  stderr2",
            reports.ResourceUnmoveUnbanPcmkSuccess(
                "R", "stdout1\n\n  stdout2\n", "stderr1\n\n  stderr2\n"
            ),
        )


class ResourceMoveConstraintCreated(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Location constraint to move resource 'R1' has been created",
            reports.ResourceMoveConstraintCreated("R1"),
        )


class ResourceMoveConstraintRemoved(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Location constraint created to move resource 'R1' has "
                "been removed"
            ),
            reports.ResourceMoveConstraintRemoved("R1"),
        )


class ResourceMoveNotAffectingResource(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Unable to move resource 'R1' using a location constraint. "
                "Current location of the resource may be affected by some "
                "other constraint."
            ),
            reports.ResourceMoveNotAffectingResource("R1"),
        )


class ResourceMoveAffectsOtherResources(NameBuildTest):
    def test_multiple(self):
        self.assert_message_from_report(
            "Moving resource 'R1' affects resources: 'p0', 'p1', 'p2'",
            reports.ResourceMoveAffectsOtherResources("R1", ["p2", "p0", "p1"]),
        )

    def test_single(self):
        self.assert_message_from_report(
            "Moving resource 'R1' affects resource: 'R2'",
            reports.ResourceMoveAffectsOtherResources("R1", ["R2"]),
        )


class ResourceMoveAutocleanSimulationFailure(NameBuildTest):
    def test_simulation(self):
        self.assert_message_from_report(
            (
                "Unable to ensure that moved resource 'R1' will stay on the "
                "same node after a constraint used for moving it is removed."
            ),
            reports.ResourceMoveAutocleanSimulationFailure(
                "R1", others_affected=False
            ),
        )

    def test_simulation_others_affected(self):
        self.assert_message_from_report(
            (
                "Unable to ensure that moved resource 'R1' or other resources "
                "will stay on the same node after a constraint used for moving "
                "it is removed."
            ),
            reports.ResourceMoveAutocleanSimulationFailure(
                "R1", others_affected=True
            ),
        )

    def test_live(self):
        self.assert_message_from_report(
            (
                "Unable to ensure that moved resource 'R1' will stay on the "
                "same node after a constraint used for moving it is removed."
                " The constraint to move the resource has not been removed "
                "from configuration. Consider removing it manually. Be aware "
                "that removing the constraint may cause resources to move to "
                "other nodes."
            ),
            reports.ResourceMoveAutocleanSimulationFailure(
                "R1", others_affected=False, move_constraint_left_in_cib=True
            ),
        )

    def test_live_others_affected(self):
        self.assert_message_from_report(
            (
                "Unable to ensure that moved resource 'R1' or other resources "
                "will stay on the same node after a constraint used for moving "
                "it is removed."
                " The constraint to move the resource has not been removed "
                "from configuration. Consider removing it manually. Be aware "
                "that removing the constraint may cause resources to move to "
                "other nodes."
            ),
            reports.ResourceMoveAutocleanSimulationFailure(
                "R1", others_affected=True, move_constraint_left_in_cib=True
            ),
        )


class ResourceMayOrMayNotMove(NameBuildTest):
    def test_build_message(self):
        self.assert_message_from_report(
            (
                "A move constraint has been created and the resource 'id' may "
                "or may not move depending on other configuration"
            ),
            reports.ResourceMayOrMayNotMove("id"),
        )


class ParseErrorJsonFile(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to parse known-hosts file '/tmp/known-hosts': "
            "some reason: line 15 column 5 (char 100)",
            reports.ParseErrorJsonFile(
                file_type_codes.PCS_KNOWN_HOSTS,
                15,
                5,
                100,
                "some reason",
                "some reason: line 15 column 5 (char 100)",
                file_path="/tmp/known-hosts",
            ),
        )


class ResourceDisableAffectsOtherResources(NameBuildTest):
    def test_multiple_disabled(self):
        self.assert_message_from_report(
            (
                "Disabling specified resource would have an effect on these "
                "resources: 'O1', 'O2'"
            ),
            reports.ResourceDisableAffectsOtherResources(
                ["D1"],
                ["O2", "O1"],
            ),
        )

    def test_multiple_affected(self):
        self.assert_message_from_report(
            (
                "Disabling specified resources would have an effect on this "
                "resource: 'O1'"
            ),
            reports.ResourceDisableAffectsOtherResources(
                ["D2", "D1"],
                ["O1"],
            ),
        )


class DrConfigAlreadyExist(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Disaster-recovery already configured",
            reports.DrConfigAlreadyExist(),
        )


class DrConfigDoesNotExist(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Disaster-recovery is not configured",
            reports.DrConfigDoesNotExist(),
        )


class NodeInLocalCluster(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Node 'node-name' is part of local cluster",
            reports.NodeInLocalCluster("node-name"),
        )


class BoothLackOfSites(NameBuildTest):
    def test_no_site(self):
        self.assert_message_from_report(
            (
                "lack of sites for booth configuration (need 2 at least): "
                "sites missing"
            ),
            reports.BoothLackOfSites([]),
        )

    def test_single_site(self):
        self.assert_message_from_report(
            (
                "lack of sites for booth configuration (need 2 at least): "
                "sites 'site1'"
            ),
            reports.BoothLackOfSites(["site1"]),
        )

    def test_multiple_sites(self):
        self.assert_message_from_report(
            (
                "lack of sites for booth configuration (need 2 at least): "
                "sites 'site1', 'site2'"
            ),
            reports.BoothLackOfSites(["site1", "site2"]),
        )


class BoothEvenPeersNumber(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "odd number of peers is required (entered 4 peers)",
            reports.BoothEvenPeersNumber(4),
        )


class BoothAddressDuplication(NameBuildTest):
    def test_single_address(self):
        self.assert_message_from_report(
            "duplicate address for booth configuration: 'addr1'",
            reports.BoothAddressDuplication(["addr1"]),
        )

    def test_multiple_addresses(self):
        self.assert_message_from_report(
            (
                "duplicate address for booth configuration: 'addr1', 'addr2', "
                "'addr3'"
            ),
            reports.BoothAddressDuplication(
                sorted(["addr2", "addr1", "addr3"])
            ),
        )


class BoothConfigUnexpectedLines(NameBuildTest):
    def test_single_line(self):
        self.assert_message_from_report(
            "unexpected line in booth config:\nline",
            reports.BoothConfigUnexpectedLines(["line"]),
        )

    def test_multiple_lines(self):
        self.assert_message_from_report(
            "unexpected lines in booth config:\nline\nline2",
            reports.BoothConfigUnexpectedLines(["line", "line2"]),
        )

    def test_file_path(self):
        self.assert_message_from_report(
            "unexpected line in booth config 'PATH':\nline",
            reports.BoothConfigUnexpectedLines(["line"], file_path="PATH"),
        )


class BoothInvalidName(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "booth name '/name' is not valid, it cannot contain /{} characters",
            reports.BoothInvalidName("/name", "/{}"),
        )


class BoothTicketNameInvalid(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "booth ticket name 'ticket&' is not valid, use up to 63 "
                "alphanumeric characters or dash"
            ),
            reports.BoothTicketNameInvalid("ticket&"),
        )


class BoothTicketDuplicate(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "booth ticket name 'ticket_name' already exists in configuration",
            reports.BoothTicketDuplicate("ticket_name"),
        )


class BoothTicketDoesNotExist(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "booth ticket name 'ticket_name' does not exist",
            reports.BoothTicketDoesNotExist("ticket_name"),
        )


class BoothTicketNotInCib(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Unable to find ticket 'name' in CIB",
            reports.BoothTicketNotInCib("name"),
        )


class BoothAlreadyInCib(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "booth instance 'name' is already created as cluster resource",
            reports.BoothAlreadyInCib("name"),
        )


class BoothPathNotExists(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Configuration directory for booth 'path' is missing. Is booth "
                "installed?"
            ),
            reports.BoothPathNotExists("path"),
        )


class BoothNotExistsInCib(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "booth instance 'name' not found in cib",
            reports.BoothNotExistsInCib("name"),
        )


class BoothConfigIsUsed(NameBuildTest):
    def test_cluster(self):
        self.assert_message_from_report(
            "booth instance 'name' is used in a cluster resource",
            reports.BoothConfigIsUsed(
                "name", reports.const.BOOTH_CONFIG_USED_IN_CLUSTER_RESOURCE
            ),
        )

    def test_cluster_resource(self):
        self.assert_message_from_report(
            "booth instance 'name' is used in cluster resource 'R'",
            reports.BoothConfigIsUsed(
                "name", reports.const.BOOTH_CONFIG_USED_IN_CLUSTER_RESOURCE, "R"
            ),
        )

    def test_systemd_enabled(self):
        self.assert_message_from_report(
            "booth instance 'name' is used - it is enabled in systemd",
            reports.BoothConfigIsUsed(
                "name", reports.const.BOOTH_CONFIG_USED_ENABLED_IN_SYSTEMD
            ),
        )

    def test_systemd_running(self):
        self.assert_message_from_report(
            "booth instance 'name' is used - it is running by systemd",
            reports.BoothConfigIsUsed(
                "name", reports.const.BOOTH_CONFIG_USED_RUNNING_IN_SYSTEMD
            ),
        )


class BoothMultipleTimesInCib(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "found more than one booth instance 'name' in cib",
            reports.BoothMultipleTimesInCib("name"),
        )


class BoothConfigDistributionStarted(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Sending booth configuration to cluster nodes...",
            reports.BoothConfigDistributionStarted(),
        )


class BoothConfigAcceptedByNode(NameBuildTest):
    def test_defaults(self):
        self.assert_message_from_report(
            "Booth config saved",
            reports.BoothConfigAcceptedByNode(),
        )

    def test_empty_name_list(self):
        self.assert_message_from_report(
            "Booth config saved",
            reports.BoothConfigAcceptedByNode(name_list=[]),
        )

    def test_node_and_empty_name_list(self):
        self.assert_message_from_report(
            "node1: Booth config saved",
            reports.BoothConfigAcceptedByNode(node="node1", name_list=[]),
        )

    def test_name_booth_only(self):
        self.assert_message_from_report(
            "Booth config saved",
            reports.BoothConfigAcceptedByNode(name_list=["booth"]),
        )

    def test_name_booth_and_node(self):
        self.assert_message_from_report(
            "node1: Booth config saved",
            reports.BoothConfigAcceptedByNode(
                node="node1",
                name_list=["booth"],
            ),
        )

    def test_single_name(self):
        self.assert_message_from_report(
            "Booth config 'some' saved",
            reports.BoothConfigAcceptedByNode(name_list=["some"]),
        )

    def test_multiple_names(self):
        self.assert_message_from_report(
            "Booth configs 'another', 'some' saved",
            reports.BoothConfigAcceptedByNode(name_list=["another", "some"]),
        )

    def test_node(self):
        self.assert_message_from_report(
            "node1: Booth configs 'another', 'some' saved",
            reports.BoothConfigAcceptedByNode(
                node="node1",
                name_list=["some", "another"],
            ),
        )


class BoothConfigDistributionNodeError(NameBuildTest):
    def test_empty_name(self):
        self.assert_message_from_report(
            "Unable to save booth config on node 'node1': reason1",
            reports.BoothConfigDistributionNodeError("node1", "reason1"),
        )

    def test_booth_name(self):
        self.assert_message_from_report(
            "Unable to save booth config on node 'node1': reason1",
            reports.BoothConfigDistributionNodeError(
                "node1",
                "reason1",
                name="booth",
            ),
        )

    def test_another_name(self):
        self.assert_message_from_report(
            "Unable to save booth config 'another' on node 'node1': reason1",
            reports.BoothConfigDistributionNodeError(
                "node1",
                "reason1",
                name="another",
            ),
        )


class BoothFetchingConfigFromNode(NameBuildTest):
    def test_empty_name(self):
        self.assert_message_from_report(
            "Fetching booth config from node 'node1'...",
            reports.BoothFetchingConfigFromNode("node1"),
        )

    def test_booth_name(self):
        self.assert_message_from_report(
            "Fetching booth config from node 'node1'...",
            reports.BoothFetchingConfigFromNode("node1", config="booth"),
        )

    def test_another_name(self):
        self.assert_message_from_report(
            "Fetching booth config 'another' from node 'node1'...",
            reports.BoothFetchingConfigFromNode("node1", config="another"),
        )


class BoothUnsupportedFileLocation(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Booth configuration '/some/file' is outside of supported "
                "booth config directory '/booth/conf/dir/', ignoring the file"
            ),
            reports.BoothUnsupportedFileLocation(
                "/some/file",
                "/booth/conf/dir/",
                file_type_codes.BOOTH_CONFIG,
            ),
        )


class BoothDaemonStatusError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "unable to get status of booth daemon: some reason",
            reports.BoothDaemonStatusError("some reason"),
        )


class BoothTicketStatusError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "unable to get status of booth tickets",
            reports.BoothTicketStatusError(),
        )

    def test_all(self):
        self.assert_message_from_report(
            "unable to get status of booth tickets: some reason",
            reports.BoothTicketStatusError(reason="some reason"),
        )


class BoothPeersStatusError(NameBuildTest):
    def test_minimal(self):
        self.assert_message_from_report(
            "unable to get status of booth peers",
            reports.BoothPeersStatusError(),
        )

    def test_all(self):
        self.assert_message_from_report(
            "unable to get status of booth peers: some reason",
            reports.BoothPeersStatusError(reason="some reason"),
        )


class BoothCannotDetermineLocalSiteIp(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "cannot determine local site ip, please specify site parameter",
            reports.BoothCannotDetermineLocalSiteIp(),
        )


class BoothTicketOperationFailed(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "unable to operation booth ticket 'ticket_name'"
                " for site 'site_ip', reason: reason"
            ),
            reports.BoothTicketOperationFailed(
                "operation", "reason", "site_ip", "ticket_name"
            ),
        )

    def test_no_site_ip(self):
        self.assert_message_from_report(
            ("unable to operation booth ticket 'ticket_name', reason: reason"),
            reports.BoothTicketOperationFailed(
                "operation", "reason", None, "ticket_name"
            ),
        )


class BoothTicketChangingState(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Changing state of ticket 'name' to standby",
            reports.BoothTicketChangingState("name", "standby"),
        )


class BoothTicketCleanup(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Cleaning up ticket 'name' from CIB",
            reports.BoothTicketCleanup("name"),
        )


# TODO: remove, use ADD_REMOVE reports
class TagAddRemoveIdsDuplication(NameBuildTest):
    def test_message_add(self):
        self.assert_message_from_report(
            "Ids to add must be unique, duplicate ids: 'dup1', 'dup2'",
            reports.TagAddRemoveIdsDuplication(
                duplicate_ids_list=["dup2", "dup1"],
            ),
        )

    def test_message_remove(self):
        self.assert_message_from_report(
            "Ids to remove must be unique, duplicate ids: 'dup1', 'dup2'",
            reports.TagAddRemoveIdsDuplication(
                duplicate_ids_list=["dup2", "dup1"],
                add_or_not_remove=False,
            ),
        )


# TODO: remove, use ADD_REMOVE reports
class TagAdjacentReferenceIdNotInTheTag(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "There is no reference id 'adj_id' in the tag 'tag_id', cannot "
                "put reference ids next to it in the tag"
            ),
            reports.TagAdjacentReferenceIdNotInTheTag("adj_id", "tag_id"),
        )


# TODO: remove, use ADD_REMOVE reports
class TagCannotAddAndRemoveIdsAtTheSameTime(NameBuildTest):
    def test_message_one_item(self):
        self.assert_message_from_report(
            "Ids cannot be added and removed at the same time: 'id1'",
            reports.TagCannotAddAndRemoveIdsAtTheSameTime(["id1"]),
        )

    def test_message_more_items(self):
        self.assert_message_from_report(
            (
                "Ids cannot be added and removed at the same time: 'id1', "
                "'id2', 'id3'"
            ),
            reports.TagCannotAddAndRemoveIdsAtTheSameTime(
                ["id3", "id2", "id1"],
            ),
        )


# TODO: remove, use ADD_REMOVE reports
class TagCannotAddReferenceIdsAlreadyInTheTag(NameBuildTest):
    def test_message_singular(self):
        self.assert_message_from_report(
            "Cannot add reference id already in the tag 'tag_id': 'id1'",
            reports.TagCannotAddReferenceIdsAlreadyInTheTag(
                "tag_id",
                ["id1"],
            ),
        )

    def test_message_plural(self):
        self.assert_message_from_report(
            "Cannot add reference ids already in the tag 'TAG': 'id1', 'id2'",
            reports.TagCannotAddReferenceIdsAlreadyInTheTag(
                "TAG",
                ["id2", "id1"],
            ),
        )


class TagCannotContainItself(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Tag cannot contain itself", reports.TagCannotContainItself()
        )


class TagCannotCreateEmptyTagNoIdsSpecified(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot create empty tag, no resource ids specified",
            reports.TagCannotCreateEmptyTagNoIdsSpecified(),
        )


# TODO: remove, use ADD_REMOVE reports
class TagCannotPutIdNextToItself(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot put id 'some_id' next to itself.",
            reports.TagCannotPutIdNextToItself("some_id"),
        )


# TODO: remove, use ADD_REMOVE reports
class TagCannotRemoveAdjacentId(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot remove id 'some_id' next to which ids are being added",
            reports.TagCannotRemoveAdjacentId("some_id"),
        )


# TODO: remove, use ADD_REMOVE reports
class TagCannotRemoveReferencesWithoutRemovingTag(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "There would be no references left in the tag 'tag-id'",
            reports.TagCannotRemoveReferencesWithoutRemovingTag("tag-id"),
        )


class TagCannotRemoveTagReferencedInConstraints(NameBuildTest):
    def test_message_singular(self):
        self.assert_message_from_report(
            "Tag 'tag1' cannot be removed because it is referenced in "
            "constraint 'constraint-id-1'",
            reports.TagCannotRemoveTagReferencedInConstraints(
                "tag1",
                ["constraint-id-1"],
            ),
        )

    def test_message_plural(self):
        self.assert_message_from_report(
            "Tag 'tag2' cannot be removed because it is referenced in "
            "constraints 'constraint-id-1', 'constraint-id-2'",
            reports.TagCannotRemoveTagReferencedInConstraints(
                "tag2",
                ["constraint-id-2", "constraint-id-1"],
            ),
        )


class TagCannotRemoveTagsNoTagsSpecified(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot remove tags, no tags to remove specified",
            reports.TagCannotRemoveTagsNoTagsSpecified(),
        )


# TODO: remove, use ADD_REMOVE reports
class TagCannotSpecifyAdjacentIdWithoutIdsToAdd(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot specify adjacent id 'some-id' without ids to add",
            reports.TagCannotSpecifyAdjacentIdWithoutIdsToAdd("some-id"),
        )


# TODO: remove, use ADD_REMOVE reports
class TagCannotUpdateTagNoIdsSpecified(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot update tag, no ids to be added or removed specified",
            reports.TagCannotUpdateTagNoIdsSpecified(),
        )


# TODO: remove, use ADD_REMOVE reports
class TagIdsNotInTheTag(NameBuildTest):
    def test_message_singular(self):
        self.assert_message_from_report(
            "Tag 'tag-id' does not contain id: 'a'",
            reports.TagIdsNotInTheTag("tag-id", ["a"]),
        )

    def test_message_plural(self):
        self.assert_message_from_report(
            "Tag 'tag-id' does not contain ids: 'a', 'b'",
            reports.TagIdsNotInTheTag("tag-id", ["b", "a"]),
        )


class RuleInEffectStatusDetectionNotSupported(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "crm_rule is not available, therefore expired parts of "
                "configuration may not be detected. Consider upgrading pacemaker."
            ),
            reports.RuleInEffectStatusDetectionNotSupported(),
        )


class RuleExpressionOptionsDuplication(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Duplicate options in a single (sub)expression: 'key', 'name'",
            reports.RuleExpressionOptionsDuplication(["name", "key"]),
        )


class RuleExpressionSinceGreaterThanUntil(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Since '987' is not sooner than until '654'",
            reports.RuleExpressionSinceGreaterThanUntil("987", "654"),
        )


class RuleExpressionParseError(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "'resource dummy op monitor' is not a valid rule expression, "
            "parse error near or after line 1 column 16",
            reports.RuleExpressionParseError(
                "resource dummy op monitor",
                "Expected end of text",
                "resource dummy op monitor",
                1,
                16,
                15,
            ),
        )


class RuleExpressionNotAllowed(NameBuildTest):
    def test_op(self):
        self.assert_message_from_report(
            "Keyword 'op' cannot be used in a rule in this command",
            reports.RuleExpressionNotAllowed(
                CibRuleExpressionType.OP_EXPRESSION
            ),
        )

    def test_rsc(self):
        self.assert_message_from_report(
            "Keyword 'resource' cannot be used in a rule in this command",
            reports.RuleExpressionNotAllowed(
                CibRuleExpressionType.RSC_EXPRESSION
            ),
        )

    def test_node_attr(self):
        self.assert_message_from_report(
            "Keywords 'defined', 'not_defined', 'eq', 'ne', 'gte', 'gt', "
            "'lte' and 'lt' cannot be used in a rule in this command",
            reports.RuleExpressionNotAllowed(CibRuleExpressionType.EXPRESSION),
        )


class RuleNoExpressionSpecified(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "No rule expression was specified",
            reports.RuleNoExpressionSpecified(),
        )


class CibNvsetAmbiguousProvideNvsetId(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            "Several options sets exist, please specify an option set ID",
            reports.CibNvsetAmbiguousProvideNvsetId(
                const.PCS_COMMAND_RESOURCE_DEFAULTS_UPDATE
            ),
        )


class AddRemoveItemsNotSpecified(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "Cannot modify stonith resource 'container-id', no devices to "
                "add or remove specified"
            ),
            reports.AddRemoveItemsNotSpecified(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
            ),
        )


class AddRemoveItemsDuplication(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "Devices to add or remove must be unique, duplicate devices: "
                "'dup1', 'dup2'"
            ),
            reports.AddRemoveItemsDuplication(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                ["dup2", "dup1"],
            ),
        )


class AddRemoveCannotAddItemsAlreadyInTheContainer(NameBuildTest):
    def test_message_plural(self):
        self.assert_message_from_report(
            "Cannot add devices 'i1', 'i2', they are already present in stonith"
            " resource 'container-id'",
            reports.AddRemoveCannotAddItemsAlreadyInTheContainer(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                ["i2", "i1"],
            ),
        )

    def test_message_singular(self):
        self.assert_message_from_report(
            "Cannot add device 'i1', it is already present in stonith resource "
            "'container-id'",
            reports.AddRemoveCannotAddItemsAlreadyInTheContainer(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                ["i1"],
            ),
        )


class AddRemoveCannotRemoveItemsNotInTheContainer(NameBuildTest):
    def test_message_plural(self):
        self.assert_message_from_report(
            (
                "Cannot remove devices 'i1', 'i2', they are not present in "
                "stonith resource 'container-id'"
            ),
            reports.AddRemoveCannotRemoveItemsNotInTheContainer(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                ["i2", "i1"],
            ),
        )

    def test_message_singular(self):
        self.assert_message_from_report(
            (
                "Cannot remove device 'i1', it is not present in "
                "stonith resource 'container-id'"
            ),
            reports.AddRemoveCannotRemoveItemsNotInTheContainer(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                ["i1"],
            ),
        )


class AddRemoveCannotAddAndRemoveItemsAtTheSameTime(NameBuildTest):
    def test_message_plural(self):
        self.assert_message_from_report(
            "Devices cannot be added and removed at the same time: 'i1', 'i2'",
            reports.AddRemoveCannotAddAndRemoveItemsAtTheSameTime(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                ["i2", "i1"],
            ),
        )

    def test_message_singular(self):
        self.assert_message_from_report(
            "Device cannot be added and removed at the same time: 'i1'",
            reports.AddRemoveCannotAddAndRemoveItemsAtTheSameTime(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                ["i1"],
            ),
        )


class AddRemoveCannotRemoveAllItemsFromTheContainer(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot remove all devices from stonith resource 'container-id'",
            reports.AddRemoveCannotRemoveAllItemsFromTheContainer(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                ["i1", "i2"],
            ),
        )


class AddRemoveAdjacentItemNotInTheContainer(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "There is no device 'adjacent-item-id' in the stonith resource "
                "'container-id', cannot add devices next to it"
            ),
            reports.AddRemoveAdjacentItemNotInTheContainer(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                "adjacent-item-id",
            ),
        )


class AddRemoveCannotPutItemNextToItself(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Cannot put device 'adjacent-item-id' next to itself",
            reports.AddRemoveCannotPutItemNextToItself(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                "adjacent-item-id",
            ),
        )


class AddRemoveCannotSpecifyAdjacentItemWithoutItemsToAdd(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "Cannot specify adjacent device 'adjacent-item-id' without "
                "devices to add"
            ),
            reports.AddRemoveCannotSpecifyAdjacentItemWithoutItemsToAdd(
                const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
                const.ADD_REMOVE_ITEM_TYPE_DEVICE,
                "container-id",
                "adjacent-item-id",
            ),
        )


class CloningStonithResourcesHasNoEffect(NameBuildTest):
    def test_singular_without_group_id(self):
        self.assert_message_from_report(
            (
                "No need to clone stonith resource 'fence1', any node can use "
                "a stonith resource (unless specifically banned) regardless of "
                "whether the stonith resource is running on that node or not"
            ),
            reports.CloningStonithResourcesHasNoEffect(["fence1"]),
        )

    def test_plural_with_group_id(self):
        self.assert_message_from_report(
            (
                "Group 'StonithGroup' contains stonith resources. No need to "
                "clone stonith resources 'fence1', 'fence2', any node can use "
                "a stonith resource (unless specifically banned) regardless of "
                "whether the stonith resource is running on that node or not"
            ),
            reports.CloningStonithResourcesHasNoEffect(
                ["fence1", "fence2"], "StonithGroup"
            ),
        )


class CommandInvalidPayload(NameBuildTest):
    def test_all(self):
        reason = "a reason"
        self.assert_message_from_report(
            f"Invalid command payload: {reason}",
            reports.CommandInvalidPayload(reason),
        )


class CommandUnknown(NameBuildTest):
    def test_all(self):
        cmd = "a cmd"
        self.assert_message_from_report(
            f"Unknown command '{cmd}'",
            reports.CommandUnknown(cmd),
        )


class NotAuthorized(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            "Current user is not authorized for this operation",
            reports.NotAuthorized(),
        )


class AgentSelfValidationResult(NameBuildTest):
    def test_message(self):
        lines = [f"line #{i}" for i in range(3)]
        self.assert_message_from_report(
            "Validation result from agent:\n  {}".format("\n  ".join(lines)),
            reports.AgentSelfValidationResult("\n".join(lines)),
        )


class AgentSelfValidationInvalidData(NameBuildTest):
    def test_message(self):
        reason = "not xml"
        self.assert_message_from_report(
            f"Invalid validation data from agent: {reason}",
            reports.AgentSelfValidationInvalidData(reason),
        )


class AgentSelfValidationSkippedUpdatedResourceMisconfigured(NameBuildTest):
    def test_message(self):
        lines = [f"line #{i}" for i in range(3)]
        self.assert_message_from_report(
            (
                "The resource was misconfigured before the update, therefore "
                "agent self-validation will not be run for the updated "
                "configuration. Validation output of the original "
                "configuration:\n  {}"
            ).format("\n  ".join(lines)),
            reports.AgentSelfValidationSkippedUpdatedResourceMisconfigured(
                "\n".join(lines)
            ),
        )


class AgentSelfValidationAutoOnWithWarnings(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            (
                "Validating resource options using the resource agent itself "
                "is enabled by default and produces warnings. In a future "
                "version, this might be changed to errors. Enable "
                "agent validation to switch to the future behavior."
            ),
            reports.AgentSelfValidationAutoOnWithWarnings(),
        )


class ResourceCloneIncompatibleMetaAttributes(NameBuildTest):
    def test_with_provider(self):
        attr = "attr_name"
        self.assert_message_from_report(
            f"Clone option '{attr}' is not compatible with 'standard:provider:type' resource agent",
            reports.ResourceCloneIncompatibleMetaAttributes(
                attr, ResourceAgentNameDto("standard", "provider", "type")
            ),
        )

    def test_without_provider(self):
        attr = "attr_name"
        self.assert_message_from_report(
            f"Clone option '{attr}' is not compatible with 'standard:type' resource agent",
            reports.ResourceCloneIncompatibleMetaAttributes(
                attr, ResourceAgentNameDto("standard", None, "type")
            ),
        )

    def test_resource_id(self):
        attr = "attr_name"
        res_id = "resource_id"
        self.assert_message_from_report(
            (
                f"Clone option '{attr}' is not compatible with 'standard:type' "
                f"resource agent of resource '{res_id}'"
            ),
            reports.ResourceCloneIncompatibleMetaAttributes(
                attr,
                ResourceAgentNameDto("standard", None, "type"),
                resource_id=res_id,
            ),
        )

    def test_group_id(self):
        attr = "attr_name"
        res_id = "resource id"
        group_id = "group id"
        self.assert_message_from_report(
            (
                f"Clone option '{attr}' is not compatible with 'standard:type' "
                f"resource agent of resource '{res_id}' in group '{group_id}'"
            ),
            reports.ResourceCloneIncompatibleMetaAttributes(
                attr,
                ResourceAgentNameDto("standard", None, "type"),
                resource_id=res_id,
                group_id=group_id,
            ),
        )


class BoothAuthfileNotUsed(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Booth authfile is not enabled",
            reports.BoothAuthfileNotUsed("instance name"),
        )


class BoothUnsupportedOptionEnableAuthfile(NameBuildTest):
    def test_message(self):
        self.assert_message_from_report(
            "Unsupported option 'enable-authfile' is set in booth configuration",
            reports.BoothUnsupportedOptionEnableAuthfile("instance name"),
        )


class CannotCreateDefaultClusterPropertySet(NameBuildTest):
    def test_all(self):
        self.assert_message_from_report(
            (
                "Cannot create default cluster_property_set element, ID "
                "'cib-bootstrap-options' already exists. Find elements with the"
                " ID and remove them from cluster configuration."
            ),
            reports.CannotCreateDefaultClusterPropertySet(
                "cib-bootstrap-options"
            ),
        )


class ClusterStatusBundleMemberIdAsImplicit(NameBuildTest):
    def test_one(self):
        self.assert_message_from_report(
            (
                "Skipping bundle 'resource-bundle': resource 'resource' has "
                "the same id as some of the implicit bundle resources"
            ),
            reports.ClusterStatusBundleMemberIdAsImplicit(
                "resource-bundle", ["resource"]
            ),
        )

    def test_multiple(self):
        self.assert_message_from_report(
            (
                "Skipping bundle 'resource-bundle': resources 'resource-0', "
                "'resource-1' have the same id as some of the implicit bundle "
                "resources"
            ),
            reports.ClusterStatusBundleMemberIdAsImplicit(
                "resource-bundle", ["resource-0", "resource-1"]
            ),
        )


class ResourceWaitDeprecated(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Ability of this command to accept 'wait' argument is "
                "deprecated and will be removed in a future release."
            ),
            reports.ResourceWaitDeprecated(),
        )


class CommandArgumentTypeMismatch(NameBuildTest):
    def test_message(self) -> str:
        self.assert_message_from_report(
            "This command does not accept entity type.",
            reports.CommandArgumentTypeMismatch(
                "entity type", "pcs stonith create"
            ),
        )


class ResourceRestartError(NameBuildTest):
    def test_message(self) -> str:
        self.assert_message_from_report(
            "Unable to restart resource 'resourceId':\nerror description",
            reports.ResourceRestartError("error description", "resourceId"),
        )


class ResourceRestartNodeIsForMultiinstanceOnly(NameBuildTest):
    def test_message(self) -> str:
        self.assert_message_from_report(
            (
                "Can only restart on a specific node for a clone or bundle, "
                "'resourceId' is a resource"
            ),
            reports.ResourceRestartNodeIsForMultiinstanceOnly(
                "resourceId", "primitive", "node01"
            ),
        )


class ResourceRestartUsingParentRersource(NameBuildTest):
    def test_message(self) -> str:
        self.assert_message_from_report(
            (
                "Restarting 'parentId' instead...\n"
                "(If a resource is a clone or bundle, you must use the clone "
                "or bundle instead)"
            ),
            reports.ResourceRestartUsingParentRersource(
                "resourceId", "parentId"
            ),
        )


class ClusterOptionsMetadataNotSupported(NameBuildTest):
    def test_success(self):
        self.assert_message_from_report(
            (
                "Cluster options metadata are not supported, please upgrade "
                "pacemaker"
            ),
            reports.ClusterOptionsMetadataNotSupported(),
        )


class StoppingResourcesBeforeDeleting(NameBuildTest):
    def test_one_resource(self) -> str:
        self.assert_message_from_report(
            "Stopping resource 'resourceId' before deleting",
            reports.StoppingResourcesBeforeDeleting(["resourceId"]),
        )

    def test_multiple_resources(self) -> str:
        self.assert_message_from_report(
            "Stopping resources 'resourceId1', 'resourceId2' before deleting",
            reports.StoppingResourcesBeforeDeleting(
                ["resourceId1", "resourceId2"]
            ),
        )


class StoppingResourcesBeforeDeletingSkipped(NameBuildTest):
    def test_success(self) -> str:
        self.assert_message_from_report(
            (
                "Resources are not going to be stopped before deletion, this "
                "may result in orphaned resources being present in the cluster"
            ),
            reports.StoppingResourcesBeforeDeletingSkipped(),
        )


class CannotStopResourcesBeforeDeleting(NameBuildTest):
    def test_one_resource(self) -> str:
        self.assert_message_from_report(
            "Cannot stop resource 'resourceId' before deleting",
            reports.CannotStopResourcesBeforeDeleting(["resourceId"]),
        )

    def test_multiple_resources(self) -> str:
        self.assert_message_from_report(
            "Cannot stop resources 'resourceId1', 'resourceId2' before deleting",
            reports.CannotStopResourcesBeforeDeleting(
                ["resourceId1", "resourceId2"]
            ),
        )

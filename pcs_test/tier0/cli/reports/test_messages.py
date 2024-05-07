import inspect
from typing import Optional
from unittest import TestCase

from pcs.cli.reports import messages as cli_messages
from pcs.common import file_type_codes
from pcs.common.reports import (
    codes,
    const,
    item,
    messages,
    types,
)


class AllClassesTested(TestCase):
    def test_success(self):
        self.maxDiff = None
        message_classes = frozenset(
            name
            for name, member in inspect.getmembers(
                cli_messages, inspect.isclass
            )
            if issubclass(member, cli_messages.CliReportMessageCustom)
            and member != cli_messages.CliReportMessageCustom
        )
        test_classes = frozenset(
            name
            for name, member in inspect.getmembers(
                inspect.getmodule(self), inspect.isclass
            )
            if issubclass(member, CliReportMessageTestBase)
        )
        untested = sorted(message_classes - test_classes)
        self.assertEqual(
            untested,
            [],
            f"It seems {len(untested)} subclass(es) of 'CliReportMessageCustom' "
            "are missing tests. Make sure the test classes have the same name "
            "as the code classes.",
        )


class CliReportMessageTestBase(TestCase):
    maxDiff = None

    @staticmethod
    def _get_cli_msg_obj(
        msg_obj: item.ReportItemMessage,
    ) -> cli_messages.CliReportMessage:
        return cli_messages.report_item_msg_from_dto(msg_obj.to_dto())

    def assert_message(
        self, msg_obj: item.ReportItemMessage, expected_msg: str
    ) -> None:
        self.assertEqual(self._get_cli_msg_obj(msg_obj).message, expected_msg)
        self.assert_same_messages_with_force_code(msg_obj, None)

    def assert_message_with_force_code(
        self,
        msg_obj: item.ReportItemMessage,
        force_code: types.ForceCode,
        expected_msg: str,
    ) -> None:
        self.assertEqual(
            self._get_cli_msg_obj(msg_obj).get_message_with_force_text(
                force_code
            ),
            expected_msg,
        )

    def assert_same_messages_with_force_code(
        self,
        msg_obj: item.ReportItemMessage,
        force_code: Optional[types.ForceCode],
    ) -> None:
        cli_msg_obj = self._get_cli_msg_obj(msg_obj)
        self.assertEqual(
            cli_msg_obj.get_message_with_force_text(force_code),
            cli_msg_obj.message,
        )


class ResourceManagedNoMonitorEnabled(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.ResourceManagedNoMonitorEnabled("resId"),
            (
                "Resource 'resId' has no enabled monitor operations. Re-run "
                "with '--monitor' to enable them."
            ),
        )


class ResourceUnmoveUnbanPcmkExpiredNotSupported(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.ResourceUnmoveUnbanPcmkExpiredNotSupported(),
            "--expired not supported, please upgrade pacemaker",
        )


class CannotUnmoveUnbanResourceMasterResourceNotPromotable(
    CliReportMessageTestBase
):
    def test_with_promotable_id(self):
        self.assert_message(
            messages.CannotUnmoveUnbanResourceMasterResourceNotPromotable(
                "R", "P"
            ),
            (
                "when specifying --promoted you must use the promotable clone "
                "id (P)"
            ),
        )

    def test_without_promotable_id(self):
        self.assert_message(
            messages.CannotUnmoveUnbanResourceMasterResourceNotPromotable("R"),
            "when specifying --promoted you must use the promotable clone id",
        )


class CannotBanResourceMasterResourceNotPromotable(CliReportMessageTestBase):
    def test_with_promotable_id(self):
        self.assert_message(
            messages.CannotBanResourceMasterResourceNotPromotable("R", "P"),
            (
                "when specifying --promoted you must use the promotable clone "
                "id (P)"
            ),
        )

    def test_without_promotable_id(self):
        self.assert_message(
            messages.CannotBanResourceMasterResourceNotPromotable("R"),
            "when specifying --promoted you must use the promotable clone id",
        )


class CannotMoveResourceMasterResourceNotPromotable(CliReportMessageTestBase):
    def test_with_promotable_id(self):
        self.assert_message(
            messages.CannotMoveResourceMasterResourceNotPromotable("R", "P"),
            (
                "when specifying --promoted you must use the promotable clone "
                "id (P)"
            ),
        )

    def test_without_promotable_id(self):
        self.assert_message(
            messages.CannotMoveResourceMasterResourceNotPromotable("R"),
            "when specifying --promoted you must use the promotable clone id",
        )


class CannotMoveResourceNotRunning(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.CannotMoveResourceNotRunning("R"),
            (
                "It is not possible to move resource 'R' as it is not running "
                "at the moment, use 'pcs resource move-with-constraint' or "
                "'pcs constraint location' commands instead"
            ),
        )


class InvalidCibContent(CliReportMessageTestBase):
    def test_message_can_be_more_verbose(self):
        report = "no verbose\noutput\n"
        self.assert_message(
            messages.InvalidCibContent(report, True),
            "invalid cib:\n{0}\n\nUse --full for more details.".format(report),
        )

    def test_message_cannot_be_more_verbose(self):
        report = "some verbose\noutput"
        self.assert_message(
            messages.InvalidCibContent(report, False),
            "invalid cib:\n{0}".format(report),
        )


class NodeCommunicationErrorNotAuthorized(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.NodeCommunicationErrorNotAuthorized(
                "node1", "some-command", "some error"
            ),
            (
                "Unable to authenticate to node1 (some error), try running "
                "'pcs host auth node1'"
            ),
        )


class NodeCommunicationErrorTimedOut(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.NodeCommunicationErrorTimedOut(
                "node-1",
                "/remote/command",
                "Connection timed out after 60049 milliseconds",
            ),
            (
                "node-1: Connection timeout, check if pcsd is running there or "
                "try setting higher timeout with --request-timeout option "
                "(Connection timed out after 60049 milliseconds)"
            ),
        )


class SbdWatchdogTestMultipleDevices(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.SbdWatchdogTestMultipleDevices(),
            (
                "Multiple watchdog devices available, therefore, watchdog "
                "which should be tested has to be specified. To list available "
                "watchdog devices use command 'pcs stonith sbd watchdog list'"
            ),
        )


class NodeUsedAsTieBreaker(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.NodeUsedAsTieBreaker("node-1", "0"),
            (
                "Node 'node-1' with id '0' is used as a tie breaker for a "
                "qdevice and therefore cannot be removed, run 'pcs quorum "
                "device update model tie_breaker=<node id>' to change it"
            ),
        )


class NodesToRemoveUnreachable(CliReportMessageTestBase):
    def test_one_node(self):
        self.assert_message(
            messages.NodesToRemoveUnreachable(["node1"]),
            (
                "Removed node 'node1' could not be reached and subsequently "
                "deconfigured. Run 'pcs cluster destroy' on the unreachable "
                "node."
            ),
        )

    def test_multiple_nodes(self):
        self.assert_message(
            messages.NodesToRemoveUnreachable(["node2", "node1"]),
            (
                "Removed nodes 'node1', 'node2' could not be reached and "
                "subsequently deconfigured. Run 'pcs cluster destroy' on the "
                "unreachable nodes."
            ),
        )


class UnableToConnectToAllRemainingNodes(CliReportMessageTestBase):
    def test_one_node(self):
        self.assert_message(
            messages.UnableToConnectToAllRemainingNodes(["node1"]),
            (
                "Remaining cluster node 'node1' could not be reached, run "
                "'pcs cluster sync' on any currently online node once the "
                "unreachable one become available"
            ),
        )

    def test_multiple_nodes(self):
        self.assert_message(
            messages.UnableToConnectToAllRemainingNodes(["node2", "node1"]),
            (
                "Remaining cluster nodes 'node1', 'node2' could not be "
                "reached, run 'pcs cluster sync' on any currently online node "
                "once the unreachable ones become available"
            ),
        )


class CannotRemoveAllClusterNodes(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.CannotRemoveAllClusterNodes(),
            (
                "No nodes would be left in the cluster, if you intend to "
                "destroy the whole cluster, run 'pcs cluster destroy --all' "
                "instead"
            ),
        )


class WaitForNodeStartupWithoutStart(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.WaitForNodeStartupWithoutStart(),
            "Cannot specify '--wait' without specifying '--start'",
        )


class HostNotFound(CliReportMessageTestBase):
    def test_one_node(self):
        self.assert_message(
            messages.HostNotFound(["node1"]),
            (
                "Host 'node1' is not known to pcs, try to "
                "authenticate the host using 'pcs host auth node1' "
                "command"
            ),
        )

    def test_multiple_nodes(self):
        self.assert_message(
            messages.HostNotFound(["node2", "node1"]),
            (
                "Hosts 'node1', 'node2' are not known to pcs, try to "
                "authenticate the hosts using 'pcs host auth node1 node2' "
                "command"
            ),
        )


class UseCommandNodeRemoveGuest(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.UseCommandNodeRemoveGuest(),
            (
                "this command is not sufficient for removing a guest node, use"
                " 'pcs cluster node remove-guest'"
            ),
        )


class UseCommandNodeAddGuest(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.UseCommandNodeAddGuest(),
            (
                "this command is not sufficient for creating a guest node, use"
                " 'pcs cluster node add-guest'"
            ),
        )


class UseCommandNodeAddRemote(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.UseCommandNodeAddRemote(),
            (
                "this command is not sufficient for creating a remote "
                "connection, use 'pcs cluster node add-remote'"
            ),
        )


class CorosyncNodeConflictCheckSkipped(CliReportMessageTestBase):
    def test_not_live_cib(self):
        self.assert_message(
            messages.CorosyncNodeConflictCheckSkipped(
                const.REASON_NOT_LIVE_CIB
            ),
            (
                "Unable to check if there is a conflict with nodes set in "
                "corosync because the command does not run on a live cluster "
                "(e.g. -f "
                "was used)"
            ),
        )

    def test_unreachable(self):
        self.assert_message(
            messages.CorosyncNodeConflictCheckSkipped(const.REASON_UNREACHABLE),
            (
                "Unable to check if there is a conflict with nodes set in "
                "corosync because pcs is unable to connect to the node(s)"
            ),
        )


class LiveEnvironmentNotConsistent(CliReportMessageTestBase):
    def test_one_one(self):
        self.assert_message(
            messages.LiveEnvironmentNotConsistent(
                [file_type_codes.BOOTH_CONFIG],
                [file_type_codes.BOOTH_KEY],
            ),
            (
                "When '--booth-conf' is specified, "
                "'--booth-key' must be specified as well"
            ),
        )

    def test_many_many(self):
        self.assert_message(
            messages.LiveEnvironmentNotConsistent(
                [file_type_codes.CIB, file_type_codes.BOOTH_CONFIG],
                [file_type_codes.COROSYNC_CONF, file_type_codes.BOOTH_KEY],
            ),
            (
                "When '--booth-conf', '-f' are specified, "
                "'--booth-key', '--corosync_conf' must be specified as well"
            ),
        )


class LiveEnvironmentRequired(CliReportMessageTestBase):
    def test_build_messages_transformable_codes(self):
        self.assert_message(
            messages.LiveEnvironmentRequired(
                [file_type_codes.COROSYNC_CONF, file_type_codes.CIB]
            ),
            "This command does not support '--corosync_conf', '-f'",
        )


class LiveEnvironmentRequiredForLocalNode(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.LiveEnvironmentRequiredForLocalNode(),
            "Node(s) must be specified if -f is used",
        )


class ServiceCommandsOnNodesSkipped(CliReportMessageTestBase):
    def test_not_live(self):
        self.assert_message(
            messages.ServiceCommandsOnNodesSkipped(
                const.REASON_NOT_LIVE_CIB,
                ["pacemaker_remote enable", "pacemaker_remote start"],
                ["nodeA", "nodeB"],
            ),
            "Running action(s) 'pacemaker_remote enable', 'pacemaker_remote "
            "start' on 'nodeA', 'nodeB' was skipped because the command "
            "does not run on a live cluster (e.g. -f was used). Please, "
            "run the action(s) manually.",
        )

    def test_unreachable(self):
        self.assert_message(
            messages.ServiceCommandsOnNodesSkipped(
                const.REASON_UNREACHABLE,
                ["pacemaker_remote enable", "pacemaker_remote start"],
                ["nodeA", "nodeB"],
            ),
            "Running action(s) 'pacemaker_remote enable', 'pacemaker_remote "
            "start' on 'nodeA', 'nodeB' was skipped because pcs is unable "
            "to connect to the node(s). Please, run the action(s) manually.",
        )

    def test_unknown_reason(self):
        self.assert_message(
            messages.ServiceCommandsOnNodesSkipped(
                "some undefined reason",
                ["pacemaker_remote enable", "pacemaker_remote start"],
                ["nodeA", "nodeB"],
            ),
            "Running action(s) 'pacemaker_remote enable', 'pacemaker_remote "
            "start' on 'nodeA', 'nodeB' was skipped because some undefined "
            "reason. Please, run the action(s) manually.",
        )


class FilesRemoveFromNodesSkipped(CliReportMessageTestBase):
    def test_not_live(self):
        self.assert_message(
            messages.FilesRemoveFromNodesSkipped(
                const.REASON_NOT_LIVE_CIB, ["file1"], ["nodeA", "nodeB"]
            ),
            "Removing 'file1' from 'nodeA', 'nodeB' was skipped because the "
            "command does not run on a live cluster (e.g. -f was used). "
            "Please, remove the file(s) manually.",
        )

    def test_unreachable(self):
        self.assert_message(
            messages.FilesRemoveFromNodesSkipped(
                const.REASON_UNREACHABLE, ["file1", "file2"], ["nodeA"]
            ),
            "Removing 'file1', 'file2' from 'nodeA' was skipped because pcs is "
            "unable to connect to the node(s). Please, remove the file(s) "
            "manually.",
        )

    def test_unknown_reason(self):
        self.assert_message(
            messages.FilesRemoveFromNodesSkipped(
                "some undefined reason", ["file1", "file2"], ["nodeA", "nodeB"]
            ),
            "Removing 'file1', 'file2' from 'nodeA', 'nodeB' was skipped "
            "because some undefined reason. Please, remove the file(s) "
            "manually.",
        )


class FilesDistributionSkipped(CliReportMessageTestBase):
    def test_not_live(self):
        self.assert_message(
            messages.FilesDistributionSkipped(
                const.REASON_NOT_LIVE_CIB, ["file1"], ["nodeA", "nodeB"]
            ),
            "Distribution of 'file1' to 'nodeA', 'nodeB' was skipped because "
            "the command does not run on a live cluster (e.g. -f was used). "
            "Please, distribute the file(s) manually.",
        )

    def test_unreachable(self):
        self.assert_message(
            messages.FilesDistributionSkipped(
                const.REASON_UNREACHABLE, ["file1", "file2"], ["nodeA"]
            ),
            "Distribution of 'file1', 'file2' to 'nodeA' was skipped because "
            "pcs is unable to connect to the node(s). Please, distribute "
            "the file(s) manually.",
        )

    def test_unknown_reason(self):
        self.assert_message(
            messages.FilesDistributionSkipped(
                "some undefined reason", ["file1", "file2"], ["nodeA", "nodeB"]
            ),
            "Distribution of 'file1', 'file2' to 'nodeA', 'nodeB' was skipped "
            "because some undefined reason. Please, distribute the file(s) "
            "manually.",
        )


class WaitForIdleNotLiveCluster(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.WaitForIdleNotLiveCluster(),
            "Cannot use '-f' together with '--wait'",
        )


class TagCannotRemoveReferencesWithoutRemovingTag(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.TagCannotRemoveReferencesWithoutRemovingTag("tag-id"),
            (
                "There would be no references left in the tag 'tag-id', please "
                "remove the whole tag using the 'pcs tag remove tag-id' command"
            ),
        )


class RuleExpressionParseError(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.RuleExpressionParseError(
                "resource dummy op monitor",
                "Expected end of text",
                "resource dummy op monitor",
                1,
                16,
                15,
            ),
            "'resource dummy op monitor' is not a valid rule expression, "
            "parse error near or after line 1 column 16\n"
            "  resource dummy op monitor\n"
            "  ---------------^",
        )


class CibNvsetAmbiguousProvideNvsetId(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.CibNvsetAmbiguousProvideNvsetId(
                const.PCS_COMMAND_RESOURCE_DEFAULTS_UPDATE
            ),
            "Several options sets exist, please use the 'pcs resource defaults "
            "set update' command and specify an option set ID",
        )


class UnableToGetAgentMetadata(CliReportMessageTestBase):
    def test_all(self):
        self.assert_message(
            messages.UnableToGetAgentMetadata(
                "agent-name", "reason\non multiple lines"
            ),
            "Agent 'agent-name' is not installed or does not provide valid "
            "metadata: reason, on multiple lines",
        )


class InvalidResourceAgentName(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.InvalidResourceAgentName(":name"),
            "Invalid resource agent name ':name'. Use standard:provider:type "
            "when standard is 'ocf' or standard:type otherwise. List of standards "
            "and providers can be obtained by using commands 'pcs resource "
            "standards' and 'pcs resource providers'.",
        )


class InvalidStonithAgentName(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.InvalidStonithAgentName("fence:name"),
            "Invalid stonith agent name 'fence:name'. Agent name cannot contain "
            "the ':' character, do not use the 'stonith:' prefix. List of agents "
            "can be obtained by using command 'pcs stonith list'.",
        )


class HostAlreadyInClusterConfig(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.HostAlreadyInClusterConfig("nodeX"),
            "nodeX: The host seems to be in a cluster already as cluster "
            "configuration files have been found on the host. If the host is "
            "not part of a cluster, run 'pcs cluster destroy' on host 'nodeX' "
            "to remove those configuration files",
        )


class CannotLeaveGroupEmptyAfterMove(CliReportMessageTestBase):
    def test_single_resource(self):
        self.assert_message(
            messages.CannotLeaveGroupEmptyAfterMove("gr1", ["R"]),
            "Unable to move resource 'R' as it would leave group 'gr1' empty. "
            "Please, use the 'pcs resource ungroup gr1' command first.",
        )

    def test_multiple_resources(self):
        self.assert_message(
            messages.CannotLeaveGroupEmptyAfterMove("gr1", ["R3", "R1", "R2"]),
            "Unable to move resources 'R1', 'R2', 'R3' as it would leave "
            "group 'gr1' empty. Please, use the 'pcs resource ungroup gr1' "
            "command first.",
        )


class StonithRestartlessUpdateUnableToPerform(CliReportMessageTestBase):
    def test_other_reason(self):
        report_msg = messages.StonithRestartlessUpdateUnableToPerform("reason")
        self.assert_message(
            report_msg,
            report_msg.message,
        )

    def test_not_running_reason(self):
        report_msg = messages.StonithRestartlessUpdateUnableToPerform(
            "reason",
            const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_NOT_RUNNING,
        )
        self.assert_message(
            report_msg,
            f"{report_msg.message}, please use command 'pcs stonith update' instead",
        )


class CommandArgumentTypeMismatch(CliReportMessageTestBase):
    def test_no_cmd(self):
        report_msg = messages.CommandArgumentTypeMismatch("element type")
        self.assert_message(
            report_msg,
            report_msg.message,
        )

    def test_unknown_cmd(self):
        report_msg = messages.CommandArgumentTypeMismatch(
            "element type", const.PCS_COMMAND_RESOURCE_CREATE
        )
        self.assert_message(
            report_msg,
            report_msg.message,
        )

    def test_use_instead(self):
        report_msg = messages.CommandArgumentTypeMismatch(
            "element type", const.PCS_COMMAND_STONITH_CREATE
        )
        self.assert_message(
            report_msg,
            f"{report_msg.message} Use 'pcs stonith create' command instead.",
        )


class NotAuthorized(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.NotAuthorized(),
            "Current user is not authorized for this operation",
        )


class AgentSelfValidationResult(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.AgentSelfValidationResult("line 1\nline 3\nline 2"),
            "Validation result from agent:\n  line 1\n  line 3\n  line 2",
        )

    def test_force(self):
        self.assert_message_with_force_code(
            messages.AgentSelfValidationResult("line 1\nline 3\nline 2"),
            codes.FORCE,
            "Validation result from agent (use --force to override):\n  line 1\n  line 3\n  line 2",
        )

    def test_unknown_force_code(self):
        self.assert_same_messages_with_force_code(
            messages.AgentSelfValidationResult("line 1\nline 3\nline 2"),
            codes.SKIP_OFFLINE_NODES,
        )


class AgentSelfValidationAutoOnWithWarnings(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.AgentSelfValidationAutoOnWithWarnings(),
            (
                "Validating resource options using the resource agent itself "
                "is enabled by default and produces warnings. In a future "
                "version, this might be changed to errors. Specify "
                "--agent-validation to switch to the future behavior."
            ),
        )


class BoothAuthfileNotUsed(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.BoothAuthfileNotUsed("instance"),
            (
                "Booth authfile is not enabled. Run 'pcs booth enable-authfile "
                "--name instance' to enable usage of authfile."
            ),
        )


class BoothUnsupportedOptionEnableAuthfile(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.BoothUnsupportedOptionEnableAuthfile("instance"),
            (
                "Unsupported option 'enable-authfile' is set in booth "
                "configuration. Run 'pcs booth clean-enable-authfile --name "
                "instance' to remove the option."
            ),
        )


class CorosyncNotRunningCheckFinishedRunning(CliReportMessageTestBase):
    def test_one_node(self):
        self.assert_message(
            messages.CorosyncNotRunningCheckFinishedRunning(["node1"]),
            (
                "Corosync is running on node 'node1'. Requested change can "
                "only be made if the cluster is stopped. In order to proceed, "
                "stop the cluster. Run \"pcs cluster stop 'node1'\" to stop "
                'the node or "pcs cluster stop --all" to stop the whole cluster.'
            ),
        )

    def test_more_nodes(self):
        self.assert_message(
            messages.CorosyncNotRunningCheckFinishedRunning(
                ["node2", "node1", "node3"]
            ),
            (
                "Corosync is running on nodes 'node1', 'node2', 'node3'. "
                "Requested change can only be made if the cluster is stopped. "
                'In order to proceed, stop the cluster. Run "pcs cluster stop '
                "'node1' 'node2' 'node3'\" to stop the nodes or \"pcs cluster "
                'stop --all" to stop the whole cluster.'
            ),
        )


class CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning(
    CliReportMessageTestBase
):
    def test_success(self):
        self.assert_message(
            messages.CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning(),
            (
                "SBD fencing is enabled in the cluster. To keep it effective, "
                "auto_tie_breaker quorum option needs to be enabled. This can "
                "only be done when the cluster is stopped. To proceed, stop the "
                "cluster, enable auto_tie_breaker, and start the cluster. Then, "
                "repeat the requested action. Use commands 'pcs cluster stop "
                "--all', 'pcs quorum update auto_tie_breaker=1', 'pcs cluster "
                "start --all'."
            ),
        )


class ResourceMoveAutocleanSimulationFailure(CliReportMessageTestBase):
    def test_constraint_not_created(self):
        self.assert_message(
            messages.ResourceMoveAutocleanSimulationFailure(
                "R1", others_affected=True
            ),
            (
                "Unable to ensure that moved resource 'R1' or other resources "
                "will stay on the same node after a constraint used for moving "
                "it is removed."
            ),
        )

    def test_without_node(self):
        self.assert_message(
            messages.ResourceMoveAutocleanSimulationFailure(
                "R1", others_affected=True, move_constraint_left_in_cib=True
            ),
            (
                "Unable to ensure that moved resource 'R1' or other resources "
                "will stay on the same node after a constraint used for moving "
                "it is removed."
                " The constraint to move the resource has not been removed "
                "from configuration. Consider removing it manually. Be aware "
                "that removing the constraint may cause resources to move to "
                "other nodes."
                " Run 'pcs resource clear R1' to remove the constraint."
            ),
        )

    def test_with_node(self):
        self.assert_message(
            messages.ResourceMoveAutocleanSimulationFailure(
                "R1",
                others_affected=False,
                node="node1",
                move_constraint_left_in_cib=True,
            ),
            (
                "Unable to ensure that moved resource 'R1' will stay on the "
                "same node after a constraint used for moving it is removed."
                " The constraint to move the resource has not been removed "
                "from configuration. Consider removing it manually. Be aware "
                "that removing the constraint may cause resources to move to "
                "other nodes."
                " Run 'pcs resource clear R1 node1' to remove the constraint."
            ),
        )


class ResourceWaitDeprecated(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.ResourceWaitDeprecated(),
            (
                "Using '--wait' is deprecated. Instead, use the 'pcs status "
                "wait' command to wait for the cluster to settle into stable "
                "state. Use the 'pcs status query resource' commands to verify "
                "that the resource is in the expected state after the wait."
            ),
        )

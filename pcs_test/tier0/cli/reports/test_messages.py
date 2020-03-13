from unittest import TestCase

from pcs.common import file_type_codes
from pcs.common.reports import (
    item,
    messages,
)
from pcs.cli.reports import messages as cli_messages


class CliReportMessageTestBase(TestCase):
    def assert_message(
        self, msg_obj: item.ReportItemMessage, expected_msg: str
    ) -> None:
        self.assertEqual(
            cli_messages.report_item_msg_from_dto(msg_obj.to_dto()).message,
            expected_msg,
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
                "when specifying --master you must use the promotable clone id "
                "(P)"
            ),
        )

    def test_without_promotable_id(self):
        self.assert_message(
            messages.CannotUnmoveUnbanResourceMasterResourceNotPromotable("R"),
            "when specifying --master you must use the promotable clone id",
        )


class CannotBanResourceMasterResourceNotPromotable(CliReportMessageTestBase):
    def test_with_promotable_id(self):
        self.assert_message(
            messages.CannotBanResourceMasterResourceNotPromotable("R", "P"),
            (
                "when specifying --master you must use the promotable clone id "
                "(P)"
            ),
        )

    def test_without_promotable_id(self):
        self.assert_message(
            messages.CannotBanResourceMasterResourceNotPromotable("R"),
            "when specifying --master you must use the promotable clone id",
        )


class CannotMoveResourceMasterResourceNotPromotable(CliReportMessageTestBase):
    def test_with_promotable_id(self):
        self.assert_message(
            messages.CannotMoveResourceMasterResourceNotPromotable("R", "P"),
            (
                "when specifying --master you must use the promotable clone id "
                "(P)"
            ),
        )

    def test_without_promotable_id(self):
        self.assert_message(
            messages.CannotMoveResourceMasterResourceNotPromotable("R"),
            "when specifying --master you must use the promotable clone id",
        )


class CannotMoveResourcePromotableNotMaster(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.CannotMoveResourcePromotableNotMaster("R", "P"),
            (
                "to move promotable clone resources you must use --master and "
                "the promotable clone id (P)"
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
                "node-1: Connection timeout, try setting higher timeout in "
                "--request-timeout option (Connection timed out after 60049 "
                "milliseconds)"
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
                "qdevice, run 'pcs quorum device update model "
                "tie_breaker=<node id>' to change it"
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


class UnableToConnectToAllRemainingNode(CliReportMessageTestBase):
    def test_one_node(self):
        self.assert_message(
            messages.UnableToConnectToAllRemainingNode(["node1"]),
            (
                "Remaining cluster node 'node1' could not be reached, run "
                "'pcs cluster sync' on any currently online node once the "
                "unreachable one become available"
            ),
        )

    def test_multiple_nodes(self):
        self.assert_message(
            messages.UnableToConnectToAllRemainingNode(["node2", "node1"]),
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
            messages.CorosyncNodeConflictCheckSkipped(messages.NOT_LIVE_CIB),
            (
                "Unable to check if there is a conflict with nodes set in "
                "corosync because the command does not run on a live cluster "
                "(e.g. -f "
                "was used)"
            ),
        )

    def test_unreachable(self):
        self.assert_message(
            messages.CorosyncNodeConflictCheckSkipped(messages.UNREACHABLE),
            (
                "Unable to check if there is a conflict with nodes set in "
                "corosync because pcs is unable to connect to the node(s)"
            ),
        )


class LiveEnvironmentNotConsistent(CliReportMessageTestBase):
    def test_one_one(self):
        self.assert_message(
            messages.LiveEnvironmentNotConsistent(
                [file_type_codes.BOOTH_CONFIG], [file_type_codes.BOOTH_KEY],
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
                messages.NOT_LIVE_CIB,
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
                messages.UNREACHABLE,
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
                messages.NOT_LIVE_CIB, ["file1"], ["nodeA", "nodeB"]
            ),
            "Removing 'file1' from 'nodeA', 'nodeB' was skipped because the "
            "command does not run on a live cluster (e.g. -f was used). "
            "Please, remove the file(s) manually.",
        )

    def test_unreachable(self):
        self.assert_message(
            messages.FilesRemoveFromNodesSkipped(
                messages.UNREACHABLE, ["file1", "file2"], ["nodeA"]
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
                messages.NOT_LIVE_CIB, ["file1"], ["nodeA", "nodeB"]
            ),
            "Distribution of 'file1' to 'nodeA', 'nodeB' was skipped because "
            "the command does not run on a live cluster (e.g. -f was used). "
            "Please, distribute the file(s) manually.",
        )

    def test_unreachable(self):
        self.assert_message(
            messages.FilesDistributionSkipped(
                messages.UNREACHABLE, ["file1", "file2"], ["nodeA"]
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


# TODO: create test/check that all subclasses of
# pcs.cli.reports.messages.CliReportMessageCustom have their test class with
# the same name in this file

from functools import partial
from typing import (
    Any,
    Dict,
    Mapping,
    Optional,
    get_type_hints,
)

from pcs.common import file_type_codes
from pcs.common.reports import (
    codes,
    const,
    dto,
    item,
    messages,
    types,
)
from pcs.common.str_tools import (
    format_list,
    format_optional,
    format_plural,
    indent,
    transform,
)
from pcs.common.tools import get_all_subclasses


class CliReportMessage:
    def __init__(self, dto_obj: dto.ReportItemMessageDto) -> None:
        self._dto_obj = dto_obj

    @property
    def code(self) -> str:
        return self._dto_obj.code

    @property
    def message(self) -> str:
        return self._dto_obj.message

    @property
    def payload(self) -> Mapping[str, Any]:
        return self._dto_obj.payload

    def get_message_with_force_text(
        self, force_code: Optional[types.ForceCode]
    ) -> str:
        force_text_map = {
            codes.SKIP_OFFLINE_NODES: ", use --skip-offline to override",
        }
        force_text = (
            force_text_map.get(force_code, ", use --force to override")
            if force_code
            else ""
        )

        return f"{self.message}{force_text}"


class CliReportMessageCustom(CliReportMessage):
    _obj: item.ReportItemMessage

    def __init__(self, dto_obj: dto.ReportItemMessageDto) -> None:
        super().__init__(dto_obj)
        self._obj = get_type_hints(self.__class__).get("_obj")(  # type: ignore
            **dto_obj.payload
        )

    @property
    def message(self) -> str:
        raise NotImplementedError()


class ResourceManagedNoMonitorEnabled(CliReportMessageCustom):
    _obj: messages.ResourceManagedNoMonitorEnabled

    @property
    def message(self) -> str:
        return (
            f"Resource '{self._obj.resource_id}' has no enabled monitor "
            "operations. Re-run with '--monitor' to enable them."
        )


class ResourceUnmoveUnbanPcmkExpiredNotSupported(CliReportMessageCustom):
    _obj: messages.ResourceUnmoveUnbanPcmkExpiredNotSupported

    @property
    def message(self) -> str:
        return "--expired not supported, please upgrade pacemaker"


class CannotUnmoveUnbanResourceMasterResourceNotPromotable(
    CliReportMessageCustom
):
    _obj: messages.CannotUnmoveUnbanResourceMasterResourceNotPromotable

    @property
    def message(self) -> str:
        return _resource_move_ban_clear_master_resource_not_promotable(
            self._obj.promotable_id
        )


class InvalidCibContent(CliReportMessageCustom):
    _obj: messages.InvalidCibContent

    @property
    def message(self) -> str:
        return "invalid cib:\n{report}{more_verbose}".format(
            report=self._obj.report,
            more_verbose=format_optional(
                self._obj.can_be_more_verbose,
                "\n\nUse --full for more details.",
            ),
        )


class NodeCommunicationErrorNotAuthorized(CliReportMessageCustom):
    _obj: messages.NodeCommunicationErrorNotAuthorized

    @property
    def message(self) -> str:
        return (
            f"Unable to authenticate to {self._obj.node} ({self._obj.reason})"
            f", try running 'pcs host auth {self._obj.node}'"
        )


class NodeCommunicationErrorTimedOut(CliReportMessageCustom):
    _obj: messages.NodeCommunicationErrorTimedOut

    @property
    def message(self) -> str:
        return (
            f"{self._obj.node}: Connection timeout, check if pcsd is running "
            "there or try setting higher timeout with --request-timeout option "
            f"({self._obj.reason})"
        )


class CannotBanResourceMasterResourceNotPromotable(CliReportMessageCustom):
    _obj: messages.CannotBanResourceMasterResourceNotPromotable

    @property
    def message(self) -> str:
        return _resource_move_ban_clear_master_resource_not_promotable(
            self._obj.promotable_id
        )


class CannotMoveResourceMasterResourceNotPromotable(CliReportMessageCustom):
    _obj: messages.CannotMoveResourceMasterResourceNotPromotable

    @property
    def message(self) -> str:
        return _resource_move_ban_clear_master_resource_not_promotable(
            self._obj.promotable_id
        )


class CannotMoveResourceNotRunning(CliReportMessageCustom):
    _obj: messages.CannotMoveResourceNotRunning

    @property
    def message(self) -> str:
        return (
            f"{self._obj.message}, use 'pcs resource move-with-constraint' or "
            "'pcs constraint location' commands instead"
        )


class SbdWatchdogTestMultipleDevices(CliReportMessageCustom):
    _obj: messages.SbdWatchdogTestMultipleDevices

    @property
    def message(self) -> str:
        return (
            "Multiple watchdog devices available, therefore, watchdog which "
            "should be tested has to be specified. To list available watchdog "
            "devices use command 'pcs stonith sbd watchdog list'"
        )


class NodeUsedAsTieBreaker(CliReportMessageCustom):
    _obj: messages.NodeUsedAsTieBreaker

    @property
    def message(self) -> str:
        return (
            self._obj.message + ", run 'pcs quorum device update model "
            "tie_breaker=<node id>' to change it"
        )


class NodesToRemoveUnreachable(CliReportMessageCustom):
    _obj: messages.NodesToRemoveUnreachable

    @property
    def message(self) -> str:
        return (
            "Removed {node} {nodes} could not be reached and subsequently "
            "deconfigured. Run 'pcs cluster destroy' on the unreachable "
            "{node}."
        ).format(
            node=format_plural(self._obj.node_list, "node"),
            nodes=format_list(self._obj.node_list),
        )


class UnableToConnectToAllRemainingNodes(CliReportMessageCustom):
    _obj: messages.UnableToConnectToAllRemainingNodes

    @property
    def message(self) -> str:
        pluralize = partial(format_plural, self._obj.node_list)
        return (
            "Remaining cluster {node} {nodes} could not be reached, run "
            "'pcs cluster sync' on any currently online node once the "
            "unreachable {one} become available"
        ).format(
            node=pluralize("node"),
            nodes=format_list(self._obj.node_list),
            one=pluralize("one"),
        )


class CannotRemoveAllClusterNodes(CliReportMessageCustom):
    _obj: messages.CannotRemoveAllClusterNodes

    @property
    def message(self) -> str:
        return (
            "No nodes would be left in the cluster, if you intend to destroy "
            "the whole cluster, run 'pcs cluster destroy --all' instead"
        )


class WaitForNodeStartupWithoutStart(CliReportMessageCustom):
    _obj: messages.WaitForNodeStartupWithoutStart

    @property
    def message(self) -> str:
        return "Cannot specify '--wait' without specifying '--start'"


class HostNotFound(CliReportMessageCustom):
    _obj: messages.HostNotFound

    @property
    def message(self) -> str:
        pluralize = partial(format_plural, self._obj.host_list)
        return (
            (
                "{host} {hosts_comma} {_is} not known to pcs, try to "
                "authenticate the {host} using 'pcs host auth {hosts_space}' "
                "command"
            )
            .format(
                host=pluralize("host"),
                hosts_comma=format_list(self._obj.host_list),
                _is=pluralize("is"),
                hosts_space=" ".join(sorted(self._obj.host_list)),
            )
            .capitalize()
        )


class UseCommandNodeRemoveRemote(CliReportMessageCustom):
    _obj: messages.UseCommandNodeRemoveRemote

    @property
    def message(self) -> str:
        return self._obj.message + ", use 'pcs cluster node remove-remote'"


class UseCommandNodeRemoveGuest(CliReportMessageCustom):
    _obj: messages.UseCommandNodeRemoveGuest

    @property
    def message(self) -> str:
        return self._obj.message + ", use 'pcs cluster node remove-guest'"


class UseCommandNodeAddGuest(CliReportMessageCustom):
    _obj: messages.UseCommandNodeAddGuest

    @property
    def message(self) -> str:
        return (
            "this command is not sufficient for creating a guest node, use"
            " 'pcs cluster node add-guest'"
        )


class UseCommandNodeAddRemote(CliReportMessageCustom):
    _obj: messages.UseCommandNodeAddRemote

    @property
    def message(self) -> str:
        return (
            "this command is not sufficient for creating a remote connection,"
            " use 'pcs cluster node add-remote'"
        )


class UseCommandRemoveAndAddGuestNode(CliReportMessageCustom):
    _obj: messages.UseCommandRemoveAndAddGuestNode

    @property
    def message(self) -> str:
        return (
            "Changing connection parameters of an existing guest node is not "
            "sufficient for connecting to a different guest node, remove the "
            "existing guest node with 'pcs cluster node remove-guest' and add "
            "a new one with 'pcs cluster node add-guest'"
        )


class CorosyncNodeConflictCheckSkipped(CliReportMessageCustom):
    _obj: messages.CorosyncNodeConflictCheckSkipped

    @property
    def message(self) -> str:
        return (
            "Unable to check if there is a conflict with nodes set in corosync "
            "because {reason}"
        ).format(reason=_skip_reason_to_string(self._obj.reason_type))


class CorosyncNotRunningCheckFinishedRunning(CliReportMessageCustom):
    _obj: messages.CorosyncNotRunningCheckFinishedRunning

    @property
    def message(self) -> str:
        return self._obj.message + (
            """ Run "pcs cluster stop {node_list}" to stop the {node} or """
            """"pcs cluster stop --all" to stop the whole cluster."""
        ).format(
            node=format_plural(self._obj.node_list, "node"),
            node_list=format_list(self._obj.node_list, separator=" "),
        )


class CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning(
    CliReportMessageCustom
):
    _obj: messages.CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning

    @property
    def message(self) -> str:
        return self._obj.message + (
            " Use commands 'pcs cluster stop --all', 'pcs quorum update "
            "auto_tie_breaker=1', 'pcs cluster start --all'."
        )


class LiveEnvironmentNotConsistent(CliReportMessageCustom):
    _obj: messages.LiveEnvironmentNotConsistent

    @property
    def message(self) -> str:
        return (
            "When {given} {_is} specified, {missing} must be specified as well"
        ).format(
            given=format_list(
                transform(
                    self._obj.mocked_files, _file_role_to_option_translation
                )
            ),
            _is=format_plural(self._obj.mocked_files, "is"),
            missing=format_list(
                transform(
                    self._obj.required_files, _file_role_to_option_translation
                )
            ),
        )


class LiveEnvironmentRequired(CliReportMessageCustom):
    _obj: messages.LiveEnvironmentRequired

    @property
    def message(self) -> str:
        return "This command does not support {forbidden_options}".format(
            forbidden_options=format_list(
                transform(
                    self._obj.forbidden_options,
                    _file_role_to_option_translation,
                )
            ),
        )


class LiveEnvironmentRequiredForLocalNode(CliReportMessageCustom):
    _obj: messages.LiveEnvironmentRequiredForLocalNode

    @property
    def message(self) -> str:
        return "Node(s) must be specified if -f is used"


class ServiceCommandsOnNodesSkipped(CliReportMessageCustom):
    _obj: messages.ServiceCommandsOnNodesSkipped

    @property
    def message(self) -> str:
        return (
            "Running action(s) {actions} on {nodes} was skipped because "
            "{reason}. Please, run the action(s) manually."
        ).format(
            actions=format_list(self._obj.action_list),
            nodes=format_list(self._obj.node_list),
            reason=_skip_reason_to_string(self._obj.reason_type),
        )


class FilesRemoveFromNodesSkipped(CliReportMessageCustom):
    _obj: messages.FilesRemoveFromNodesSkipped

    @property
    def message(self) -> str:
        return (
            "Removing {files} from {nodes} was skipped because {reason}. "
            "Please, remove the file(s) manually."
        ).format(
            files=format_list(self._obj.file_list),
            nodes=format_list(self._obj.node_list),
            reason=_skip_reason_to_string(self._obj.reason_type),
        )


class FilesDistributionSkipped(CliReportMessageCustom):
    _obj: messages.FilesDistributionSkipped

    @property
    def message(self) -> str:
        return (
            "Distribution of {files} to {nodes} was skipped because "
            "{reason}. Please, distribute the file(s) manually."
        ).format(
            files=format_list(self._obj.file_list),
            nodes=format_list(self._obj.node_list),
            reason=_skip_reason_to_string(self._obj.reason_type),
        )


class WaitForIdleNotLiveCluster(CliReportMessageCustom):
    _obj: messages.WaitForIdleNotLiveCluster

    @property
    def message(self) -> str:
        return "Cannot use '-f' together with '--wait'"


class TagCannotRemoveReferencesWithoutRemovingTag(CliReportMessageCustom):
    _obj: messages.TagCannotRemoveReferencesWithoutRemovingTag

    @property
    def message(self) -> str:
        tag_id = self._obj.tag_id
        return (
            f"There would be no references left in the tag '{tag_id}', please "
            f"remove the whole tag using the 'pcs tag remove {tag_id}' command"
        )


class RuleExpressionParseError(CliReportMessageCustom):
    _obj: messages.RuleExpressionParseError

    @property
    def message(self) -> str:
        # Messages coming from the parser are not very useful and readable,
        # they mostly contain one line grammar expression covering the whole
        # rule. No user would be able to parse that. Therefore we omit the
        # messages.
        marker = "-" * (self._obj.column_number - 1) + "^"
        return (
            f"'{self._obj.rule_string}' is not a valid rule expression, parse "
            f"error near or after line {self._obj.line_number} column "
            f"{self._obj.column_number}\n"
            f"  {self._obj.rule_line}\n"
            f"  {marker}"
        )


class CibNvsetAmbiguousProvideNvsetId(CliReportMessageCustom):
    _obj: messages.CibNvsetAmbiguousProvideNvsetId

    @property
    def message(self) -> str:
        command_map = {
            const.PCS_COMMAND_RESOURCE_DEFAULTS_UPDATE: (
                "pcs resource defaults set update"
            ),
            const.PCS_COMMAND_OPERATION_DEFAULTS_UPDATE: (
                "pcs resource op defaults set update"
            ),
        }
        command = command_map.get(self._obj.pcs_command, "")
        return (
            f"Several options sets exist, please use the '{command}' command "
            "and specify an option set ID"
        )


class UnableToGetAgentMetadata(CliReportMessageCustom):
    _obj: messages.UnableToGetAgentMetadata

    @property
    def message(self) -> str:
        reason = ", ".join(self._obj.reason.splitlines())
        return (
            f"Agent '{self._obj.agent}' is not installed or does not provide "
            f"valid metadata: {reason}"
        )


class HostAlreadyInClusterConfig(CliReportMessageCustom):
    _obj: messages.HostAlreadyInClusterConfig

    @property
    def message(self) -> str:
        return (
            f"{self._obj.host_name}: The host seems to be in a cluster already "
            "as cluster configuration files have been found on the host. If "
            "the host is not part of a cluster, run 'pcs cluster destroy' on "
            f"host '{self._obj.host_name}' to remove those configuration files"
        )


class CannotLeaveGroupEmptyAfterMove(CliReportMessageCustom):
    _obj: messages.CannotLeaveGroupEmptyAfterMove

    @property
    def message(self) -> str:
        return (
            f"{self._obj.message} Please, use the 'pcs resource "
            f"ungroup {self._obj.group_id}' command first."
        )


class StonithRestartlessUpdateUnableToPerform(CliReportMessageCustom):
    _obj: messages.StonithRestartlessUpdateUnableToPerform

    @property
    def message(self) -> str:
        msg = self._obj.message
        if (
            self._obj.reason_type
            == const.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_NOT_RUNNING
        ):
            msg += ", please use command 'pcs stonith update' instead"
        return msg


class InvalidResourceAgentName(CliReportMessageCustom):
    _obj: messages.InvalidResourceAgentName

    @property
    def message(self) -> str:
        return (
            f"{self._obj.message} List of standards and providers can be "
            "obtained by using commands 'pcs resource standards' and "
            "'pcs resource providers'."
        )


class InvalidStonithAgentName(CliReportMessageCustom):
    _obj: messages.InvalidStonithAgentName

    @property
    def message(self) -> str:
        return (
            f"{self._obj.message} List of agents can be obtained by using "
            "command 'pcs stonith list'."
        )


class ResourceStonithCommandsMismatch(CliReportMessageCustom):
    _obj: messages.ResourceStonithCommandsMismatch

    @property
    def message(self) -> str:
        cmd = (
            {const.PCS_COMMAND_STONITH_CREATE: "pcs stonith create"}.get(
                self._obj.command_to_use_instead
            )
            if self._obj.command_to_use_instead
            else None
        )
        additional_msg = format_optional(cmd, " Use '{}' command instead.")
        return f"{self._obj.message}{additional_msg}"


class AgentSelfValidationResult(CliReportMessageCustom):
    _obj: messages.AgentSelfValidationResult
    _base_msg = "Validation result from agent"

    @property
    def _formatted_result(self) -> str:
        return "\n".join(indent(self._obj.result.splitlines()))

    @property
    def message(self) -> str:
        return f"{self._base_msg}:\n{self._formatted_result}"

    def get_message_with_force_text(
        self, force_code: Optional[types.ForceCode]
    ) -> str:
        force_text = (
            " (use --force to override)" if force_code == codes.FORCE else ""
        )
        return f"{self._base_msg}{force_text}:\n{self._formatted_result}"


class BoothAuthfileNotUsed(CliReportMessageCustom):
    _obj: messages.BoothAuthfileNotUsed

    @property
    def message(self) -> str:
        return (
            f"{self._obj.message}. Run 'pcs booth enable-authfile --name "
            f"{self._obj.instance}' to enable usage of authfile."
        )


class BoothUnsupportedOptionEnableAuthfile(CliReportMessageCustom):
    _obj: messages.BoothUnsupportedOptionEnableAuthfile

    @property
    def message(self) -> str:
        return (
            f"{self._obj.message}. Run 'pcs booth clean-enable-authfile --name "
            f"{self._obj.instance}' to remove the option."
        )


class ResourceMoveAutocleanSimulationFailure(CliReportMessageCustom):
    _obj: messages.ResourceMoveAutocleanSimulationFailure

    @property
    def message(self) -> str:
        if not self._obj.move_constraint_left_in_cib:
            return self._obj.message
        node = format_optional(self._obj.node, " {}")
        return (
            f"{self._obj.message} Run 'pcs resource clear "
            f"{self._obj.resource_id}{node}' to remove the constraint."
        )


def _create_report_msg_map() -> Dict[str, type]:
    result: Dict[str, type] = {}
    for report_msg_cls in get_all_subclasses(CliReportMessageCustom):
        # pylint: disable=protected-access
        code = (
            get_type_hints(report_msg_cls)  # noqa: SLF001
            .get("_obj", item.ReportItemMessage)
            ._code
        )
        if code:
            if code in result:
                raise AssertionError()
            result[code] = report_msg_cls
    return result


REPORT_MSG_MAP = _create_report_msg_map()


def report_item_msg_from_dto(obj: dto.ReportItemMessageDto) -> CliReportMessage:
    return REPORT_MSG_MAP.get(obj.code, CliReportMessage)(obj)


_file_role_to_option_translation: Mapping[file_type_codes.FileTypeCode, str] = {
    file_type_codes.BOOTH_CONFIG: "--booth-conf",
    file_type_codes.BOOTH_KEY: "--booth-key",
    file_type_codes.CIB: "-f",
    file_type_codes.COROSYNC_CONF: "--corosync_conf",
}


def _resource_move_ban_clear_master_resource_not_promotable(
    promotable_id: str,
) -> str:
    return (
        "when specifying --promoted you must use the promotable clone id{_id}"
    ).format(
        _id=format_optional(promotable_id, " ({})"),
    )


def _skip_reason_to_string(reason: types.ReasonType) -> str:
    return {
        const.REASON_NOT_LIVE_CIB: (
            "the command does not run on a live cluster (e.g. -f was used)"
        ),
        const.REASON_UNREACHABLE: "pcs is unable to connect to the node(s)",
    }.get(reason, reason)

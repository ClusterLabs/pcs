import sys
import json
import logging

from typing import (
    Any,
    Dict,
    Mapping,
    Optional,
)

from dacite import DaciteError

from pcs import settings, utils
from pcs.cli.common.env_cli import Env
from pcs.cli.common.lib_wrapper import Library
from pcs.common import communication
from pcs.common.interface import dto
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
    ReportProcessor,
)
from pcs.common.resource_agent.dto import ResourceAgentNameDto
from pcs.lib.errors import LibraryError


SUPPORTED_COMMANDS = {
    "acl.add_permission",
    "acl.assign_role_to_group",
    "acl.assign_role_to_target",
    "acl.create_group",
    "acl.create_role",
    "acl.create_target",
    "acl.remove_group",
    "acl.remove_permission",
    "acl.remove_role",
    "acl.remove_target",
    "acl.unassign_role_from_group",
    "acl.unassign_role_from_target",
    "alert.add_recipient",
    "alert.create_alert",
    "alert.remove_alert",
    "alert.remove_recipient",
    "alert.update_alert",
    "alert.update_recipient",
    "cluster.add_nodes",
    "cluster.node_clear",
    "cluster.remove_nodes",
    "cluster.setup",
    "constraint_colocation.create_with_set",
    "constraint_order.create_with_set",
    "constraint_ticket.create",
    "constraint_ticket.create_with_set",
    "constraint_ticket.remove",
    "fencing_topology.add_level",
    "fencing_topology.remove_all_levels",
    "fencing_topology.remove_levels_by_params",
    "fencing_topology.verify",
    "node.maintenance_unmaintenance_all",
    "node.maintenance_unmaintenance_list",
    "node.standby_unstandby_all",
    "node.standby_unstandby_list",
    "qdevice.client_net_import_certificate",
    "qdevice.qdevice_net_sign_certificate_request",
    "resource_agent.describe_agent",
    "resource_agent.get_agents_list",
    "resource_agent.get_agent_metadata",
    "resource_agent.list_agents",
    "resource_agent.list_agents_for_standard_and_provider",
    "resource_agent.list_ocf_providers",
    "resource_agent.list_standards",
    "resource.ban",
    "resource.create",
    "resource.create_as_clone",
    "resource.create_in_group",
    "resource.disable",
    "resource.disable_safe",
    "resource.disable_simulate",
    "resource.enable",
    "resource.group_add",
    "resource.manage",
    "resource.move",
    "resource.move_autoclean",
    "resource.unmanage",
    "resource.unmove_unban",
    "sbd.disable_sbd",
    "sbd.enable_sbd",
    "services.disable_service",
    "services.enable_service",
    "services.get_services_info",
    "services.start_service",
    "services.stop_service",
    "scsi.unfence_node",
    "status.full_cluster_status_plaintext",
    "stonith_agent.describe_agent",
    "stonith_agent.list_agents",
    "stonith.create",
    "stonith.create_in_group",
}


def _convert_input_data(cmd: str, data: Dict[str, Any]) -> Mapping[str, Any]:
    if cmd == "resource_agent.get_agent_metadata":
        try:
            data["agent_name"] = dto.from_dict(
                ResourceAgentNameDto, data["agent_name"]
            )
        except (DaciteError, KeyError) as e:
            _exit(
                communication.const.COM_STATUS_INPUT_ERROR,
                status_msg=str(e),
            )
    return data


def _exit(
    status: communication.types.CommunicationResultStatus,
    status_msg: Optional[str] = None,
    report_list: Optional[ReportItemList] = None,
    data: Any = None,
) -> None:
    json.dump(
        dto.to_dict(
            communication.dto.InternalCommunicationResultDto(
                status,
                status_msg,
                [report.to_dto() for report in (report_list or [])],
                data,
            )
        ),
        sys.stdout,
    )
    sys.exit(0)


def get_cli_env(
    options: communication.dto.InternalCommunicationRequestOptionsDto,
) -> Env:
    env = Env()
    env.user, env.groups = utils.get_cib_user_groups()
    env.known_hosts_getter = utils.read_known_hosts_file
    # Debug messages always go to the processor. The parameter only affects if
    # they will be printed to stdout. We are not printing the messages. Instead
    # we get all the messages the processor got. So the value of the parameter
    # does not matter.
    env.report_processor = LibraryReportProcessor()
    env.request_timeout = (
        options.request_timeout or settings.default_request_timeout
    )
    return env


class LibraryReportProcessor(ReportProcessor):
    processed_items: ReportItemList = []

    def _do_report(self, report_item: ReportItem) -> None:
        self.processed_items.append(report_item)


def main() -> None:
    # pylint: disable=broad-except
    argv = sys.argv[1:]
    if argv:
        _exit(
            communication.const.COM_STATUS_INPUT_ERROR,
            status_msg="No arguments allowed",
        )

    utils.subprocess_setup()
    logging.basicConfig()

    try:
        input_dto = dto.from_dict(
            communication.dto.InternalCommunicationRequestDto,
            json.load(sys.stdin),
        )
        cli_env = get_cli_env(input_dto.options)
        lib = Library(cli_env, utils.get_middleware_factory())
        if input_dto.cmd not in SUPPORTED_COMMANDS:
            _exit(
                communication.const.COM_STATUS_UNKNOWN_CMD,
                status_msg=f"Unknown command '{input_dto.cmd}'",
            )
        for sub_cmd in input_dto.cmd.split("."):
            lib = getattr(lib, sub_cmd)
        output_data = lib(**_convert_input_data(input_dto.cmd, input_dto.cmd_data))  # type: ignore
        _exit(
            communication.const.COM_STATUS_SUCCESS,
            report_list=cli_env.report_processor.processed_items,
            data=(
                dto.to_dict(output_data)
                if isinstance(output_data, dto.DataTransferObject)
                else output_data
            ),
        )
    except LibraryError as e:
        _exit(
            communication.const.COM_STATUS_ERROR,
            report_list=(
                cli_env.report_processor.processed_items + list(e.args)
            ),
            data=e.output,
        )
    except json.JSONDecodeError as e:
        _exit(
            communication.const.COM_STATUS_INPUT_ERROR,
            status_msg=f"Unable to parse input data: {e.msg}",
        )
    except DaciteError as e:
        _exit(
            communication.const.COM_STATUS_INPUT_ERROR,
            status_msg=str(e),
        )
    except Exception as e:
        # TODO: maybe add traceback?
        _exit(communication.const.COM_STATUS_EXCEPTION, status_msg=str(e))

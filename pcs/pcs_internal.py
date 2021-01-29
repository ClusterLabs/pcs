import sys
import json
import logging

from pcs import settings, utils
from pcs.cli.common.env_cli import Env
from pcs.cli.common.lib_wrapper import Library
from pcs.common.interface import dto
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
    ReportProcessor,
)
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
    "resource.unmanage",
    "resource.unmove_unban",
    "sbd.disable_sbd",
    "sbd.enable_sbd",
    "status.full_cluster_status_plaintext",
    "stonith_agent.describe_agent",
    "stonith_agent.list_agents",
    "stonith.create",
    "stonith.create_in_group",
}


def _exit(status, status_msg=None, report_list=None, data=None):
    json.dump(
        dict(
            status=status,
            status_msg=status_msg,
            report_list=report_list or [],
            data=data,
        ),
        sys.stdout,
    )
    sys.exit(0)


def get_cli_env(options):
    env = Env()
    env.user, env.groups = utils.get_cib_user_groups()
    env.known_hosts_getter = utils.read_known_hosts_file
    # Debug messages always go to the processor. The parameter only affects if
    # they will be printed to stdout. We are not printing the messages. Instead
    # we get all the messages the processor got. So the value of the parameter
    # does not matter.
    env.report_processor = LibraryReportProcessor()
    env.request_timeout = (
        options.get("request_timeout") or settings.default_request_timeout
    )
    return env


class LibraryReportProcessor(ReportProcessor):
    processed_items: ReportItemList = []

    def _do_report(self, report_item: ReportItem) -> None:
        self.processed_items.append(report_item)


def export_reports(report_list):
    return [report_item_to_dict(report) for report in report_list]


def report_item_to_dict(report_item: ReportItem) -> dto.DtoPayload:
    return dto.to_dict(report_item.to_dto())


def main():
    # pylint: disable=broad-except
    argv = sys.argv[1:]
    if argv:
        _exit("input_error", status_msg="No arguments allowed")

    utils.subprocess_setup()
    logging.basicConfig()

    try:
        input_data = json.load(sys.stdin)
        cli_env = get_cli_env(input_data.get("options", {}))
        lib = Library(cli_env, utils.get_middleware_factory())
        cmd = input_data["cmd"]
        if cmd not in SUPPORTED_COMMANDS:
            _exit("unknown_cmd", status_msg=f"Unknown command '{cmd}'")
        for sub_cmd in cmd.split("."):
            lib = getattr(lib, sub_cmd)
        output_data = lib(**input_data["cmd_data"])
        _exit(
            "success",
            report_list=export_reports(
                cli_env.report_processor.processed_items
            ),
            data=(
                dto.to_dict(output_data)
                if isinstance(output_data, dto.DataTransferObject)
                else output_data
            ),
        )
    except LibraryError as e:
        _exit(
            "error",
            report_list=export_reports(
                cli_env.report_processor.processed_items + list(e.args)
            ),
        )
    except json.JSONDecodeError as e:
        _exit("input_error", status_msg=f"Unable to parse input data: {e.msg}")
    except KeyError as e:
        _exit("input_error", status_msg=f"Missing key {e}")
    except Exception as e:
        # TODO: maybe add traceback?
        _exit("exception", status_msg=str(e))

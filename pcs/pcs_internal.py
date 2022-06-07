import json
import logging
import sys
from typing import (
    Any,
    Optional,
)

from dacite import DaciteError

from pcs import (
    settings,
    utils,
)
from pcs.cli.common.env_cli import Env
from pcs.cli.common.lib_wrapper import Library
from pcs.common import communication
from pcs.common.interface import dto
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
    ReportProcessor,
)
from pcs.lib.errors import LibraryError

SUPPORTED_COMMANDS = {
    "services.disable_service",
    "services.enable_service",
    "services.get_services_info",
    "services.start_service",
    "services.stop_service",
}


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
        output_data = lib(**input_dto.cmd_data)  # type: ignore
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

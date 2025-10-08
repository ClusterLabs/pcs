import contextlib
import os
from typing import Any, Optional, cast

from pcs import (
    settings,
    utils,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import Argv, InputModifiers
from pcs.cli.file import metadata as cli_metadata
from pcs.cli.reports.output import error
from pcs.cli.reports.processor import ReportProcessorToConsole
from pcs.common.auth import HostAuthData
from pcs.common.communication.logger import CommunicatorLogger
from pcs.common.file import RawFile, RawFileError
from pcs.common.file_type_codes import PCS_KNOWN_HOSTS
from pcs.common.host import Destination, PcsKnownHost
from pcs.common.node_communicator import Communicator, NodeCommunicatorFactory
from pcs.common.reports.processor import ReportProcessorToLog
from pcs.common.tools import format_os_error
from pcs.common.validate import is_port_number
from pcs.daemon import log
from pcs.lib.communication.nodes import Auth
from pcs.lib.communication.tools import run
from pcs.lib.file import toolbox
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.host.config.facade import Facade
from pcs.lib.interface.config import ParserErrorException


def local_auth_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -u - username
      * -p - password
      * --request-timeout - timeout for HTTP requests
    """
    if os.geteuid() == 0:
        raise error("This command cannot be run as superuser")

    del lib
    modifiers.ensure_only_supported("-u", "-p", "--request-timeout")
    if len(argv) > 1:
        raise CmdLineInputError()
    port = argv[0] if argv else settings.pcsd_default_port
    if not is_port_number(str(port)):
        raise CmdLineInputError()

    username, password = utils.get_user_and_pass()
    LOCALHOST = "localhost"

    report_processor = ReportProcessorToConsole(bool(modifiers.get("--debug")))
    node_communicator = _get_node_communicator(
        # we know that --request-timeout value is either not defined, or it is
        # a valid number, since it is validated in app.py, so this is safe
        int(modifiers.get("--request-timeout") or 0)
        if modifiers.is_specified("--request-timeout")
        else None
    )

    com_cmd = Auth(
        {
            LOCALHOST: HostAuthData(
                username=username,
                password=password,
                dest_list=[Destination(LOCALHOST, int(port))],
            )
        },
        report_processor,
    )
    received_tokens: dict[str, str] = run(node_communicator, com_cmd)  # type: ignore[no-untyped-call]
    if LOCALHOST not in received_tokens:
        # errors have already been reported by the communication command
        raise SystemExit(1)

    new_known_hosts = [
        PcsKnownHost(
            name=LOCALHOST,
            token=received_tokens[LOCALHOST],
            dest_list=[Destination(LOCALHOST, int(port))],
        )
    ]

    file_instance = FileInstance(
        RawFile(cli_metadata.for_file_type(PCS_KNOWN_HOSTS)),  # type: ignore[no-untyped-call]
        toolbox.for_file_type(PCS_KNOWN_HOSTS),
    )
    try:
        if not file_instance.raw_file.exists():
            known_hosts_facade = Facade.create()
        else:
            known_hosts_facade = cast(Facade, file_instance.read_to_facade())
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    except ParserErrorException as e:
        report_processor.report_list(
            file_instance.parser_exception_to_report_list(e)
        )
    if report_processor.has_errors:
        raise SystemExit(1)

    known_hosts_facade.update_known_hosts(new_known_hosts)

    # create the .pcs folder in home
    try:
        path = os.path.expanduser("~/.pcs")
        with contextlib.suppress(FileExistsError):
            # its not an error if the folder already exists
            os.mkdir(path, 0o700)
        # documentation states that "mode" in os.mkdir is ignored on some
        # platforms and chmod should be used
        os.chmod(path, 0o700)
    except OSError as e:
        raise error(format_os_error(e)) from e

    try:
        file_instance.write_facade(known_hosts_facade, can_overwrite=True)
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    if report_processor.has_errors:
        raise SystemExit(1)


# used to simplify testing
def _get_node_communicator(timeout: Optional[int]) -> Communicator:
    log_report_processor = ReportProcessorToLog(log.pcsd)
    return NodeCommunicatorFactory(
        CommunicatorLogger([log_report_processor]),
        user=None,
        groups=None,
        request_timeout=timeout,
    ).get_communicator()

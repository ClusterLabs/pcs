from typing import (
    TYPE_CHECKING,
    Optional,
)

from pcs import settings
from pcs.common import reports
from pcs.common.file import RawFileError
from pcs.common.str_tools import join_multilines
from pcs.lib.booth.constants import AUTHFILE_FIX_OPTION
from pcs.lib.booth.env import BoothEnv
from pcs.lib.errors import LibraryError
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.interface.config import ParserErrorException

if TYPE_CHECKING:
    from pcs.lib.booth.config_facade import ConfigFacade


def get_daemon_status(runner, name=None):
    cmd = [settings.booth_exec, "status"]
    if name:
        cmd += ["-c", name]
    stdout, stderr, return_value = runner.run(cmd)
    # 7 means that there is no booth instance running
    if return_value not in [0, 7]:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.BoothDaemonStatusError(
                    join_multilines([stderr, stdout])
                )
            )
        )
    return stdout


def get_tickets_status(runner, name=None):
    cmd = [settings.booth_exec, "list"]
    if name:
        cmd += ["-c", name]
    stdout, stderr, return_value = runner.run(cmd)
    if return_value != 0:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.BoothTicketStatusError(
                    join_multilines([stderr, stdout]),
                )
            )
        )
    return stdout


def get_peers_status(runner, name=None):
    cmd = [settings.booth_exec, "peers"]
    if name:
        cmd += ["-c", name]
    stdout, stderr, return_value = runner.run(cmd)
    if return_value != 0:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.BoothPeersStatusError(
                    join_multilines([stderr, stdout]),
                )
            )
        )
    return stdout


def check_authfile_misconfiguration(
    env: BoothEnv, report_processor: reports.ReportProcessor
) -> Optional[reports.item.ReportItemMessage]:
    if (
        not settings.booth_enable_authfile_set_enabled
        and not settings.booth_enable_authfile_unset_enabled
    ):
        return None
    if not env.config.raw_file.exists():
        return None
    try:
        facade: ConfigFacade = env.config.read_to_facade()
        if (
            settings.booth_enable_authfile_set_enabled
            and facade.get_authfile()
            and (facade.get_option(AUTHFILE_FIX_OPTION) or "0").lower()
            not in ("1", "yes", "on")
        ):
            return reports.messages.BoothAuthfileNotUsed(env.instance_name)
        if (
            settings.booth_enable_authfile_unset_enabled
            and not settings.booth_enable_authfile_set_enabled
            and facade.get_option(AUTHFILE_FIX_OPTION) is not None
        ):
            return reports.messages.BoothUnsupportedOptionEnableAuthfile(
                env.instance_name
            )
    except RawFileError as e:
        report_processor.report(
            raw_file_error_report(e, is_forced_or_warning=True)
        )
    except ParserErrorException as e:
        report_processor.report_list(
            env.config.parser_exception_to_report_list(
                e, is_forced_or_warning=True
            )
        )
    return None

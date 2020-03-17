import base64

from pcs.common import reports
from pcs.common.file import RawFileError
from pcs.common.reports import codes as report_codes
from pcs.common.reports.item import ReportItem
from pcs.lib.booth import config_files
from pcs.lib.communication.booth import BoothSaveFiles
from pcs.lib.communication.tools import run
from pcs.lib.errors import LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.interface.config import ParserErrorException

def send_all_config_to_node(
    communicator,
    reporter,
    target_list,
    rewrite_existing=False,
    skip_wrong_config=False
):
    """
    Send all booth configs from default booth config directory and theri
    authfiles to specified node.

    communicator -- NodeCommunicator
    reporter -- report processor
    target_list list -- list of targets to which configs should be delivered
    rewrite_existing -- if True rewrite existing file
    skip_wrong_config -- if True skip local configs that are unreadable
    """
    # TODO adapt to new file transfer framework once it is written
    # TODO the function is not modular enough - it raises LibraryError

    file_list = []
    for conf_file_name in sorted(config_files.get_all_configs_file_names()):
        config_file = FileInstance.for_booth_config(conf_file_name)
        try:
            booth_conf_data = config_file.raw_file.read()
            authfile_name, authfile_data, authfile_report_list = (
                config_files.get_authfile_name_and_data(
                    config_file.raw_to_facade(booth_conf_data)
                )
            )
            reporter.report_list(authfile_report_list)
            file_list.append({
                "name": conf_file_name,
                "data": booth_conf_data.decode("utf-8"),
                "is_authfile": False
            })
            if authfile_name and authfile_data:
                file_list.append({
                    "name": authfile_name,
                    "data": base64.b64encode(authfile_data).decode("utf-8"),
                    "is_authfile": True
                })
        except RawFileError as e:
            reporter.report(
                raw_file_error_report(
                    e,
                    force_code=report_codes.SKIP_UNREADABLE_CONFIG,
                    is_forced_or_warning=skip_wrong_config,
                )
            )
        except ParserErrorException as e:
            reporter.report_list(
                config_file.parser_exception_to_report_list(
                    e,
                    force_code=report_codes.SKIP_UNREADABLE_CONFIG,
                    is_forced_or_warning=skip_wrong_config,
                )
            )
    if reporter.has_errors:
        raise LibraryError()

    if not file_list:
        # no booth configs exist, nothing to be synced
        return

    reporter.report(
        ReportItem.info(reports.messages.BoothConfigDistributionStarted())
    )
    com_cmd = BoothSaveFiles(
        reporter, file_list, rewrite_existing=rewrite_existing
    )
    com_cmd.set_targets(target_list)
    run(communicator, com_cmd)

    if reporter.has_errors:
        raise LibraryError()

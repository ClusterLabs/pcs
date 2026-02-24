from typing import cast

from pcs.common import reports
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import RawFileError, raw_file_error_report
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.permissions.config.facade import FacadeV2 as PcsSettingsFacade

from .const import DEFAULT_PERMISSIONS


def read_pcs_settings_conf() -> tuple[
    PcsSettingsFacade, reports.ReportItemList
]:
    file_instance = FileInstance.for_pcs_settings_config()
    report_list: reports.ReportItemList = []

    default_empty_file = PcsSettingsFacade.create(
        # reasonable default if file doesn't exist
        # set default permissions for backwards compatibility (there is no way
        # to differentiante between an old cluster without config and a new
        # cluster without config)
        data_version=0,
        permissions=DEFAULT_PERMISSIONS,
    )
    if not file_instance.raw_file.exists():
        return default_empty_file, report_list

    try:
        return cast(
            PcsSettingsFacade, file_instance.read_to_facade()
        ), report_list
    except RawFileError as e:
        report_list.append(raw_file_error_report(e))
    except ParserErrorException as e:
        report_list.extend(file_instance.parser_exception_to_report_list(e))
    return default_empty_file, report_list

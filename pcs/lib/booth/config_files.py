import os

from pcs import settings
from pcs.common import file_type_codes
from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.file.instance import FileInstance


def get_all_configs_file_names():
    """
    Get a list of all files ending with '.conf' from booth configuration dir.
    """
    if not os.path.isdir(settings.booth_config_dir):
        return []
    return [
        file_name
        for file_name in os.listdir(settings.booth_config_dir)
        if file_name.endswith(".conf")
        and len(file_name) > len(".conf")
        and os.path.isfile(os.path.join(settings.booth_config_dir, file_name))
    ]


def get_authfile_name_and_data(booth_conf_facade):
    """
    Get booth auth filename, content and reports based on booth config facade

    pcs.lib.booth.config_facade.ConfigFacade booth_conf_facade -- booth config
    """
    authfile_name = None
    authfile_data = None
    report_list = []

    authfile_path = booth_conf_facade.get_authfile()
    if authfile_path:
        authfile_dir, authfile_name = os.path.split(authfile_path)
        if (authfile_dir == settings.booth_config_dir) and authfile_name:
            authfile_data = FileInstance.for_booth_key(authfile_name).read_raw()
        else:
            authfile_name = None
            report_list.append(
                ReportItem.warning(
                    reports.messages.BoothUnsupportedFileLocation(
                        authfile_path,
                        settings.booth_config_dir,
                        file_type_codes.BOOTH_KEY,
                    )
                )
            )

    return authfile_name, authfile_data, report_list

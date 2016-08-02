from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import binascii

from pcs.common import report_codes
from pcs.lib import reports as lib_reports
from pcs.lib.booth import reports, config_structure
from pcs.lib.errors import ReportItemSeverity
from pcs.settings import booth_config_dir as BOOTH_CONFIG_DIR


def generate_key():
    return binascii.hexlify(os.urandom(32))

def get_all_configs():
    """
    Returns list of all file names (without suffix) ending with '.conf' in
    booth configuration directory.
    """
    return [
        file for file in os.listdir(BOOTH_CONFIG_DIR) if file.endswith(".conf")
    ]


def _read_config(file_name):
    """
    Read specified booth config from default booth config directory.

    file_name -- string, name of file
    """
    with open(os.path.join(BOOTH_CONFIG_DIR, file_name), "r") as file:
        return file.read()


def read_configs(reporter, skip_wrong_config=False):
    """
    Returns content of all configs present on local system in dictionary,
    where key is name of config and value is its content.

    reporter -- report processor
    skip_wrong_config -- if True skip local configs that are unreadable
    """
    report_list = []
    output = {}
    for file_name in get_all_configs():
        try:
            output[file_name] = _read_config(file_name)
        except EnvironmentError:
            report_list.append(reports.booth_config_unable_to_read(
                file_name,
                (
                    ReportItemSeverity.WARNING if skip_wrong_config
                    else ReportItemSeverity.ERROR
                ),
                (
                    None if skip_wrong_config
                    else report_codes.SKIP_UNREADABLE_CONFIG
                )
            ))
    reporter.process_list(report_list)
    return output


def read_authfiles_from_configs(reporter, config_content_list):
    """
    Returns content of authfiles of configs specified in config_content_list in
    dictionary where key is path to authfile and value is its content as bytes

    reporter -- report processor
    config_content_list -- list of configs content
    """
    output = {}
    for config in config_content_list:
        authfile_path = config_structure.get_authfile(
            config_structure.parse(config)
        )
        if authfile_path:
            output[os.path.basename(authfile_path)] = read_authfile(
                reporter, authfile_path
            )
    return output


def read_authfile(reporter, path):
    """
    Returns content of specified authfile as bytes. None if file is not in
    default booth directory or there was some IO error.

    reporter -- report processor
    path -- path to the authfile to be read
    """
    if not path:
        return None
    if os.path.dirname(os.path.abspath(path)) != BOOTH_CONFIG_DIR:
        reporter.process(reports.booth_unsupported_file_location(path))
        return None
    try:
        with open(path, "rb") as file:
            return file.read()
    except EnvironmentError as e:
        reporter.process(lib_reports.file_io_error(
            "authfile", path, str(e), severity=ReportItemSeverity.WARNING
        ))
        return None

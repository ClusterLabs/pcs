from __future__ import (
    absolute_import,
    division,
    print_function,
)

import os
import base64

from pcs.common import report_codes
from pcs.lib import reports as lib_reports
from pcs.lib.communication.booth import BoothSaveFiles
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.errors import LibraryError, ReportItemSeverity as Severities
from pcs.lib.booth import (
    config_files as booth_conf,
    config_structure,
    config_parser,
    reports,
)


def send_all_config_to_node(
    communicator,
    reporter,
    target,
    rewrite_existing=False,
    skip_wrong_config=False
):
    """
    Send all booth configs from default booth config directory and theri
    authfiles to specified node.

    communicator -- NodeCommunicator
    reporter -- report processor
    node -- NodeAddress
    rewrite_existing -- if True rewrite existing file
    skip_wrong_config -- if True skip local configs that are unreadable
    """
    config_dict = booth_conf.read_configs(reporter, skip_wrong_config)
    if not config_dict:
        return

    reporter.process(reports.booth_config_distribution_started())

    file_list = []
    for config, config_data in sorted(config_dict.items()):
        try:
            authfile_path = config_structure.get_authfile(
                config_parser.parse(config_data)
            )
            file_list.append({
                "name": config,
                "data": config_data,
                "is_authfile": False
            })
            if authfile_path:
                content = booth_conf.read_authfile(reporter, authfile_path)
                if not content:
                    continue
                file_list.append({
                    "name": os.path.basename(authfile_path),
                    "data": base64.b64encode(content).decode("utf-8"),
                    "is_authfile": True
                })
        except LibraryError:
            reporter.process(reports.booth_skipping_config(
                config, "unable to parse config"
            ))

    com_cmd = BoothSaveFiles(
        reporter, file_list, rewrite_existing=rewrite_existing
    )
    com_cmd.set_targets([target])
    response = run_and_raise(communicator, com_cmd)[0][1]
    try:
        report_list = []
        for file in response["existing"]:
            report_list.append(lib_reports.file_already_exists(
                None,
                file,
                Severities.WARNING if rewrite_existing else Severities.ERROR,
                (
                    None if rewrite_existing
                    else report_codes.FORCE_FILE_OVERWRITE
                ),
                target.label
            ))
        for file, reason in response["failed"].items():
            report_list.append(reports.booth_config_distribution_node_error(
                target.label, reason, file
            ))
        reporter.process_list(report_list)
        reporter.process(
            reports.booth_config_accepted_by_node(target.label, response["saved"])
        )
    except (KeyError, ValueError):
        raise LibraryError(lib_reports.invalid_response_format(target.label))


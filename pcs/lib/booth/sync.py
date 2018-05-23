import os
import base64

from pcs.common.reports import SimpleReportProcessor
from pcs.lib.communication.booth import BoothSaveFiles
from pcs.lib.communication.tools import run
from pcs.lib.errors import LibraryError
from pcs.lib.booth import (
    config_files as booth_conf,
    config_structure,
    config_parser,
    reports,
)

# TODO: fix tests
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
    _reporter = SimpleReportProcessor(reporter)
    config_dict = booth_conf.read_configs(reporter, skip_wrong_config)
    if not config_dict:
        return

    _reporter.report(reports.booth_config_distribution_started())

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
            _reporter.report(reports.booth_skipping_config(
                config, "unable to parse config"
            ))

    com_cmd = BoothSaveFiles(
        _reporter, file_list, rewrite_existing=rewrite_existing
    )
    com_cmd.set_targets(target_list)
    run(communicator, com_cmd)

    if _reporter.has_errors:
        raise LibraryError()

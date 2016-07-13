from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os

from pcs.common import env_file_role_codes
from pcs.lib.booth import reports
from pcs.lib.env_file import GhostFile, RealFile
from pcs.lib.errors import LibraryError
from pcs.settings import booth_config_dir as BOOTH_CONFIG_DIR


def get_config_file_name(name):
    report_list = []
    if "/" in name:
        report_list.append(reports.booth_invalid_name(name))
    if not os.path.exists(BOOTH_CONFIG_DIR):
        report_list.append(reports.booth_config_dir_does_not_exists(
            BOOTH_CONFIG_DIR
        ))
    if report_list:
        raise LibraryError(*report_list)
    return "{0}.conf".format(os.path.join(BOOTH_CONFIG_DIR, name))

class BoothEnv(object):
    def __init__(self, report_processor, env_data):
        self.__report_processor = report_processor
        if "config_file" in env_data:
            self.__config = GhostFile(
                file_role=env_file_role_codes.BOOTH_CONFIG,
                content=env_data["config_file"]["content"]
            )
        else:
            self.__config = RealFile(
                file_role=env_file_role_codes.BOOTH_CONFIG,
                file_path=get_config_file_name(env_data["name"]),
            )

    def get_config_content(self):
        return self.__config.read()

    def create_config(
        self, content, can_overwrite_existing=False
    ):
        self.__config.assert_no_conflict_with_existing(
            self.__report_processor,
            can_overwrite_existing
        )
        self.__config.write(content)

    def export(self):
        return {} if self.__config.is_live else {
            "config_file": self.__config.export(),
        }

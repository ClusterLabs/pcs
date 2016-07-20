from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import pwd
import grp

from pcs import settings
from pcs.common import env_file_role_codes
from pcs.lib.booth import reports
from pcs.lib.env_file import GhostFile, RealFile
from pcs.lib.errors import LibraryError
from pcs.settings import booth_config_dir as BOOTH_CONFIG_DIR


def get_booth_env_file_name(name, extension):
    report_list = []
    if "/" in name:
        report_list.append(reports.booth_invalid_name(name))
    if not os.path.exists(BOOTH_CONFIG_DIR):
        report_list.append(reports.booth_config_dir_does_not_exists(
            BOOTH_CONFIG_DIR
        ))
    if report_list:
        raise LibraryError(*report_list)
    return "{0}.{1}".format(os.path.join(BOOTH_CONFIG_DIR, name), extension)

def get_config_file_name(name):
    return get_booth_env_file_name(name, "conf")

def get_key_path(name):
    return get_booth_env_file_name(name, "key")

def set_keyfile_access(file_path):
    #shutil.chown is not in python2
    uid = pwd.getpwnam(settings.pacemaker_uname).pw_uid
    gid = grp.getgrnam(settings.pacemaker_gname).gr_gid
    os.chown(file_path, uid, gid)
    os.chmod(file_path, 0o400)

class BoothEnv(object):
    def __init__(self, report_processor, env_data):
        self.__report_processor = report_processor
        if "config_file" in env_data:
            self.__config = GhostFile(
                file_role=env_file_role_codes.BOOTH_CONFIG,
                content=env_data["config_file"]["content"]
            )
            self.__key_path = env_data["key_path"]
            self.__key = GhostFile(
                file_role=env_file_role_codes.BOOTH_KEY,
                content=env_data["key_file"]["content"]
            )
        else:
            self.__config = RealFile(
                file_role=env_file_role_codes.BOOTH_CONFIG,
                file_path=get_config_file_name(env_data["name"]),
            )
            self.__key_path = get_key_path(env_data["name"])
            self.__key = RealFile(
                file_role=env_file_role_codes.BOOTH_KEY,
                file_path=self.__key_path,
            )

    @property
    def key_path(self):
        return self.__key_path

    def get_config_content(self):
        return self.__config.read()

    def create_config(self, content, can_overwrite_existing=False):
        self.__config.assert_no_conflict_with_existing(
            self.__report_processor,
            can_overwrite_existing
        )
        self.__config.write(content)

    def create_key(self, key_content, can_overwrite_existing=False):
        self.__key.assert_no_conflict_with_existing(
            self.__report_processor,
            can_overwrite_existing
        )
        self.__key.write(key_content, set_keyfile_access)

    def push_config(self, content):
        self.__config.write(content)

    def export(self):
        return {} if self.__config.is_live else {
            "config_file": self.__config.export(),
            "key_file": self.__key.export(),
        }

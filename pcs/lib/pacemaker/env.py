from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import env_file_role_codes
from pcs.lib.env_file import GhostFile, RealFile
from pcs import settings


class PacemakerEnv(object):
    def __init__(self, report_processor, env_data, get_cib):
        """
        callable get_cib should return cib as lxml tree
        """
        self.__report_processor = report_processor
        if "authkey" in env_data:
            self.__authkey = GhostFile(
                file_role=env_file_role_codes.PACEMAKER_AUTHKEY,
                content=env_data["authkey"]["content"]
            )
        else:
            self.__authkey = RealFile(
                file_role=env_file_role_codes.PACEMAKER_AUTHKEY,
                file_path=settings.pacemaker_authkey_path,
            )
        self.get_cib = get_cib

    def export(self):
        return {} if self.__authkey.is_live else {
            "authkey": self.__authkey.export()
        }

    @property
    def has_authkey(self):
        return self.__authkey.exists

    def get_authkey_content(self):
        return self.__authkey.read()

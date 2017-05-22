from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import env_file_role_codes
from pcs.lib.env_file import RealFile
from pcs import settings


class PacemakerEnv(object):
    def __init__(self):
        """
        callable get_cib should return cib as lxml tree
        """
        self.__authkey = RealFile(
            file_role=env_file_role_codes.PACEMAKER_AUTHKEY,
            file_path=settings.pacemaker_authkey_file,
        )

    @property
    def has_authkey(self):
        return self.__authkey.exists

    def get_authkey_content(self):
        return self.__authkey.read()

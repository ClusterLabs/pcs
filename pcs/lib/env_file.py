from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path

from pcs.common import report_codes
from pcs.common.tools import format_environment_error
from pcs.lib import reports
from pcs.lib.errors import ReportItemSeverity, LibraryError, LibraryEnvError


class GhostFile(object):
    is_live = False
    def __init__(self, file_role, content=None):
        self.__file_role = file_role
        self.__content = content
        self.__no_existing_file_expected = False
        self.__can_overwrite_existing_file = False

    def read(self):
        if self.__content is None:
            raise LibraryEnvError(
                reports.file_does_not_exists(self.__file_role)
            )

        return self.__content

    def write(self, content):
        self.__content = content

    def assert_no_conflict_with_existing(
        self, report_processor, can_overwrite_existing=False
    ):
        self.__no_existing_file_expected = True
        self.__can_overwrite_existing_file = can_overwrite_existing

    def export(self):
        return {
            "content": self.__content,
            "no_existing_file_expected": self.__no_existing_file_expected,
            "can_overwrite_existing_file": self.__can_overwrite_existing_file,
        }


class RealFile(object):
    is_live = True
    def __init__(
        self, file_role, file_path,
        overwrite_code=report_codes.FORCE_FILE_OVERWRITE
    ):
        self.__file_role = file_role
        self.__file_path = file_path
        self.__overwrite_code = overwrite_code

    def assert_no_conflict_with_existing(
        self, report_processor, can_overwrite_existing=False
    ):
        if os.path.exists(self.__file_path):
            report_processor.process(reports.file_already_exists(
                self.__file_role,
                self.__file_path,
                ReportItemSeverity.WARNING if can_overwrite_existing
                    else ReportItemSeverity.ERROR,
                forceable=None if can_overwrite_existing
                    else self.__overwrite_code,
            ))

    def write(self, content):
        try:
            with open(self.__file_path, "w") as config_file:
                config_file.write(content)
        except EnvironmentError as e:
            raise self.__report_io_error(e)

    def read(self):
        try:
            with open(self.__file_path, "r") as file:
                return file.read()
        except EnvironmentError as e:
            raise self.__report_io_error(e)

    def __report_io_error(self, e):
        return LibraryError(reports.file_io_error(
            self.__file_role,
            file_path=self.__file_path,
            reason=format_environment_error(e)
        ))

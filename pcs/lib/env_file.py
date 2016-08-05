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
        self.__is_binary = False

    def read(self):
        if self.__content is None:
            raise LibraryEnvError(
                reports.file_does_not_exist(self.__file_role)
            )

        return self.__content

    def remove(self, silence_no_existence):
        raise AssertionError("Remove GhostFile is not supported.")

    def write(self, content, file_operation=None, is_binary=False):
        """
        callable file_operation is there only for RealFile compatible interface
            it has no efect
        """
        self.__is_binary = is_binary
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
            "is_binary": self.__is_binary,
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

    def write(self, content, file_operation=None, is_binary=False):
        """
        callable file_operation takes path and proces operation on it e.g. chmod
        """
        mode = "wb" if is_binary else "w"
        try:
            with open(self.__file_path, mode) as config_file:
                config_file.write(content)
            if file_operation:
                file_operation(self.__file_path)
        except EnvironmentError as e:
            raise self.__report_io_error(e, "write")

    def read(self):
        try:
            with open(self.__file_path, "r") as file:
                return file.read()
        except EnvironmentError as e:
            raise self.__report_io_error(e, "read")

    def remove(self, silence_no_existence=False):
        if os.path.exists(self.__file_path):
            try:
                os.remove(self.__file_path)
            except EnvironmentError as e:
                raise self.__report_io_error(e, "remove")
        elif not silence_no_existence:
            raise LibraryError(reports.file_io_error(
                self.__file_role,
                file_path=self.__file_path,
                operation="remove",
                reason="File does not exist"
            ))

    def __report_io_error(self, e, operation):
        return LibraryError(reports.file_io_error(
            self.__file_role,
            file_path=self.__file_path,
            operation=operation,
            reason=format_environment_error(e)
        ))

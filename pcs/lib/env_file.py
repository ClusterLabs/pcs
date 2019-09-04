import os.path

from pcs.common import report_codes
from pcs.common.tools import format_environment_error
from pcs.lib import reports
from pcs.lib.errors import ReportItemSeverity, LibraryError

def export_ghost_file(ghost_file):
    return {
        "content": ghost_file.content,
    }

# TODO drop everything bellow once not needed anymore

class RealFile:
    is_live = True
    def __init__(self, file_role, file_path, is_binary=False):
        self.__file_role = file_role
        self.__file_path = file_path
        self.__is_binary = is_binary

    def assert_no_conflict_with_existing(
        self, report_processor, can_overwrite_existing=False
    ):
        if self.exists:
            report_processor.process(reports.file_already_exists(
                self.__file_role,
                self.__file_path,
                ReportItemSeverity.WARNING if can_overwrite_existing
                    else ReportItemSeverity.ERROR,
                forceable=None if can_overwrite_existing
                    else report_codes.FORCE_FILE_OVERWRITE,
            ))

    @property
    def exists(self):
        return os.path.exists(self.__file_path)

    def write(self, content, file_operation=None):
        """
        callable file_operation takes path and proces operation on it e.g. chmod
        """
        mode = "wb" if self.__is_binary else "w"
        try:
            with open(self.__file_path, mode) as config_file:
                config_file.write(content)
            if file_operation:
                file_operation(self.__file_path)
        except EnvironmentError as e:
            raise self.__report_io_error(e, "write")

    def read(self):
        try:
            mode = "rb" if self.__is_binary else "r"
            with open(self.__file_path, mode) as file:
                return file.read()
        except EnvironmentError as e:
            raise self.__report_io_error(e, "read")

    def remove(self, silence_no_existence=False):
        if self.exists:
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

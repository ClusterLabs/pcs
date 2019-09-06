import errno
import os

from pcs.common.file import(
    RawFile,
    RawFileError,
    RawFileInterface,
)
from pcs.lib import reports

# TODO add logging (logger / debug reports ?)

def raw_file_error_report(error, force_code=None, is_forced_or_warning=False):
    """
    Translate a RawFileError instance to a report

    RawFileError error -- an exception to be translated
    string force_code -- is it a forcible error? by which code?
    bool is_forced_or_warning -- translate to a warning if True, error otherwise
    """
    return reports.get_problem_creator(force_code, is_forced_or_warning)(
        reports.file_io_error,
        error.file_type.file_type_code,
        # do not report real file path if we were working with a ghost file
        "" if isinstance(error, GhostFileError) else error.file_type.path,
        error.reason,
        error.action,
    )

def export_ghost_file(ghost_file):
    """
    Export GhostFile so it can be transfered to a client

    GhostFile ghost_file -- a ghost file instance
    """
    return {
        "content": ghost_file.content,
    }

class RealFile(RawFile):
    # TODO implement method "backup" in the parent
    # pylint: disable=abstract-method
    @property
    def is_ghost(self):
        return False


class GhostFileError(RawFileError):
    pass


class GhostFile(RawFileInterface):
    def __init__(self, file_type, file_data=None):
        """
        FileMetadata file_type -- describes the file and provides its metadata
        bytes file_data -- data of the ghost file
        """
        super().__init__(file_type)
        self.__file_data = file_data

    @property
    def is_ghost(self):
        return True

    @property
    def content(self):
        """
        Export the file content
        """
        return self.__file_data

    def exists(self):
        return self.__file_data is not None

    def read(self):
        if self.__file_data is None:
            raise GhostFileError(
                self.file_type,
                RawFileError.ACTION_READ,
                # get "no such file" message as defined and worded in the system
                os.strerror(errno.ENOENT)
            )
        return self.__file_data

    def write(self, file_data, can_overwrite=False):
        self.__file_data = file_data

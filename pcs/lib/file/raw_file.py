import errno
import os
from typing import Optional

# the import makes it look like RealFile is implemented here so we don't
# have to import RawFile from common and Ghost file from here in other
# places
# pylint: disable=unused-import
from pcs.common import reports as report
from pcs.common.file import(
    RawFile as RealFile,
    RawFileError,
    RawFileInterface,
)
from pcs.common.reports.item import ReportItem
from pcs.lib import reports

# TODO add logging (logger / debug reports ?)

def raw_file_error_report(
    error: RawFileError,
    force_code: Optional[report.types.ForceCode] = None,
    is_forced_or_warning: bool = False
) -> ReportItem:
    """
    Translate a RawFileError instance to a report

    error -- an exception to be translated
    force_code -- is it a forcible error? by which code?
    is_forced_or_warning -- translate to a warning if True, error otherwise
    """
    return ReportItem(
        severity=report.item.get_severity(force_code, is_forced_or_warning),
        message=report.messages.FileIoError(
            error.metadata.file_type_code,
            error.action,
            error.reason,
            # do not report real file path if we were working with a ghost file
            file_path=(
                "" if isinstance(error, GhostFileError) else error.metadata.path
            ),
        ),
    )

def export_ghost_file(ghost_file):
    """
    Export GhostFile so it can be transfered to a client

    GhostFile ghost_file -- a ghost file instance
    """
    return {
        "content": ghost_file.content,
    }


class GhostFileError(RawFileError):
    pass


class GhostFile(RawFileInterface):
    def __init__(self, metadata, file_data=None):
        """
        FileMetadata metadata -- describes the file and provides its metadata
        bytes file_data -- data of the ghost file
        """
        super().__init__(metadata)
        self.__file_data = file_data

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
                self.metadata,
                RawFileError.ACTION_READ,
                # get "no such file" message as defined and worded in the system
                os.strerror(errno.ENOENT)
            )
        return self.__file_data

    def write(self, file_data, can_overwrite=False):
        self.__file_data = file_data

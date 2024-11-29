import errno
import os
from contextlib import contextmanager
from io import BytesIO
from typing import (
    Dict,
    Iterator,
    Optional,
)

# the import makes it look like RealFile is implemented here so we don't
# have to import RawFile from common and Ghost file from here in other
# places
# pylint: disable=unused-import
from pcs.common import reports
from pcs.common.file import (
    FileMetadata,
    RawFileError,
    RawFileInterface,
)
from pcs.common.file import RawFile as RealFile  # noqa: F401

# TODO add logging (logger / debug reports ?)


def raw_file_error_report(
    error: RawFileError,
    force_code: Optional[reports.types.ForceCode] = None,
    is_forced_or_warning: bool = False,
) -> reports.ReportItem:
    """
    Translate a RawFileError instance to a report

    error -- an exception to be translated
    force_code -- is it a forcible error? by which code?
    is_forced_or_warning -- translate to a warning if True, error otherwise
    """
    return reports.ReportItem(
        severity=reports.get_severity(force_code, is_forced_or_warning),
        message=reports.messages.FileIoError(
            error.metadata.file_type_code,
            error.action,
            error.reason,
            # do not report real file path if we were working with a ghost file
            file_path=(
                "" if isinstance(error, GhostFileError) else error.metadata.path
            ),
        ),
    )


class GhostFileError(RawFileError):
    pass


class GhostFile(RawFileInterface):
    def __init__(
        self, metadata: FileMetadata, file_data: Optional[bytes] = None
    ):
        """
        metadata -- describes the file and provides its metadata
        file_data -- data of the ghost file
        """
        super().__init__(metadata)
        self.__file_data = file_data

    @property
    def content(self) -> Optional[bytes]:
        """
        Export the file content
        """
        return self.__file_data

    def exists(self) -> bool:
        return self.__file_data is not None

    def read(self) -> bytes:
        if self.__file_data is None:
            raise GhostFileError(
                self.metadata,
                RawFileError.ACTION_READ,
                # get "no such file" message as defined and worded in the system
                os.strerror(errno.ENOENT),
            )
        return self.__file_data

    def write(self, file_data: bytes, can_overwrite: bool = False) -> None:
        self.__file_data = file_data

    @contextmanager
    def update(self) -> Iterator[BytesIO]:
        io_buffer = BytesIO(self.read())
        io_buffer.seek(0)
        yield io_buffer
        self.write(io_buffer.getvalue(), can_overwrite=True)


def export_ghost_file(ghost_file: GhostFile) -> Dict[str, Optional[bytes]]:
    """
    Export GhostFile so it can be transferred to a client

    ghost_file -- a ghost file instance
    """
    return {
        "content": ghost_file.content,
    }

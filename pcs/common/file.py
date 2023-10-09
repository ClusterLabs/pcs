import fcntl
import os
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from typing import (
    IO,
    Any,
    ContextManager,
    Iterator,
    NewType,
    Optional,
)

from pcs.common.file_type_codes import FileTypeCode
from pcs.common.tools import format_os_error

# TODO add logging (logger / debug reports ?) to the RawFile class; be aware
# the class is used both in pcs.cli and pcs.lib packages


@dataclass(frozen=True)
class FileMetadata:
    file_type_code: FileTypeCode
    path: str
    owner_user_name: Optional[str]
    owner_group_name: Optional[str]
    permissions: Optional[int]
    is_binary: bool


FileAction = NewType("FileAction", str)


class RawFileError(Exception):
    # So far there has been no need to have a separate exception for each
    # action. Actions must be passed in a report and we certainely do not want
    # a separate report for each action.

    ACTION_CHMOD = FileAction("chmod")
    ACTION_CHOWN = FileAction("chown")
    ACTION_READ = FileAction("read")
    ACTION_REMOVE = FileAction("remove")
    ACTION_UPDATE = FileAction("update")
    ACTION_WRITE = FileAction("write")

    def __init__(
        self, metadata: FileMetadata, action: FileAction, reason: str = ""
    ):
        """
        metadata -- describes the file involved in the error
        action -- possible values enumerated in RawFileError
        reason -- plain text error details
        """
        super().__init__()
        self.metadata = metadata
        self.action = action
        self.reason = reason


class FileAlreadyExists(RawFileError):
    def __init__(self, metadata: FileMetadata):
        """
        metadata -- describes the file involved in the error
        """
        super().__init__(metadata, RawFileError.ACTION_WRITE)


class RawFileInterface:
    def __init__(self, metadata: FileMetadata):
        """
        metadata -- describes the file and provides its metadata
        """
        self.__metadata = metadata

    @property
    def metadata(self) -> FileMetadata:
        return self.__metadata

    def exists(self) -> bool:
        """
        Return True if file exists, False otherwise
        """
        raise NotImplementedError()

    def read(self) -> bytes:
        """
        Return content of the file as bytes
        """
        raise NotImplementedError()

    def write(self, file_data: bytes, can_overwrite: bool = False) -> None:
        """
        Write file_data to the file

        file_data -- data to be written
        can_overwrite -- raise if False and the file already exists
        """
        raise NotImplementedError()

    def update(self) -> ContextManager[BytesIO]:
        """
        Returns a context manager which __enter__ method returns a buffer
        filled with file data and stores data from the returned buffer to the
        same file once __exit__ method is called. Context manager holds an
        exclusive lock on the file between __enter__ and __exit__ calls.
        """
        raise NotImplementedError()


class RawFile(RawFileInterface):
    def exists(self) -> bool:
        # Returns False if the file is not accessible, does not raise.
        return os.path.exists(self.metadata.path)

    def read(self) -> bytes:
        try:
            mode = "rb" if self.metadata.is_binary else "r"
            with open(self.metadata.path, mode) as my_file:
                # the lock is released when the file gets closed on leaving the
                # with statement
                fcntl.flock(my_file.fileno(), fcntl.LOCK_SH)
                content = my_file.read()
                return (
                    content
                    if self.metadata.is_binary
                    else content.encode("utf-8")
                )
        except OSError as e:
            # Specific exception if the file does not exist is not needed,
            # anyone can and should check that using the exists method.
            raise RawFileError(
                self.metadata, RawFileError.ACTION_READ, format_os_error(e)
            ) from e

    def _chown(self) -> None:
        try:
            # Need to split to two conditions and check owner and group
            # separately due to mypy.
            if self.metadata.owner_user_name is not None:
                shutil.chown(
                    self.metadata.path,
                    user=self.metadata.owner_user_name,
                )
            if self.metadata.owner_group_name is not None:
                shutil.chown(
                    self.metadata.path,
                    group=self.metadata.owner_group_name,
                )
        except LookupError as e:
            raise RawFileError(
                self.metadata, RawFileError.ACTION_CHOWN, str(e)
            ) from e
        except OSError as e:
            raise RawFileError(
                self.metadata,
                RawFileError.ACTION_CHOWN,
                format_os_error(e),
            ) from e

    def _chmod(self, file_obj: IO[Any]) -> None:
        if self.metadata.permissions is not None:
            try:
                os.chmod(file_obj.fileno(), self.metadata.permissions)
            except OSError as e:
                raise RawFileError(
                    self.metadata,
                    RawFileError.ACTION_CHMOD,
                    format_os_error(e),
                ) from e

    def write(self, file_data: bytes, can_overwrite: bool = False) -> None:
        try:
            mode = "{write_mode}{binary_mode}".format(
                write_mode="w" if can_overwrite else "x",
                binary_mode="b" if self.metadata.is_binary else "",
            )
            with open(self.metadata.path, mode) as my_file:
                # the lock is released when the file gets closed on leaving the
                # with statement
                fcntl.flock(my_file.fileno(), fcntl.LOCK_EX)
                # Set the ownership and permissions to cover the case when we
                # just created the file. If the file already existed, make sure
                # the ownership and permissions are correct before writing any
                # data into it.
                self._chown()
                self._chmod(my_file)

                # Write file data
                my_file.write(
                    file_data
                    if self.metadata.is_binary
                    else file_data.decode("utf-8")
                )
        except FileExistsError as e:
            raise FileAlreadyExists(self.metadata) from e
        except OSError as e:
            raise RawFileError(
                self.metadata, RawFileError.ACTION_WRITE, format_os_error(e)
            ) from e

    @contextmanager
    def update(self) -> Iterator[BytesIO]:
        mode = "a+"
        if self.metadata.is_binary:
            mode += "b"
        try:
            with open(self.metadata.path, mode) as file_obj:
                # the lock is released when the file gets closed on leaving the
                # with statement
                fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX)
                file_obj.seek(0)
                content = file_obj.read()
                stream = BytesIO(
                    content
                    if self.metadata.is_binary
                    else content.encode("utf-8")
                )
                stream.seek(0)
                yield stream
                self._chown()
                self._chmod(file_obj)
                file_obj.seek(0)
                file_obj.truncate()
                new_content = stream.getvalue()
                file_obj.write(
                    new_content
                    if self.metadata.is_binary
                    else new_content.decode("utf-8")
                )

        except OSError as e:
            # Specific exception if the file does not exist is not needed,
            # anyone can and should check that using the exists method.
            raise RawFileError(
                self.metadata, RawFileError.ACTION_UPDATE, format_os_error(e)
            ) from e

    def remove(self, fail_if_file_not_found: bool = True) -> None:
        try:
            os.remove(self.metadata.path)
        except FileNotFoundError as e:
            if fail_if_file_not_found:
                raise self.__get_raw_file_error(e) from e
        except OSError as e:
            raise self.__get_raw_file_error(e) from e

    def backup(self) -> None:
        # TODO implement
        raise NotImplementedError()

    def __get_raw_file_error(self, e: OSError) -> RawFileError:
        return RawFileError(
            self.metadata, RawFileError.ACTION_REMOVE, format_os_error(e)
        )

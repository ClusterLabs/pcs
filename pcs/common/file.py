from collections import namedtuple
import fcntl
import os
import shutil

from pcs.common.tools import format_os_error

# TODO add logging (logger / debug reports ?) to the RawFile class; be aware
# the class is used both in pcs.cli and pcs.lib packages

FileMetadata = namedtuple(
    "FileMetadata",
    [
        "file_type_code",
        "path",
        "owner_user_name",
        "owner_group_name",
        "permissions",
        "is_binary",
    ]
)


class RawFileError(Exception):
    # So far there has been no need to have a separate exception for each
    # action. Actions must be passed in a report and we certainely do not want
    # a separate report for each action.
    ACTION_CHMOD = "chmod"
    ACTION_CHOWN = "chown"
    ACTION_READ = "read"
    ACTION_REMOVE = "remove"
    ACTION_WRITE = "write"

    def __init__(self, file_type, action, reason=""):
        """
        FileMetadata file_type -- describes the file involved in the error
        string action -- possible values enumerated in RawFileError
        string reason -- plain text error details
        """
        super().__init__()
        self.file_type = file_type
        self.action = action
        self.reason = reason


class FileAlreadyExists(RawFileError):
    def __init__(self, file_type):
        """
        FileMetadata file_type -- describes the file involved in the error
        """
        super().__init__(file_type, RawFileError.ACTION_WRITE)


class RawFileInterface():
    def __init__(self, file_type):
        """
        FileMetadata file_type -- describes the file and provides its metadata
        """
        self.__file_type = file_type

    @property
    def file_type(self):
        return self.__file_type

    def exists(self):
        """
        Return True if file exists, False otherwise
        """
        raise NotImplementedError()

    def read(self):
        """
        Return content of the file as bytes
        """
        raise NotImplementedError()

    def write(self, file_data, can_overwrite=False):
        """
        Write file_data to the file

        bytes file_data -- data to be written
        bool can_overwrite -- raise if False and the file already exists
        """
        raise NotImplementedError()


class RawFile(RawFileInterface):
    def exists(self):
        # Returns False if the file is not accessible, does not raise.
        return os.path.exists(self.file_type.path)

    def read(self):
        try:
            mode = "rb" if self.file_type.is_binary else "r"
            with open(self.file_type.path, mode) as my_file:
                # the lock is released when the file gets closed on leaving the
                # with statement
                fcntl.flock(my_file.fileno(), fcntl.LOCK_SH)
                content = my_file.read()
                return (
                    content if self.file_type.is_binary
                    else content.encode("utf-8")
                )
        except OSError as e:
            # Specific expection if the file does not exist is not needed,
            # anyone can and should check that using the exists method.
            raise RawFileError(
                self.file_type,
                RawFileError.ACTION_READ,
                format_os_error(e)
            )

    def write(self, file_data, can_overwrite=False):
        try:
            mode = "{write_mode}{binary_mode}".format(
                write_mode="w" if can_overwrite else "x",
                binary_mode="b" if self.file_type.is_binary else "",
            )
            # It seems pylint cannot process constructing the mode variable and
            # gives a false positive.
            # pylint: disable=bad-open-mode
            with open(self.file_type.path, mode) as my_file:
                # the lock is released when the file gets closed on leaving the
                # with statement
                fcntl.flock(my_file.fileno(), fcntl.LOCK_EX)
                # Set the ownership and permissions to cover the case when we
                # just created the file. If the file already existed, make sure
                # the ownership and permissions are correct before writing any
                # data into it.
                if (
                    self.file_type.owner_user_name is not None
                    or
                    self.file_type.owner_group_name is not None
                ):
                    try:
                        shutil.chown(
                            self.file_type.path,
                            self.file_type.owner_user_name,
                            self.file_type.owner_group_name,
                        )
                    except LookupError as e:
                        raise RawFileError(
                            self.file_type,
                            RawFileError.ACTION_CHOWN,
                            str(e)
                        )
                    except OSError as e:
                        raise RawFileError(
                            self.file_type,
                            RawFileError.ACTION_CHOWN,
                            format_os_error(e)
                        )

                if self.file_type.permissions is not None:
                    try:
                        os.chmod(my_file.fileno(), self.file_type.permissions)
                    except OSError as e:
                        raise RawFileError(
                            self.file_type,
                            RawFileError.ACTION_CHMOD,
                            format_os_error(e)
                        )
                # Write file data
                my_file.write(
                    file_data if self.file_type.is_binary
                    else file_data.decode("utf-8")
                )
        except FileExistsError as e:
            raise FileAlreadyExists(self.file_type)
        except OSError as e:
            raise RawFileError(
                self.file_type,
                RawFileError.ACTION_WRITE,
                format_os_error(e)
            )

    def remove(self, fail_if_file_not_found=True):
        get_raw_file_error = lambda e: RawFileError(
            self.file_type, RawFileError.ACTION_REMOVE, format_os_error(e)
        )
        try:
            os.remove(self.file_type.path)
        except FileNotFoundError as e:
            if fail_if_file_not_found:
                raise get_raw_file_error(e)
        except OSError as e:
            raise get_raw_file_error(e)

    def backup(self):
        # TODO implement
        raise NotImplementedError()

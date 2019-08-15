from pcs.common.file import(
    RawFile,
    RawFileError,
    RawFileInterface,
)

# TODO add logging (logger / debug reports ?)


class RealFile(RawFile):
    # TODO implement method "backup" in the parent
    # pylint: disable=abstract-method
    @property
    def is_ghost(self):
        return False


class GhostFileNotProvided(RawFileError):
    pass


class GhostFile(RawFileInterface):
    def __init__(self, file_type, file_data=None):
        super().__init__(file_type)
        self.__file_data = file_data
        self.__can_overwrite_existing_file = False

    @property
    def is_ghost(self):
        return True

    @property
    def content(self):
        return self.__file_data

    @property
    def can_overwrite_existing_file(self):
        return self.__can_overwrite_existing_file

    def exists(self):
        return self.__file_data is not None

    def read(self):
        if self.__file_data is None:
            # TODO replace by RawFileError(read, "data not provided") ???
            raise GhostFileNotProvided(self.file_type, RawFileError.ACTION_READ)
        return self.__file_data

    def write(self, file_data, can_overwrite=False):
        self.__file_data = file_data
        self.__can_overwrite_existing_file = can_overwrite

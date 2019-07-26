from pcs.common.file import(
    RawFile,
    RawFileError,
    RawFileInterface,
)

# TODO add logging (logger / debug reports ?)
# TODO implement RealFile.backup - here or in cli?


class RealFile(RawFile):
    @property
    def is_ghost(self):
        return False

    def backup(self):
        pass


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

    def export(self):
        return {
            "content": self.__file_data,
            # TODO drop from here and cli, it has never been set to False
            "no_existing_file_expected": True,
            "can_overwrite_existing_file": self.__can_overwrite_existing_file,
            "is_binary": self.file_type.is_binary,
        }

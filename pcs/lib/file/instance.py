from pcs.common import file_type_codes
from pcs.lib.file import (
    fs_metadata,
    raw_file,
    toolbox,
)

# This is a high level class to be used in lib.command. To prevent code
# duplication, it catches exceptions and handles error states from lower layers
# and raises LibraryError in such cases.
class FileInstance():
    @staticmethod
    def for_booth_config(name, ghost_file=False, ghost_data=None):
        return FileInstance._for_booth(
            file_type_codes.BOOTH_CONFIG, name, ghost_file, ghost_data
        )

    @staticmethod
    def for_booth_key(name, ghost_file=False, ghost_data=None):
        return FileInstance._for_booth(
            file_type_codes.BOOTH_KEY, name, ghost_file, ghost_data
        )

    @staticmethod
    def _for_booth(file_type_code, name, ghost_file, ghost_data):
        metadata = fs_metadata.for_file_type(file_type_code, name)
        return FileInstance(
            _get_raw_file(metadata, ghost_file, ghost_data),
            toolbox.for_file_type(file_type_code)
        )

    @staticmethod
    def for_known_hosts():
        file_type_code = file_type_codes.PCS_KNOWN_HOSTS
        return FileInstance(
            raw_file.RealFile(fs_metadata.for_file_type(file_type_code)),
            toolbox.for_file_type(file_type_code)
        )

    def __init__(self, raw_file_interface, file_toolbox):
        self._raw_file = raw_file_interface
        self._toolbox = file_toolbox

    @property
    def raw_file(self):
        return self._raw_file

    @property
    def toolbox(self):
        return self._toolbox

    def parser_exception_to_report_list(
        self, exception, force_code=None, is_forced_or_warning=False
    ):
        return self._toolbox.parser.exception_to_report_list(
            exception,
            self._raw_file.file_type.file_type_code,
            None if self._raw_file.is_ghost else self._raw_file.file_type.path,
            force_code,
            is_forced_or_warning
        )

    def read_to_facade(self):
        return self._toolbox.facade(self.read_to_structure())

    def read_to_structure(self):
        return self._toolbox.parser.parse(self.read_raw())

    def read_raw(self):
        return self._raw_file.read()

    def raw_to_facade(self, raw_file_data):
        return self._toolbox.facade(self.raw_to_structure(raw_file_data))

    def raw_to_structure(self, raw_file_data):
        return self._toolbox.parser.parse(raw_file_data)

    def write_facade(self, facade, can_overwrite=False):
        self.write_structure(facade.config, can_overwrite=can_overwrite)

    def write_structure(self, structure, can_overwrite=False):
        self.write_raw(
            self._toolbox.exporter.export(structure),
            can_overwrite=can_overwrite
        )

    def write_raw(self, raw_file_data, can_overwrite=False):
        self._raw_file.write(raw_file_data, can_overwrite=can_overwrite)

    def remove(self, fail_if_file_not_found=True):
        self._raw_file.remove(fail_if_file_not_found=fail_if_file_not_found)


def _get_raw_file(file_type, is_ghost, ghost_data):
    if not is_ghost:
        return raw_file.RealFile(file_type)
    return raw_file.GhostFile(file_type, file_data=ghost_data)

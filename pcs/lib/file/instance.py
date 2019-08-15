from pcs.common import file_type_codes
from pcs.common.file import RawFileError
from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.file import(
    fs_metadata,
    raw_file,
    toolbox,
)

# This is a high level class to be used in lib.command. To prevent code
# duplication, it catches exceptions and handles error states from lower layers
# and raises LibraryError in such cases.
class FileInstance():
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

    def read_to_structure(self):
        try:
            parser = self._toolbox.parser(
                self._raw_file.read(),
                self._raw_file.file_type.file_type_code,
                self._raw_file.file_type.path
            )
            if parser.was_error():
                raise LibraryError(*parser.get_reports())
            return parser.get_parsed()
        except RawFileError as e:
            raise LibraryError(
                reports.file_io_error(
                    e.file_type.file_type_code,
                    e.file_type.path,
                    e.reason,
                    e.action,
                )
            )

    def read_to_facade(self):
        return self._toolbox.facade(self.read_to_structure())

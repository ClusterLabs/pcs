from pcs.common import file_type_codes
from pcs.lib.file import(
    fs_metadata,
    raw_file,
    toolbox,
)

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
        return self._toolbox.parser(self._raw_file.read())

    def read_to_facade(self):
        return self._toolbox.facade(self.read_to_structure())

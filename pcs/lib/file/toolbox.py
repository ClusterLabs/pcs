from collections import namedtuple
import json

from pcs.common import file_type_codes as code
from pcs.lib import reports
from pcs.lib import file_interfaces
from pcs.lib.booth.config_facade import ConfigFacade as BoothConfigFacade
from pcs.lib.booth.config_parser import (
    Exporter as BoothConfigExporter,
    Parser as BoothConfigParser,
)


FileToolbox = namedtuple(
    "FileToolbox",
    [
        # File type code the toolbox belongs to
        "file_type_code",
        # Provides an easy access for reading and modifying data
        "facade",
        # Turns raw data into a structure which the facade is able to process
        "parser",
        # Turns a structure produced by the parser and the facade to raw data
        "exporter",
        # Checks that the structure is valid
        "validator",
        # Provides means for file syncing based on the file's version
        "version_controller",
    ]
)

class JsonParser(file_interfaces.ParserInterface):
    def _main_parse(self):
        try:
            # json.loads handles bytes, it expects utf-8, 16 or 32 encoding
            self._parsed = json.loads(self._raw_file_data)
        except json.JSONDecodeError as e:
            self._parse_error = True
            self._report_list.append(
                reports.parse_error_json_file(
                    self._file_type_code,
                    self._file_path,
                    e.lineno,
                    e.colno,
                    e.pos,
                    e.msg,
                    str(e)
                )
            )

class JsonExporter(file_interfaces.ExporterInterface):
    @staticmethod
    def export(config_structure):
        return json.dumps(config_structure).encode("utf-8")


_toolboxes = {
    code.BOOTH_CONFIG: FileToolbox(
        file_type_code=code.BOOTH_CONFIG,
        facade=BoothConfigFacade,
        parser=BoothConfigParser,
        exporter=BoothConfigExporter,
        validator=None, # TODO needed for files syncing
        version_controller=None, # TODO needed for files syncing
    ),
    code.PCS_KNOWN_HOSTS: FileToolbox(
        file_type_code=code.PCS_KNOWN_HOSTS,
        facade=None, # TODO needed for 'auth' and 'deauth' commands
        parser=JsonParser,
        exporter=JsonExporter,
        validator=None, # TODO needed for files syncing
        version_controller=None, # TODO needed for files syncing
    ),
}

def for_file_type(file_type_code):
    return _toolboxes[file_type_code]

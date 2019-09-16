from collections import namedtuple
import json

from pcs.common import file_type_codes as code
from pcs.lib import reports
from pcs.lib.booth.config_facade import ConfigFacade as BoothConfigFacade
from pcs.lib.booth.config_parser import (
    Exporter as BoothConfigExporter,
    Parser as BoothConfigParser,
)
from pcs.lib.interface.config import (
    ExporterInterface,
    FacadeInterface,
    ParserErrorException,
    ParserInterface,
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


class JsonParserException(ParserErrorException):
    def __init__(self, json_exception):
        super().__init__()
        self.json_exception = json_exception

class JsonParser(ParserInterface):
    """
    Adapts standard json parser to our interfaces
    """
    @staticmethod
    def parse(raw_file_data):
        try:
            # json.loads handles bytes, it expects utf-8, 16 or 32 encoding
            return json.loads(raw_file_data)
        except json.JSONDecodeError as e:
            raise JsonParserException(e)

    @staticmethod
    def exception_to_report_list(
        exception, file_type_code, file_path, force_code, is_forced_or_warning
    ):
        report_creator = reports.get_problem_creator(
            force_code=force_code, is_forced=is_forced_or_warning
        )
        if isinstance(exception, JsonParserException):
            if isinstance(exception.json_exception, json.JSONDecodeError):
                return [
                    report_creator(
                        reports.parse_error_json_file,
                        file_type_code,
                        exception.json_exception.lineno,
                        exception.json_exception.colno,
                        exception.json_exception.pos,
                        exception.json_exception.msg,
                        str(exception.json_exception),
                        file_path=file_path,
                    )
                ]
        raise exception

class JsonExporter(ExporterInterface):
    """
    Adapts standard json exporter to our interfaces
    """
    @staticmethod
    def export(config_structure):
        return json.dumps(
            config_structure, indent=4, sort_keys=True,
        ).encode("utf-8")


class NoopParser(ParserInterface):
    @staticmethod
    def parse(raw_file_data):
        return raw_file_data

    @staticmethod
    def exception_to_report_list(
        exception, file_type_code, file_path, force_code, is_forced_or_warning
    ):
        return []

class NoopExporter(ExporterInterface):
    @staticmethod
    def export(config_structure):
        return config_structure

class NoopFacade(FacadeInterface):
    @classmethod
    def create(cls):
        return cls(bytes())


_toolboxes = {
    code.BOOTH_CONFIG: FileToolbox(
        file_type_code=code.BOOTH_CONFIG,
        facade=BoothConfigFacade,
        parser=BoothConfigParser,
        exporter=BoothConfigExporter,
        validator=None, # TODO needed for files syncing
        version_controller=None, # TODO needed for files syncing
    ),
    code.BOOTH_KEY: FileToolbox(
        file_type_code=code.BOOTH_KEY,
        facade=NoopFacade,
        parser=NoopParser,
        exporter=NoopExporter,
        validator=None, # TODO needed for files syncing
        version_controller=None, # TODO needed for files syncing
    ),
    code.PACEMAKER_AUTHKEY: FileToolbox(
        file_type_code=code.PACEMAKER_AUTHKEY,
        facade=NoopFacade,
        parser=NoopParser,
        exporter=NoopExporter,
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

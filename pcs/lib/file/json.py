import json
from typing import Optional

from pcs.common import file_type_codes as code
from pcs.common import reports
from pcs.common.interface.dto import SerializableType
from pcs.lib.interface.config import (
    ExporterInterface,
    ParserErrorException,
    ParserInterface,
)


class JsonParserException(ParserErrorException):
    def __init__(self, json_exception: json.JSONDecodeError):
        super().__init__()
        self.json_exception = json_exception


class JsonParser(ParserInterface):
    """
    Adapts standard json parser to our interfaces
    """

    @staticmethod
    def parse(raw_file_data: bytes) -> SerializableType:
        try:
            # json.loads handles bytes, it expects utf-8, 16 or 32 encoding
            return json.loads(raw_file_data)
        except json.JSONDecodeError as e:
            raise JsonParserException(e) from e

    @staticmethod
    def exception_to_report_list(
        exception: ParserErrorException,
        file_type_code: code.FileTypeCode,
        file_path: Optional[str],
        force_code: Optional[reports.types.ForceCode],
        is_forced_or_warning: bool,
    ) -> reports.ReportItemList:
        if isinstance(exception, JsonParserException) and isinstance(
            exception.json_exception, json.JSONDecodeError
        ):
            return [
                reports.ReportItem(
                    severity=reports.item.get_severity(
                        force_code,
                        is_forced_or_warning,
                    ),
                    message=reports.messages.ParseErrorJsonFile(
                        file_type_code,
                        exception.json_exception.lineno,
                        exception.json_exception.colno,
                        exception.json_exception.pos,
                        exception.json_exception.msg,
                        str(exception.json_exception),
                        file_path=file_path,
                    ),
                )
            ]
        raise exception


class JsonExporter(ExporterInterface):
    """
    Adapts standard json exporter to our interfaces
    """

    @staticmethod
    def export(config_structure: SerializableType) -> bytes:
        return json.dumps(
            config_structure,
            indent=4,
            sort_keys=True,
        ).encode("utf-8")

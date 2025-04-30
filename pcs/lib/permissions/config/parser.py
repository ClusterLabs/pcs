from enum import Enum
from typing import (
    FrozenSet,
    Optional,
)

import dacite

from pcs.common import file_type_codes as code
from pcs.common import reports
from pcs.lib.file.json import JsonParser, JsonParserException
from pcs.lib.interface.config import (
    ParserErrorException,
    ParserInterface,
)

from .types import ConfigV2


class ParserError(ParserErrorException):
    def __init__(self, msg: Optional[str] = None) -> None:
        super().__init__()
        self.msg = msg


class ParserV2(ParserInterface):
    @staticmethod
    def parse(raw_file_data: bytes) -> ConfigV2:
        data = JsonParser.parse(raw_file_data)
        try:
            if not isinstance(data, dict):
                raise ParserError("Invalid data: root element is not an object")
            try:
                version = data.pop("format_version")
            except KeyError as e:
                raise ParserError("'format_version' not defined") from e
            if version != 2:
                raise ParserError(f"Unsupported format version '{version}'")
            return dacite.from_dict(
                ConfigV2, data, config=dacite.Config(cast=[Enum, FrozenSet])
            )
        except dacite.DaciteError as e:
            raise ParserError(str(e)) from e
        except ValueError as e:
            raise ParserError(str(e)) from e

    @staticmethod
    def exception_to_report_list(
        exception: ParserErrorException,
        file_type_code: code.FileTypeCode,
        file_path: Optional[str],
        force_code: Optional[reports.types.ForceCode],
        is_forced_or_warning: bool,
    ) -> reports.ReportItemList:
        if isinstance(exception, JsonParserException):
            return JsonParser.exception_to_report_list(
                exception,
                file_type_code,
                file_path,
                force_code,
                is_forced_or_warning,
            )
        if isinstance(exception, ParserError):
            return [
                reports.ReportItem(
                    severity=reports.item.get_severity(
                        force_code, is_forced_or_warning
                    ),
                    message=reports.messages.ParseErrorInvalidFileStructure(
                        exception.msg or "", file_type_code, file_path
                    ),
                )
            ]
        raise AssertionError() from exception

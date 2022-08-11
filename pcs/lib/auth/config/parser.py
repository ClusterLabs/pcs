from typing import (
    List,
    Optional,
)

import dacite

from pcs.common import file_type_codes as code
from pcs.common import reports
from pcs.lib.file.json import JsonParser
from pcs.lib.interface.config import (
    ParserErrorException,
    ParserInterface,
)

from .types import TokenEntry


class ParserError(ParserErrorException):
    def __init__(self, msg: Optional[str] = None) -> None:
        super().__init__()
        self.msg = msg


class Parser(ParserInterface):
    @staticmethod
    def parse(raw_file_data: bytes) -> List[TokenEntry]:
        data = JsonParser.parse(raw_file_data)
        if not isinstance(data, list):
            raise ParserError("root object is not list")
        try:
            return [
                dacite.from_dict(TokenEntry, entry_dict) for entry_dict in data
            ]
        except dacite.DaciteError as e:
            raise ParserError(str(e)) from e

    @staticmethod
    def exception_to_report_list(
        exception: ParserErrorException,
        file_type_code: code.FileTypeCode,
        file_path: Optional[str],
        force_code: Optional[reports.types.ForceCode],
        is_forced_or_warning: bool,
    ) -> reports.ReportItemList:
        raise NotImplementedError()

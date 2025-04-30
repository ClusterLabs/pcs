from typing import Optional

import dacite

from pcs.common import file_type_codes, reports
from pcs.lib.file.json import JsonParser, JsonParserException
from pcs.lib.interface.config import ParserErrorException, ParserInterface

from .types import KnownHosts


class InvalidFileStructureException(ParserErrorException):
    def __init__(self, msg: str):
        super().__init__()
        self.msg = msg


class Parser(ParserInterface):
    @staticmethod
    def parse(raw_file_data: bytes) -> KnownHosts:
        data = JsonParser.parse(raw_file_data)

        # change the structure of the parsed json, so it can be mapped into our
        # dataclass
        if not isinstance(data, dict):
            raise InvalidFileStructureException("root element is not an object")
        hosts_field = data.get("known_hosts")
        if hosts_field is not None and isinstance(hosts_field, dict):
            for host_name, host_data in hosts_field.items():
                host_data["name"] = host_name

        try:
            return dacite.from_dict(KnownHosts, data)
        except dacite.DaciteError as e:
            raise InvalidFileStructureException(str(e)) from e

    @staticmethod
    def exception_to_report_list(
        exception: ParserErrorException,
        file_type_code: file_type_codes.FileTypeCode,
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
        if isinstance(exception, InvalidFileStructureException):
            return [
                reports.ReportItem(
                    severity=reports.item.get_severity(
                        force_code,
                        is_forced_or_warning,
                    ),
                    message=reports.messages.ParseErrorInvalidFileStructure(
                        exception.msg, file_type_code, file_path
                    ),
                )
            ]
        raise AssertionError() from exception

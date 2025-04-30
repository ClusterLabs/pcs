from dataclasses import dataclass

from pcs.common.file_type_codes import FileTypeCode
from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class SyncConfigsDto(DataTransferObject):
    cluster_name: str
    configs: dict[FileTypeCode, str]

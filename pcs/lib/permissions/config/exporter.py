import dataclasses

from pcs.lib.file.json import JsonExporter
from pcs.lib.interface.config import ExporterInterface

from .types import ConfigV2


class ExporterV2(ExporterInterface):
    @staticmethod
    def export(config_structure: ConfigV2) -> bytes:
        data = dataclasses.asdict(config_structure)
        data["format_version"] = 2
        return JsonExporter.export(data)

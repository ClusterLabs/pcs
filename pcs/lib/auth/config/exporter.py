import dataclasses
from typing import List

from pcs.lib.file.json import JsonExporter
from pcs.lib.interface.config import ExporterInterface

from .types import TokenEntry


class Exporter(ExporterInterface):
    @staticmethod
    def export(config_structure: List[TokenEntry]) -> bytes:
        return JsonExporter.export(
            [dataclasses.asdict(entry) for entry in config_structure]
        )

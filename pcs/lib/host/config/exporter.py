import dataclasses

from pcs.lib.file.json import JsonExporter
from pcs.lib.interface.config import ExporterInterface

from .types import KnownHosts


class Exporter(ExporterInterface):
    @staticmethod
    def export(config_structure: KnownHosts) -> bytes:
        data = dataclasses.asdict(config_structure)

        # remove attribute not stored in file
        for host in data["known_hosts"].values():
            del host["name"]

        return JsonExporter.export(data)

from pcs.common import file_type_codes
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.toolbox import FileToolbox
from pcs.lib.file.toolbox import for_file_type as get_file_toolbox

from .config.facade import (
    DrRole,
    Facade,
)


class DrEnv:
    def __init__(self) -> None:
        self._config_file = FileInstance.for_dr_config()

    @staticmethod
    def create_facade(role: DrRole) -> Facade:
        return Facade.create(role)

    @property
    def config(self) -> FileInstance:
        return self._config_file

    @staticmethod
    def get_config_toolbox() -> FileToolbox:
        return get_file_toolbox(file_type_codes.PCS_DR_CONFIG)

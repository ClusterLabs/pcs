import time
from typing import Any

from pcs import settings
from pcs.common.validate import is_integer
from pcs.lib.interface.config import FacadeInterface


class Facade(FacadeInterface):
    def __init__(self, parsed_config: dict[str, Any]):
        super().__init__(parsed_config)

    @classmethod
    def create(cls) -> "Facade":
        return cls({})

    @property
    def is_sync_allowed(self) -> bool:
        thread_disabled = self._config.get("thread_disabled", False)
        if not isinstance(thread_disabled, bool):
            thread_disabled = False
        return not (thread_disabled or self.is_sync_paused)

    @property
    def is_sync_paused(self) -> bool:
        paused_until = self._config.get("thread_paused_until")
        return (
            paused_until is not None
            and is_integer(paused_until)
            and time.time() < paused_until
        )

    @property
    def sync_interval(self) -> int:
        return self.__get_int(
            "thread_interval",
            settings.cfgsync_thread_interval_default,
            settings.cfgsync_thread_interval_minimum,
        )

    @property
    def sync_interval_previous_not_connected(self) -> int:
        return self.__get_int(
            "thread_interval_previous_not_connected",
            settings.cfgsync_thread_interval_previous_not_connected_default,
            settings.cfgsync_thread_interval_previous_not_connected_minimum,
        )

    @property
    def file_backup_count(self) -> int:
        return self.__get_int(
            "file_backup_count",
            settings.cfgsync_file_backup_count_default,
            settings.cfgsync_file_backup_count_minimum,
        )

    def __get_int(
        self, key: str, default_value: int, minimum_value: int
    ) -> int:
        real_value = self._config.get(key, default_value)
        if is_integer(real_value):
            return max(real_value, minimum_value)
        return default_value

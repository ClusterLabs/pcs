from typing import Optional

from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.reports.item import ReportItem
from pcs.lib.booth import (
    config_validators,
    constants,
)
from pcs.lib.errors import LibraryError
from pcs.lib.file import raw_file
from pcs.lib.file.instance import FileInstance


class BoothEnv:
    def __init__(self, instance_name: Optional[str], booth_files_data):
        """
        Create a new BoothEnv

        instance_name -- booth instance name
        dict booth_files_data -- ghost files (config_data, key_data, key_path)
        """
        if (
            "config_data" in booth_files_data
            and "key_data" not in booth_files_data
        ):
            raise LibraryError(
                ReportItem.error(
                    reports.messages.LiveEnvironmentNotConsistent(
                        [file_type_codes.BOOTH_CONFIG],
                        [file_type_codes.BOOTH_KEY],
                    )
                )
            )
        if (
            "config_data" not in booth_files_data
            and "key_data" in booth_files_data
        ):
            raise LibraryError(
                ReportItem.error(
                    reports.messages.LiveEnvironmentNotConsistent(
                        [file_type_codes.BOOTH_KEY],
                        [file_type_codes.BOOTH_CONFIG],
                    )
                )
            )

        self._instance_name = instance_name or constants.DEFAULT_INSTANCE_NAME
        report_list = config_validators.check_instance_name(self._instance_name)
        if report_list:
            raise LibraryError(*report_list)

        self._config_file = FileInstance.for_booth_config(
            f"{self._instance_name}.conf",
            **self._init_file_data(booth_files_data, "config_data"),
        )
        self._key_file = FileInstance.for_booth_key(
            f"{self._instance_name}.key",
            **self._init_file_data(booth_files_data, "key_data"),
        )
        if isinstance(self._key_file.raw_file, raw_file.GhostFile):
            self._key_path = booth_files_data.get("key_path", "")
        else:
            self._key_path = self._key_file.raw_file.metadata.path

    @staticmethod
    def _init_file_data(booth_files_data, file_key):
        # ghost file not specified
        if file_key not in booth_files_data:
            return dict(
                ghost_file=False,
                ghost_data=None,
            )
        return dict(
            ghost_file=True,
            ghost_data=booth_files_data[file_key],
        )

    @property
    def instance_name(self) -> str:
        return self._instance_name

    @property
    def config(self):
        return self._config_file

    @property
    def config_path(self):
        if isinstance(self._config_file.raw_file, raw_file.GhostFile):
            raise AssertionError(
                "Reading config path is supported only in live environment"
            )
        return self._config_file.raw_file.metadata.path

    @property
    def key(self):
        return self._key_file

    @property
    def key_path(self):
        return self._key_path

    @property
    def ghost_file_codes(self):
        codes = []
        if isinstance(self._config_file.raw_file, raw_file.GhostFile):
            codes.append(self._config_file.raw_file.metadata.file_type_code)
        if isinstance(self._key_file.raw_file, raw_file.GhostFile):
            codes.append(self._key_file.raw_file.metadata.file_type_code)
        return codes

    def create_facade(self, site_list, arbitrator_list):
        return self._config_file.toolbox.facade.create(
            site_list, arbitrator_list
        )

    def export(self):
        if not isinstance(self._config_file.raw_file, raw_file.GhostFile):
            return {}
        return {
            "config_file": raw_file.export_ghost_file(
                self._config_file.raw_file
            ),
            "key_file": raw_file.export_ghost_file(self._key_file.raw_file),
        }

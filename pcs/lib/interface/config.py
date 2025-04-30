from typing import (
    Any,
    Optional,
)

from pcs.common import (
    file_type_codes,
    reports,
)


class ParserErrorException(Exception):
    pass


class ParserInterface:
    @staticmethod
    def parse(raw_file_data: bytes) -> Any:
        raise NotImplementedError()

    @staticmethod
    def exception_to_report_list(
        exception: ParserErrorException,
        file_type_code: file_type_codes.FileTypeCode,
        file_path: Optional[str],
        force_code: Optional[reports.types.ForceCode],
        is_forced_or_warning: bool,
    ) -> reports.ReportItemList:
        raise NotImplementedError()


class ExporterInterface:
    @staticmethod
    def export(config_structure: Any) -> bytes:
        """
        Export config structure to raw file data (bytes)

        config_structure -- parsed config file
        """
        raise NotImplementedError()


class FacadeInterface:
    # Facades should also implement a 'create' classmethod which creates a new
    # facade with a minimalistic config in it. This method for sure has
    # different interface in each class (depending on which config's facade it
    # is). The create method is not used by the files framework (there is no
    # need and also due to mentioned interface differences). Therefore the
    # create method is not defined here in the interface.

    _config: Any

    def __init__(self, parsed_config: Any):
        """
        Create a facade around a parsed config file

        parsed_config -- parsed config file
        """
        self._set_config(parsed_config)

    def _set_config(self, config: Any) -> None:
        self._config = config

    @property
    def config(self) -> Any:
        """
        Export a parsed config file
        """
        return self._config


class SyncVersionFacadeInterface(FacadeInterface):
    """
    Interface implemented by files that support automatic synchronization done
    by pcsd
    """

    @property
    def data_version(self) -> int:
        """
        Get data version of the underlying config file
        """
        raise NotImplementedError()

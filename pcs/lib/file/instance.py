from typing import (
    Any,
    Optional,
)

from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import (
    FileMetadata,
    RawFileInterface,
)
from pcs.lib.file import (
    metadata,
    raw_file,
)
from pcs.lib.file import toolbox as file_toolbox
from pcs.lib.interface.config import (
    FacadeInterface,
    ParserErrorException,
)


class FileInstance:
    # pylint: disable=too-many-public-methods
    """
    Provides a high-level easy access to config files
    """

    @classmethod
    def for_booth_config(
        cls,
        name: str,
        ghost_file: bool = False,
        ghost_data: Optional[bytes] = None,
    ) -> "FileInstance":
        """
        Factory for booth config file

        name -- booth instance name
        ghost_file -- use GhostFile if True, RealFile otherwise
        ghost_data -- initial GhostFile data
        """
        return cls._for_booth(
            file_type_codes.BOOTH_CONFIG, name, ghost_file, ghost_data
        )

    @classmethod
    def for_booth_key(
        cls,
        name: str,
        ghost_file: bool = False,
        ghost_data: Optional[bytes] = None,
    ) -> "FileInstance":
        """
        Factory for booth key file

        name -- booth instance name
        ghost_file -- use GhostFile if True, RealFile otherwise
        ghost_data -- initial GhostFile data
        """
        return cls._for_booth(
            file_type_codes.BOOTH_KEY, name, ghost_file, ghost_data
        )

    @classmethod
    def _for_booth(
        cls,
        file_type_code: file_type_codes.FileTypeCode,
        name: str,
        ghost_file: bool,
        ghost_data: Optional[bytes],
    ) -> "FileInstance":
        return cls(
            _get_raw_file(
                metadata.for_file_type(file_type_code, name),
                ghost_file,
                ghost_data,
            ),
            file_toolbox.for_file_type(file_type_code),
        )

    @classmethod
    def for_known_hosts(cls) -> "FileInstance":
        """
        Factory for known-hosts file
        """
        return cls.for_common(file_type_codes.PCS_KNOWN_HOSTS)

    @classmethod
    def for_pacemaker_key(cls) -> "FileInstance":
        """
        Factory for pacemaker key file
        """
        return cls.for_common(file_type_codes.PACEMAKER_AUTHKEY)

    @classmethod
    def for_dr_config(cls) -> "FileInstance":
        """
        Factory for disaster-recovery config file
        """
        return cls.for_common(file_type_codes.PCS_DR_CONFIG)

    @classmethod
    def for_corosync_conf(cls) -> "FileInstance":
        """
        Factory for corosync config file
        """
        return cls.for_common(file_type_codes.COROSYNC_CONF)

    @classmethod
    def for_qnetd_ca_cert(cls) -> "FileInstance":
        """
        Factory for corosync qnetd CA certificate
        """
        return cls.for_common(file_type_codes.COROSYNC_QNETD_CA_CERT)

    @classmethod
    def for_pcs_users_config(cls) -> "FileInstance":
        return cls.for_common(file_type_codes.PCS_USERS_CONF)

    @classmethod
    def for_pcs_settings_config(cls) -> "FileInstance":
        return cls.for_common(file_type_codes.PCS_SETTINGS_CONF)

    @classmethod
    def for_cfgsync_ctl(cls) -> "FileInstance":
        return cls.for_common(file_type_codes.CFGSYNC_CTL)

    @classmethod
    def for_common(
        cls,
        file_type_code: file_type_codes.FileTypeCode,
    ) -> "FileInstance":
        return cls(
            raw_file.RealFile(metadata.for_file_type(file_type_code)),
            file_toolbox.for_file_type(file_type_code),
        )

    def __init__(
        self,
        raw_file_interface: RawFileInterface,
        file_toolbox: file_toolbox.FileToolbox,
    ):
        """
        Factories should be used instead

        RawFileInterface raw_file_interface -- RealFile or GhostFile instance
        FileToolbox file_toolbox -- collection of file tools
        """
        self._raw_file = raw_file_interface
        self._toolbox = file_toolbox

    @property
    def raw_file(self) -> RawFileInterface:
        """
        Get the underlying RawFileInterface instance
        """
        return self._raw_file

    @property
    def toolbox(self) -> file_toolbox.FileToolbox:
        """
        Get the underlying FileToolbox instance
        """
        return self._toolbox

    def parser_exception_to_report_list(
        self,
        exception: ParserErrorException,
        force_code: Optional[reports.types.ForceCode] = None,
        is_forced_or_warning: bool = False,
    ) -> reports.ReportItemList:
        """
        Translate a RawFileError instance to a report

        exception -- an exception to be translated
        string force_code -- is it a forcible error? by which code?
        is_forced_or_warning -- return a warning if True, error otherwise
        """
        return self._toolbox.parser.exception_to_report_list(
            exception,
            self._raw_file.metadata.file_type_code,
            (
                None
                if isinstance(self._raw_file, raw_file.GhostFile)
                else self._raw_file.metadata.path
            ),
            force_code,
            is_forced_or_warning,
        )

    def read_to_facade(self) -> FacadeInterface:
        return self._toolbox.facade(self.read_to_structure())

    def read_to_structure(self) -> Any:
        return self._toolbox.parser.parse(self.read_raw())

    def read_raw(self) -> bytes:
        return self._raw_file.read()

    def raw_to_facade(self, raw_file_data: bytes) -> FacadeInterface:
        """
        Parse raw file data and return a corresponding facade

        raw_file_data -- data to be parsed
        """
        return self._toolbox.facade(self.raw_to_structure(raw_file_data))

    def raw_to_structure(self, raw_file_data: bytes) -> Any:
        """
        Parse raw file data and return a corresponding structure

        raw_file_data -- data to be parsed
        """
        return self._toolbox.parser.parse(raw_file_data)

    def facade_to_raw(self, facade: FacadeInterface) -> bytes:
        return self._toolbox.exporter.export(facade.config)

    def write_facade(
        self, facade: FacadeInterface, can_overwrite: bool = False
    ) -> None:
        self.write_structure(facade.config, can_overwrite=can_overwrite)

    def write_structure(
        self, structure: Any, can_overwrite: bool = False
    ) -> None:
        self.write_raw(
            self._toolbox.exporter.export(structure),
            can_overwrite=can_overwrite,
        )

    def write_raw(
        self, raw_file_data: bytes, can_overwrite: bool = False
    ) -> None:
        """
        Write raw data to a file

        raw_file_data -- data to be written
        can_overwrite -- raise if False and the file already exists
        """
        self._raw_file.write(raw_file_data, can_overwrite=can_overwrite)


def _get_raw_file(
    file_metadata: FileMetadata, is_ghost: bool, ghost_data: Optional[bytes]
) -> RawFileInterface:
    if is_ghost:
        return raw_file.GhostFile(file_metadata, file_data=ghost_data)
    return raw_file.RealFile(file_metadata)

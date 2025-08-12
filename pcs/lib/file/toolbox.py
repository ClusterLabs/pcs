from dataclasses import dataclass
from typing import (
    Optional,
    Type,
)

from pcs.common import file_type_codes as code
from pcs.common import reports
from pcs.lib.auth import config as auth_config
from pcs.lib.booth.config_facade import ConfigFacade as BoothConfigFacade
from pcs.lib.booth.config_parser import Exporter as BoothConfigExporter
from pcs.lib.booth.config_parser import Parser as BoothConfigParser
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade
from pcs.lib.corosync.config_parser import Exporter as CorosyncConfigExporter
from pcs.lib.corosync.config_parser import Parser as CorosyncConfigParser
from pcs.lib.dr.config.facade import Facade as DrConfigFacade
from pcs.lib.host.config.exporter import Exporter as KnownHostsExporter
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.host.config.parser import Parser as KnownHostsParser
from pcs.lib.interface.config import (
    ExporterInterface,
    FacadeInterface,
    ParserErrorException,
    ParserInterface,
)
from pcs.lib.pcs_cfgsync.config.facade import Facade as CfgsyncCtlFacade
from pcs.lib.permissions import config as pcs_settings_conf

from .json import (
    JsonExporter,
    JsonParser,
)


@dataclass(frozen=True)
class FileToolbox:
    # File type code the toolbox belongs to
    file_type_code: code.FileTypeCode
    # Provides an easy access for reading and modifying data
    facade: Type[FacadeInterface]
    # Turns raw data into a structure which the facade is able to process
    parser: Type[ParserInterface]
    # Turns a structure produced by the parser and the facade to raw data
    exporter: Type[ExporterInterface]
    # Checks that the structure is valid
    validator: None  # TBI
    # Provides means for file syncing based on the file's version
    version_controller: None  # TBI


class NoopParser(ParserInterface):
    @staticmethod
    def parse(raw_file_data: bytes) -> bytes:
        return raw_file_data

    @staticmethod
    def exception_to_report_list(
        exception: ParserErrorException,
        file_type_code: code.FileTypeCode,
        file_path: Optional[str],
        force_code: Optional[reports.types.ForceCode],
        is_forced_or_warning: bool,
    ) -> reports.ReportItemList:
        del (
            exception,
            file_type_code,
            file_path,
            force_code,
            is_forced_or_warning,
        )
        return []


class NoopExporter(ExporterInterface):
    @staticmethod
    def export(config_structure: bytes) -> bytes:
        return config_structure


class NoopFacade(FacadeInterface):
    @classmethod
    def create(cls) -> "NoopFacade":
        return cls(bytes())


_toolboxes = {
    code.BOOTH_CONFIG: FileToolbox(
        file_type_code=code.BOOTH_CONFIG,
        facade=BoothConfigFacade,
        parser=BoothConfigParser,
        exporter=BoothConfigExporter,
        validator=None,  # TODO needed for files syncing
        version_controller=None,  # TODO needed for files syncing
    ),
    code.BOOTH_KEY: FileToolbox(
        file_type_code=code.BOOTH_KEY,
        facade=NoopFacade,
        parser=NoopParser,
        exporter=NoopExporter,
        validator=None,  # TODO needed for files syncing
        version_controller=None,  # TODO needed for files syncing
    ),
    code.PCS_CFGSYNC_CTL: FileToolbox(
        file_type_code=code.PCS_CFGSYNC_CTL,
        facade=CfgsyncCtlFacade,
        parser=JsonParser,
        exporter=JsonExporter,
        validator=None,
        version_controller=None,
    ),
    code.COROSYNC_CONF: FileToolbox(
        file_type_code=code.COROSYNC_CONF,
        facade=CorosyncConfigFacade,
        parser=CorosyncConfigParser,
        exporter=CorosyncConfigExporter,
        validator=None,  # TODO needed for files syncing
        version_controller=None,  # TODO needed for files syncing
    ),
    code.COROSYNC_QNETD_CA_CERT: FileToolbox(
        file_type_code=code.COROSYNC_QNETD_CA_CERT,
        facade=NoopFacade,
        parser=NoopParser,
        exporter=NoopExporter,
        validator=None,  # TODO needed for files syncing
        version_controller=None,  # TODO needed for files syncing
    ),
    code.PACEMAKER_AUTHKEY: FileToolbox(
        file_type_code=code.PACEMAKER_AUTHKEY,
        facade=NoopFacade,
        parser=NoopParser,
        exporter=NoopExporter,
        validator=None,  # TODO needed for files syncing
        version_controller=None,  # TODO needed for files syncing
    ),
    code.PCS_KNOWN_HOSTS: FileToolbox(
        file_type_code=code.PCS_KNOWN_HOSTS,
        facade=KnownHostsFacade,
        parser=KnownHostsParser,
        exporter=KnownHostsExporter,
        validator=None,  # TODO needed for files syncing
        version_controller=None,  # TODO needed for files syncing
    ),
    code.PCS_DR_CONFIG: FileToolbox(
        file_type_code=code.PCS_DR_CONFIG,
        facade=DrConfigFacade,
        parser=JsonParser,
        exporter=JsonExporter,
        validator=None,  # TODO needed for files syncing
        version_controller=None,  # TODO needed for files syncing
    ),
    code.PCS_USERS_CONF: FileToolbox(
        file_type_code=code.PCS_USERS_CONF,
        facade=auth_config.facade.Facade,
        parser=auth_config.parser.Parser,
        exporter=auth_config.exporter.Exporter,
        validator=None,  # TODO needed for files syncing
        version_controller=None,  # TODO needed for files syncing
    ),
    code.PCS_SETTINGS_CONF: FileToolbox(
        file_type_code=code.PCS_SETTINGS_CONF,
        facade=pcs_settings_conf.facade.FacadeV2,
        parser=pcs_settings_conf.parser.ParserV2,
        exporter=pcs_settings_conf.exporter.ExporterV2,
        validator=None,  # TODO needed for files syncing
        version_controller=None,  # TODO needed for files syncing
    ),
}


def for_file_type(file_type_code: code.FileTypeCode) -> FileToolbox:
    return _toolboxes[file_type_code]

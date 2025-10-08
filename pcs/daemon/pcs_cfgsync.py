from logging import Logger
from typing import TYPE_CHECKING, Optional, cast

from pcs.common.node_communicator import Communicator, RequestTarget
from pcs.common.reports.processor import ReportProcessor
from pcs.common.reports.utils import format_file_role
from pcs.common.str_tools import format_list
from pcs.common.types import StringIterable
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import RawFileError, raw_file_error_report
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node_communication import NodeTargetLibFactory
from pcs.lib.pcs_cfgsync.config.facade import Facade as CfgsyncCtlFacade
from pcs.lib.pcs_cfgsync.fetcher import ConfigFetcher

if TYPE_CHECKING:
    from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncFacade
    from pcs.lib.host.config.facade import Facade as KnownHostsFacade


class CfgSyncPullManager:
    def __init__(
        self,
        report_processor: ReportProcessor,
        node_communicator: Communicator,
        logger: Logger,
    ):
        self._logger = logger
        self._report_processor = report_processor
        self._node_communicator = node_communicator
        self._fetcher = ConfigFetcher(
            self._node_communicator, self._report_processor
        )

    def run_cfgsync(self) -> int:
        self._logger.info("Config files sync started")

        ctl_facade = self._read_cfgsync_ctl()

        if not ctl_facade.is_sync_allowed:
            self._logger.info(
                "Config files sync is disabled or paused, skipping"
            )
            return ctl_facade.sync_interval

        cluster_name, node_names = self._get_cluster_info()
        if not cluster_name or len(node_names) < 2:
            self._logger.info(
                "Config files sync skipped, this host does not seem to be in a "
                "cluster of at least 2 nodes"
            )
            return ctl_facade.sync_interval

        target_list = self._get_request_targets(node_names)
        if len(target_list) < 2:
            self._logger.info(
                "Config files sync skipped, unable to find at least 2 request "
                "targets"
            )
            return ctl_facade.sync_interval

        self._logger.info(
            "Fetching config files from nodes: %s",
            format_list(t.label for t in target_list),
        )
        configs, was_connected = self._fetcher.fetch(cluster_name, target_list)
        for file_code, facade in configs.items():
            instance = FileInstance.for_common(file_code)
            try:
                self._logger.info(
                    "Saving config '%s' version %d to '%s'",
                    format_file_role(instance.raw_file.metadata.file_type_code),
                    facade.data_version,
                    instance.raw_file.metadata.path,
                )
                instance.write_facade(facade, can_overwrite=True)
            except RawFileError as e:
                self._report_processor.report(raw_file_error_report(e))

        self._logger.info("Config files sync finished")
        if was_connected:
            return ctl_facade.sync_interval
        return ctl_facade.sync_interval_previous_not_connected

    def _read_cfgsync_ctl(self) -> CfgsyncCtlFacade:
        ctl_instance = FileInstance.for_pcs_cfgsync_ctl()
        if not ctl_instance.raw_file.exists():
            self._logger.debug(
                "File '%s' does not exist, using default settings for config "
                "files sync",
                ctl_instance.raw_file.metadata.path,
            )
            return CfgsyncCtlFacade.create()

        ctl_facade = self._read_file(ctl_instance)
        if ctl_facade is not None:
            return ctl_facade
        self._logger.info(
            "Unable to read '%s', using default settings for config files sync",
            ctl_instance.raw_file.metadata.path,
        )
        return CfgsyncCtlFacade.create()

    def _get_cluster_info(self) -> tuple[str, list[str]]:
        corosync_conf_instance = FileInstance.for_corosync_conf()
        if not corosync_conf_instance.raw_file.exists():
            return "", []
        corosync_conf: Optional[CorosyncFacade] = self._read_file(
            corosync_conf_instance
        )
        if corosync_conf is None:
            return "", []

        cluster_name = corosync_conf.get_cluster_name()
        node_names = [
            node.name
            for node in corosync_conf.get_nodes()
            if node.name is not None
        ]
        return cluster_name, node_names

    def _get_request_targets(
        self, node_names: StringIterable
    ) -> list[RequestTarget]:
        known_hosts_instance = FileInstance.for_known_hosts()
        known_hosts_conf: Optional[KnownHostsFacade] = self._read_file(
            known_hosts_instance
        )

        reports, target_list = NodeTargetLibFactory(
            known_hosts_conf.known_hosts
            if known_hosts_conf is not None
            else {},
            self._report_processor,
        ).get_target_list_with_reports(node_names)
        self._report_processor.report_list(reports)
        return target_list

    def _read_file[T](self, file_instance: FileInstance) -> Optional[T]:
        try:
            return cast(T, file_instance.read_to_facade())
        except RawFileError as e:
            self._report_processor.report(raw_file_error_report(e))
        except ParserErrorException as e:
            self._report_processor.report_list(
                file_instance.parser_exception_to_report_list(e)
            )
        return None

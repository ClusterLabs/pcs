from typing import Optional, Sequence

from pcs.common import reports
from pcs.common.file_type_codes import PCS_KNOWN_HOSTS, PCS_SETTINGS_CONF
from pcs.common.host import PcsKnownHost
from pcs.common.node_communicator import Communicator, RequestTarget
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import RawFileError, raw_file_error_report
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.interface.config import SyncVersionFacadeInterface
from pcs.lib.pcs_cfgsync.save_sync import (
    save_sync_new_known_hosts,
    save_sync_new_version,
)
from pcs.lib.permissions.config.facade import FacadeV2 as PcsSettingsFacade


def update_pcs_settings_locally(
    pcs_settings: PcsSettingsFacade,
    report_processor: reports.ReportProcessor,
) -> None:
    pcs_settings.set_data_version(pcs_settings.data_version + 1)
    try:
        FileInstance.for_pcs_settings_config().write_facade(
            pcs_settings, can_overwrite=True
        )
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))


def update_known_hosts_locally(
    known_hosts: KnownHostsFacade,
    new_hosts: Sequence[PcsKnownHost],
    report_processor: reports.ReportProcessor,
) -> None:
    known_hosts.update_known_hosts(new_hosts)
    known_hosts.set_data_version(known_hosts.data_version + 1)

    try:
        FileInstance.for_known_hosts().write_facade(
            known_hosts, can_overwrite=True
        )
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))


def _handle_conflict(
    new_file: Optional[SyncVersionFacadeInterface],
    file_instance: FileInstance,
    report_processor: reports.ReportProcessor,
) -> None:
    report_processor.report(
        reports.ReportItem.error(
            reports.messages.PcsCfgsyncConflictRepeatAction()
        )
    )
    try:
        if new_file is not None:
            file_instance.write_facade(new_file, can_overwrite=True)
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))


def sync_pcs_settings_in_cluster(
    pcs_settings: PcsSettingsFacade,
    local_cluster_name: str,
    request_targets: Sequence[RequestTarget],
    node_communicator: Communicator,
    report_processor: reports.ReportProcessor,
) -> None:
    conflict_detected, failed_nodes, new_file = save_sync_new_version(
        PCS_SETTINGS_CONF,
        pcs_settings,
        local_cluster_name,
        request_targets,
        node_communicator,
        report_processor,
        fetch_on_conflict=True,
        reject_is_error=True,
    )
    if conflict_detected:
        _handle_conflict(
            new_file, FileInstance.for_pcs_settings_config(), report_processor
        )

    if failed_nodes:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncSendingConfigsToNodesFailed(
                    [PCS_SETTINGS_CONF], sorted(failed_nodes)
                )
            )
        )


def sync_known_hosts_in_cluster(
    known_hosts: KnownHostsFacade,
    new_hosts: Sequence[PcsKnownHost],
    local_cluster_name: str,
    request_targets: Sequence[RequestTarget],
    node_communicator: Communicator,
    report_processor: reports.ReportProcessor,
) -> None:
    conflict_detected, failed_nodes, new_file = save_sync_new_known_hosts(
        known_hosts,
        new_hosts,
        [],
        local_cluster_name,
        request_targets,
        node_communicator,
        report_processor,
    )
    if conflict_detected:
        _handle_conflict(
            new_file, FileInstance.for_known_hosts(), report_processor
        )

    if failed_nodes:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncSendingConfigsToNodesFailed(
                    [PCS_KNOWN_HOSTS], sorted(failed_nodes)
                )
            )
        )

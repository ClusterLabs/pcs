from typing import Optional, Sequence, cast

from pcs.common import reports
from pcs.common.file_type_codes import PCS_KNOWN_HOSTS, FileTypeCode
from pcs.common.host import PcsKnownHost
from pcs.common.node_communicator import Communicator, RequestTarget
from pcs.common.types import StringSequence
from pcs.lib.communication.pcs_cfgsync import SetConfigs, SetConfigsResult
from pcs.lib.communication.tools import run
from pcs.lib.file.toolbox import for_file_type as toolbox_for_file_type
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.interface.config import SyncVersionFacadeInterface
from pcs.lib.pcs_cfgsync.fetcher import ConfigFetcher


def save_sync_new_version(
    file_type_code: FileTypeCode,
    file: SyncVersionFacadeInterface,
    cluster_name: str,
    target_list: Sequence[RequestTarget],
    node_communicator: Communicator,
    report_processor: reports.ReportProcessor,
    fetch_on_conflict: bool,
    reject_is_error: bool = True,
) -> tuple[bool, Optional[SyncVersionFacadeInterface]]:
    """
    Update the file data_version of the file and send it to targets. If any
    target contained newer version of the file and fetch_on_conflict is set
    to True, then fetch the newest version of the file from all of the targets.
    Returns True if conflict was detected, and newest file if it was fetched.

    file_type_code -- type of the file
    file -- the local file
    cluster_name -- name of the cluster
    target_list -- cluster nodes where we are sending the updated config
    node_communicator -- tool for communication with the nodes
    report_processor -- tool for reporting
    fetch_on_conflict -- if True, fetch the newest version of the file from
        the targets on conflict
    reject_is_error -- if True, rejected configs will be reported as errors
    """
    toolbox = toolbox_for_file_type(file_type_code)
    file.set_data_version(file.data_version + 1)
    com_cmd = SetConfigs(
        report_processor,
        cluster_name,
        {file_type_code: toolbox.exporter.export(file.config).decode("utf-8")},
        rejection_severity=reports.ReportItemSeverity.error()
        if reject_is_error
        else reports.ReportItemSeverity.info(),
    )
    com_cmd.set_targets(target_list)  # type: ignore[no-untyped-call]
    results = run(node_communicator, com_cmd)  # type: ignore[no-untyped-call]

    # we are only interested in the REJECTED state, so we can decide if we need
    # to fetch the newest version of the file from the cluster. The other
    # statuses/errors are already reported during the communication command
    # call
    if not any(
        results[node_name].get(file_type_code) == SetConfigsResult.REJECTED
        for node_name in results
    ):
        return False, None

    file_to_save = None
    if fetch_on_conflict:
        report_processor.report(
            reports.ReportItem.info(
                reports.messages.PcsCfgsyncFetchingNewestConfig(
                    [file_type_code], [target.label for target in target_list]
                )
            )
        )
        fetcher = ConfigFetcher(node_communicator, report_processor)
        newest_files, _ = fetcher.fetch(
            cluster_name, target_list, [file_type_code]
        )
        file_to_save = newest_files.get(file_type_code)
    return True, file_to_save


def save_sync_new_known_hosts(
    known_hosts_facade: KnownHostsFacade,
    new_hosts: Sequence[PcsKnownHost],
    hosts_to_remove: StringSequence,
    cluster_name: str,
    target_list: Sequence[RequestTarget],
    node_communicator: Communicator,
    report_processor: reports.ReportProcessor,
) -> tuple[bool, Optional[SyncVersionFacadeInterface]]:
    """
    Add and/or remove known hosts from the file, then send it to targets.
    If any target contained newer version of the file, then try to resolve the
    conflict by fetching the newest version of the file from all of the
    targets and merging the local file with the newest file from cluster. Then
    add and/or remove the new hosts to the merged file and send it to targets.
    If some node has newer version of the file even after this, then fetch
    the newest version. Returns True if there was conflict that the function
    could not resolve, and newest file if it was fetched.

    known_hosts_facade -- local known-hosts file
    new_hosts -- hosts to add
    hosts_to_remove -- hosts to remove
    cluster_name -- name of the cluster
    target_list -- cluster nodes where we are sending the updated config
    node_communicator -- tool for communication with the nodes
    report_processor -- tool for reporting
    """
    old_local_known_hosts = known_hosts_facade.config
    known_hosts_facade.remove_known_hosts(hosts_to_remove)
    known_hosts_facade.update_known_hosts(new_hosts)

    conflict_detected, new_file = save_sync_new_version(
        PCS_KNOWN_HOSTS,
        known_hosts_facade,
        cluster_name,
        target_list,
        node_communicator,
        report_processor,
        fetch_on_conflict=True,
        reject_is_error=False,
    )

    if not conflict_detected:
        return False, None

    if new_file is None:
        # we detected conflict, but got no new file to work with, so it does
        # not make sense to try sending the config again
        return True, None

    newest_known_hosts_from_cluster = cast(KnownHostsFacade, new_file)

    known_hosts_facade = KnownHostsFacade(old_local_known_hosts)
    known_hosts_facade.set_data_version(
        newest_known_hosts_from_cluster.data_version
    )
    # first add the tokens from the cluster then the new tokens, so we overwrite
    # any tokens that were previously in the configs with the new tokens
    known_hosts_facade.update_known_hosts(
        list(newest_known_hosts_from_cluster.known_hosts.values())
    )
    known_hosts_facade.remove_known_hosts(hosts_to_remove)
    known_hosts_facade.update_known_hosts(new_hosts)

    return save_sync_new_version(
        PCS_KNOWN_HOSTS,
        known_hosts_facade,
        cluster_name,
        target_list,
        node_communicator,
        report_processor,
        fetch_on_conflict=True,
    )

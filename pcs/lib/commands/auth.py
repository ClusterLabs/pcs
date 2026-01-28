from typing import Mapping, cast

from pcs.common import reports
from pcs.common.auth import HostAuthData, HostWithTokenAuthData
from pcs.common.file import RawFileError
from pcs.common.file_type_codes import PCS_KNOWN_HOSTS
from pcs.common.node_communicator import PcsKnownHost, RequestTarget
from pcs.common.types import StringSequence
from pcs.lib.auth import validations
from pcs.lib.communication.nodes import Auth
from pcs.lib.communication.tools import run
from pcs.lib.env import LibraryEnvironment, LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pcs_cfgsync.save_sync import save_sync_new_known_hosts


def auth_hosts_token_no_sync(
    env: LibraryEnvironment, hosts: Mapping[str, HostWithTokenAuthData]
) -> None:
    """
    Add the specified hosts with custom tokens to the local known-hosts file.
    The updates to the known-hosts file are not synchronized into the cluster.
    Automatic known hosts synchronization should be disabled in cluster when
    setting a custom token.

    hosts -- mapping of host names to data needed for their authentication
    """
    if env.report_processor.report_list(
        validations.validate_hosts_with_token(hosts)
    ).has_errors:
        raise LibraryError()

    new_known_hosts = [
        host_data.to_known_host(host_name)
        for host_name, host_data in hosts.items()
    ]

    known_hosts_facade = _read_known_hosts_file(env.report_processor)

    known_hosts_facade.update_known_hosts(new_known_hosts)
    known_hosts_facade.set_data_version(known_hosts_facade.data_version + 1)

    try:
        FileInstance.for_known_hosts().write_facade(
            known_hosts_facade, can_overwrite=True
        )
    except RawFileError as e:
        env.report_processor.report(raw_file_error_report(e))
        raise LibraryError() from e


def auth_hosts(  # noqa: PLR0912
    env: LibraryEnvironment, hosts: Mapping[str, HostAuthData]
) -> None:
    """
    Authenticate the specified hosts. Sync the known-hosts file to all cluster
    nodes if the local node is in a cluster

    hosts -- mapping of host names to data needed for their authentication
    """
    if env.report_processor.report_list(
        validations.validate_hosts(hosts)
    ).has_errors:
        raise LibraryError()

    node_communicator = env.get_node_communicator()
    com_cmd = Auth(hosts, env.report_processor)
    # we do not want to raise LibraryError in case only some nodes returned
    # errors, since we want to update the known-hosts file with whatever tokens
    # we were able to receive - this is how the old impl behaved
    # this means we cannot blindly check errors by using processor.has_errors
    received_tokens: dict[str, str] = run(
        node_communicator,
        com_cmd,
    )  # type: ignore[no-untyped-call]

    new_known_hosts = [
        PcsKnownHost(
            name=host_name,
            token=received_tokens[host_name],
            dest_list=auth_data.dest_list,
        )
        for host_name, auth_data in hosts.items()
        if host_name in received_tokens
    ]

    if not new_known_hosts:
        if env.report_processor.has_errors:
            raise LibraryError()
        return

    known_hosts_facade = _read_known_hosts_file(env.report_processor)

    if not FileInstance.for_corosync_conf().raw_file.exists():
        # we are not running in a cluster, so just save the new tokens locally
        known_hosts_facade.update_known_hosts(new_known_hosts)
        known_hosts_facade.set_data_version(known_hosts_facade.data_version + 1)

        try:
            FileInstance.for_known_hosts().write_facade(
                known_hosts_facade, can_overwrite=True
            )
        except RawFileError as e:
            env.report_processor.report(raw_file_error_report(e))
            raise LibraryError() from e
        return

    # we are in cluster, so we distribute the new tokens
    corosync_conf = env.get_corosync_conf()
    cluster_name = corosync_conf.get_cluster_name()

    # we want to send the tokens to all cluster nodes, but we want to use
    # the new tokens in case we ran auth on any nodes that are already in
    # the cluster
    node_names, report_list = get_existing_nodes_names(corosync_conf, None)
    env.report_processor.report_list(report_list)
    new_hosts_already_in_cluster = set(received_tokens) & set(node_names)
    (
        report_list,
        target_list,
    ) = env.get_node_target_factory().get_target_list_with_reports(
        sorted(set(node_names) - new_hosts_already_in_cluster),
        allow_skip=False,
        report_none_host_found=False,
    )
    env.report_processor.report_list(report_list)
    target_list.extend(
        RequestTarget.from_known_host(host)
        for host in new_known_hosts
        if host.name in new_hosts_already_in_cluster
    )
    if not target_list:
        # we can end, since we have no cluster nodes where to send the config to
        if env.report_processor.has_errors:
            raise LibraryError()
        return

    conflict_detected, failed_nodes, new_file = save_sync_new_known_hosts(
        known_hosts_facade,
        new_known_hosts,
        [],
        cluster_name,
        target_list,
        node_communicator,
        env.report_processor,
    )
    if conflict_detected:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncConflictRepeatAction()
            )
        )
        try:
            if new_file is not None:
                FileInstance.for_known_hosts().write_facade(new_file, True)
        except RawFileError as e:
            env.report_processor.report(raw_file_error_report(e))

    nodes_with_missing_token = set(node_names) - {
        target.label for target in target_list
    }
    if failed_nodes or nodes_with_missing_token:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncSendingConfigsToNodesFailed(
                    [PCS_KNOWN_HOSTS],
                    sorted(set(failed_nodes) | nodes_with_missing_token),
                )
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()


def deauth_hosts(env: LibraryEnvironment, hosts: StringSequence) -> None:
    """
    Deauth the specified hosts. Sync the known-hosts file to all cluster
    nodes if the local node is in a cluster

    hosts -- host names of hosts to be deauthenticated
    """
    if not hosts:
        env.report_processor.report(
            reports.ReportItem.error(reports.messages.NoHostSpecified())
        )
        raise LibraryError()

    known_hosts_facade = _read_known_hosts_file(env.report_processor)

    current_known_hosts = known_hosts_facade.known_hosts
    unknown_hosts = {
        host_name for host_name in hosts if host_name not in current_known_hosts
    }
    if unknown_hosts:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.HostNotFound(sorted(unknown_hosts))
            )
        )
    if not (set(hosts) - unknown_hosts):
        if env.report_processor.has_errors:
            raise LibraryError()
        return

    _deauth_hosts_common(env, known_hosts_facade, hosts)


def deauth_all_local_hosts(env: LibraryEnvironment) -> None:
    """
    Deauth all hosts present in the local known-hosts file. Sync the known-hosts
    file to all cluster nodes if the local node is in a cluster
    """
    known_hosts_facade = _read_known_hosts_file(env.report_processor)

    all_known_hosts = list(known_hosts_facade.known_hosts.keys())
    if not all_known_hosts:
        return

    _deauth_hosts_common(env, known_hosts_facade, all_known_hosts)


def _read_known_hosts_file(
    report_processor: reports.ReportProcessor,
) -> KnownHostsFacade:
    file_instance = FileInstance.for_known_hosts()
    try:
        if file_instance.raw_file.exists():
            return cast(KnownHostsFacade, file_instance.read_to_facade())
        return KnownHostsFacade.create(data_version=0)
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    except ParserErrorException as e:
        report_processor.report_list(
            file_instance.parser_exception_to_report_list(e)
        )
    raise LibraryError()


def _deauth_hosts_common(
    env: LibraryEnvironment,
    known_hosts_facade: KnownHostsFacade,
    hosts_to_deauth: StringSequence,
) -> None:
    """
    Extracted common parts of deauth commands, to reduce code duplication
    Deauth hosts and sync the known-hosts file if needed.
    """
    if not FileInstance.for_corosync_conf().raw_file.exists():
        known_hosts_facade.remove_known_hosts(hosts_to_deauth)
        known_hosts_facade.set_data_version(known_hosts_facade.data_version + 1)
        try:
            FileInstance.for_known_hosts().write_facade(
                known_hosts_facade, can_overwrite=True
            )
        except RawFileError as e:
            env.report_processor.report(raw_file_error_report(e))
        if env.report_processor.has_errors:
            raise LibraryError()
        return

    node_communicator = env.get_node_communicator()
    corosync_conf = env.get_corosync_conf()
    cluster_name = corosync_conf.get_cluster_name()
    node_names, report_list = get_existing_nodes_names(corosync_conf, None)
    env.report_processor.report_list(report_list)
    report_list, target_list = (
        env.get_node_target_factory().get_target_list_with_reports(
            node_names, allow_skip=False
        )
    )
    env.report_processor.report_list(report_list)
    if not target_list:
        # we can end, since we have no cluster nodes where to send the config to
        if env.report_processor.has_errors:
            raise LibraryError()
        return

    conflict_detected, failed_nodes, new_file = save_sync_new_known_hosts(
        known_hosts_facade,
        [],
        hosts_to_deauth,
        cluster_name,
        target_list,
        node_communicator,
        env.report_processor,
    )
    if conflict_detected:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncConflictRepeatAction()
            )
        )
        try:
            if new_file is not None:
                FileInstance.for_known_hosts().write_facade(new_file, True)
        except RawFileError as e:
            env.report_processor.report(raw_file_error_report(e))

    nodes_with_missing_token = set(node_names) - {
        target.label for target in target_list
    }
    if failed_nodes or nodes_with_missing_token:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.PcsCfgsyncSendingConfigsToNodesFailed(
                    [PCS_KNOWN_HOSTS],
                    sorted(set(failed_nodes) | nodes_with_missing_token),
                )
            )
        )

    if env.report_processor.has_errors:
        raise LibraryError()

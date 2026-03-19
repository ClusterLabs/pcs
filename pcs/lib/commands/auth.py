from typing import Mapping, Sequence, cast

from pcs.common import reports
from pcs.common.auth import HostAuthData, HostWithTokenAuthData
from pcs.common.file import RawFileError
from pcs.common.node_communicator import PcsKnownHost, RequestTarget
from pcs.lib.auth import validations
from pcs.lib.communication.nodes import Auth
from pcs.lib.communication.tools import run
from pcs.lib.env import LibraryEnvironment, LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pcs_cfgsync.sync_files import (
    sync_known_hosts_in_cluster,
    update_known_hosts_locally,
)


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

    update_known_hosts_locally(
        known_hosts_facade, new_known_hosts, [], env.report_processor
    )
    if env.report_processor.has_errors:
        raise LibraryError()


def auth_hosts(
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

    com_cmd = Auth(hosts, env.report_processor)
    # we do not want to raise LibraryError in case only some nodes returned
    # errors, since we want to update the known-hosts file with whatever tokens
    # we were able to receive - this is how the old impl behaved
    # this means we cannot blindly check errors by using processor.has_errors
    received_tokens: dict[str, str] = run(
        env.get_node_communicator(),
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

    __auth_deauth_hosts_common(env, known_hosts_facade, new_known_hosts, [])


def deauth_hosts(env: LibraryEnvironment, hosts: list[str]) -> None:
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

    __auth_deauth_hosts_common(env, known_hosts_facade, [], hosts)


def deauth_all_local_hosts(env: LibraryEnvironment) -> None:
    """
    Deauth all hosts present in the local known-hosts file. Sync the known-hosts
    file to all cluster nodes if the local node is in a cluster
    """
    known_hosts_facade = _read_known_hosts_file(env.report_processor)

    all_known_hosts = list(known_hosts_facade.known_hosts.keys())
    if not all_known_hosts:
        return

    __auth_deauth_hosts_common(env, known_hosts_facade, [], all_known_hosts)


# TODO
# hosts_to_remove: set[str] or AbstractSet[str] would be ideal, to show that
# duplicates are ignored
# We would need to update pcs.common.interface.dto to allow sets when calling
# commands through API - json doesn't have set
def known_hosts_change(
    env: LibraryEnvironment,
    hosts_to_add: Mapping[str, HostWithTokenAuthData],
    hosts_to_remove: list[str],
) -> None:
    """
    Legacy command, allowing to directly change contents of known-hosts file on
    host

    Add and remove known-hosts, synchronize the known-hosts file if the local
    node is in cluster

    hosts_to_add -- new hosts to be added
    hosts_to_remove -- hosts to be removed
    """
    if env.report_processor.report_list(
        validations.validate_known_hosts_change(hosts_to_add, hosts_to_remove)
    ).has_errors:
        raise LibraryError()

    known_hosts_facade = _read_known_hosts_file(env.report_processor)

    new_known_hosts = [
        host_data.to_known_host(host_name)
        for host_name, host_data in hosts_to_add.items()
    ]
    __auth_deauth_hosts_common(
        env, known_hosts_facade, new_known_hosts, hosts_to_remove
    )


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


def __auth_deauth_hosts_common(
    env: LibraryEnvironment,
    known_hosts_facade: KnownHostsFacade,
    new_hosts: Sequence[PcsKnownHost],
    hosts_to_deauth: list[str],
) -> None:
    """
    Extracted common part of auth and deauth commands, to reduce code
    duplication

    Add and/or remove the hosts and sync the known-hosts file if needed
    """
    if not env.has_corosync_conf:
        # we are not running in a cluster, so just save the updated file
        # locally
        update_known_hosts_locally(
            known_hosts_facade,
            new_hosts,
            hosts_to_deauth,
            env.report_processor,
        )
        if env.report_processor.has_errors:
            raise LibraryError()
        return

    # we are in cluster, we distribute the new tokens
    corosync_conf = env.get_corosync_conf()
    cluster_name = corosync_conf.get_cluster_name()

    # we want to send the tokens to all cluster nodes, but we want to use
    # the new tokens in case we ran auth on any nodes that are already in
    # the cluster
    node_names, report_list = get_existing_nodes_names(corosync_conf, None)
    env.report_processor.report_list(report_list)
    new_hosts_already_in_cluster = {host.name for host in new_hosts} & set(
        node_names
    )
    (
        report_list,
        target_list,
    ) = env.get_node_target_factory().get_target_list_with_reports(
        sorted(set(node_names) - new_hosts_already_in_cluster), allow_skip=False
    )
    env.report_processor.report_list(report_list)
    target_list.extend(
        RequestTarget.from_known_host(host)
        for host in new_hosts
        if host.name in new_hosts_already_in_cluster
    )
    if not target_list:
        # we can end, since we have no cluster nodes where to send the config to
        if env.report_processor.has_errors:
            raise LibraryError()
        return
    nodes_with_missing_token = set(node_names) - {
        target.label for target in target_list
    }

    sync_known_hosts_in_cluster(
        known_hosts_facade,
        new_hosts,
        hosts_to_deauth,
        cluster_name,
        target_list,
        env.get_node_communicator_no_privilege_transition(),
        env.report_processor,
        nodes_with_missing_token,
    )
    if env.report_processor.has_errors:
        raise LibraryError()

from typing import Optional, Sequence

from lxml.etree import _Element

from pcs import settings
from pcs.common import reports
from pcs.common.permissions.dto import PermissionEntryDto
from pcs.common.permissions.types import PermissionGrantedType
from pcs.lib import node_communication_format
from pcs.lib.auth.types import AuthUser
from pcs.lib.cib import fencing_topology
from pcs.lib.cib.nvpair_multi import NVSET_INSTANCE, find_nvsets
from pcs.lib.cib.resource.bundle import verify as verify_bundles
from pcs.lib.cib.resource.primitive import find_primitives_by_agent
from pcs.lib.cib.tools import get_resources
from pcs.lib.commands.cluster.utils import ensure_live_env
from pcs.lib.communication import cluster
from pcs.lib.communication.corosync import (
    CheckCorosyncOffline,
    ReloadCorosyncConf,
)
from pcs.lib.communication.nodes import (
    DistributeFilesWithoutForces,
    GetOnlineTargets,
)
from pcs.lib.communication.tools import (
    AllSameDataMixin,
    CommunicationCommandInterface,
    run,
    run_and_raise,
)
from pcs.lib.corosync import config_validators
from pcs.lib.env import LibraryEnvironment, WaitType
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pacemaker.live import (
    get_cib,
    get_cib_file_runner_env,
    get_cib_xml,
    get_cib_xml_cmd_results,
    has_cib_xml,
)
from pcs.lib.pacemaker.live import verify as verify_cmd
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.pcs_cfgsync.sync_files import (
    sync_pcs_settings_in_cluster,
    update_pcs_settings_locally,
)
from pcs.lib.permissions.checker import PermissionsChecker
from pcs.lib.permissions.config.types import PermissionEntry
from pcs.lib.permissions.tools import (
    complete_access_list,
    read_pcs_settings_conf,
)
from pcs.lib.permissions.types import PermissionRequiredType
from pcs.lib.permissions.validations import validate_set_permissions
from pcs.lib.resource_agent.types import ResourceAgentName
from pcs.lib.tools import generate_binary_key


def verify(env: LibraryEnvironment, verbose: bool = False) -> None:
    runner = env.cmd_runner()
    (
        dummy_stdout,
        verify_stderr,
        verify_returncode,
        can_be_more_verbose,
    ) = verify_cmd(runner, verbose=verbose)

    # 1) Do not even try to think about upgrading!
    # 2) We do not need cib management in env (no need for push...).
    # So env.get_cib is not best choice here (there were considerations to
    # upgrade cib at all times inside env.get_cib). Go to a lower level here.
    if verify_returncode != 0:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.InvalidCibContent(
                    verify_stderr,
                    can_be_more_verbose,
                )
            )
        )

        # Cib is sometimes loadable even if `crm_verify` fails (e.g. when
        # fencing topology is invalid). On the other hand cib with id
        # duplication is not loadable.
        # We try extra checks when cib is possible to load.
        cib_xml, dummy_stderr, returncode = get_cib_xml_cmd_results(runner)
        if returncode != 0:
            raise LibraryError()
    else:
        cib_xml = get_cib_xml(runner)

    cib = get_cib(cib_xml)
    env.report_processor.report_list(
        fencing_topology.verify(
            cib,
            ClusterState(env.get_cluster_state()).node_section.nodes,
        )
    )
    env.report_processor.report_list(verify_bundles(get_resources(cib)))
    if env.report_processor.has_errors:
        raise LibraryError()


def corosync_authkey_change(
    env: LibraryEnvironment,
    corosync_authkey: Optional[bytes] = None,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Distribute new corosync authkey to all cluster nodes.

    env -- LibraryEnvironment
    corosync_authkey -- new authkey; if None, generate a random one
    force_flags -- list of flags codes
    """
    report_processor = env.report_processor
    target_factory = env.get_node_target_factory()

    cluster_nodes_names, nodes_report_list = get_existing_nodes_names(
        env.get_corosync_conf(),
        error_on_missing_name=True,
    )
    report_processor.report_list(nodes_report_list)
    (
        target_report_list,
        cluster_nodes_target_list,
    ) = target_factory.get_target_list_with_reports(
        cluster_nodes_names,
        allow_skip=False,
    )
    report_processor.report_list(target_report_list)
    if corosync_authkey is not None:
        if len(corosync_authkey) != settings.corosync_authkey_bytes:
            report_processor.report(
                reports.ReportItem(
                    severity=reports.item.get_severity(
                        reports.codes.FORCE,
                        reports.codes.FORCE in force_flags,
                    ),
                    message=reports.messages.CorosyncAuthkeyWrongLength(
                        len(corosync_authkey),
                        settings.corosync_authkey_bytes,
                        settings.corosync_authkey_bytes,
                    ),
                )
            )
    else:
        corosync_authkey = generate_binary_key(
            random_bytes_count=settings.corosync_authkey_bytes
        )

    if report_processor.has_errors:
        raise LibraryError()

    com_cmd: AllSameDataMixin = GetOnlineTargets(
        report_processor,
        ignore_offline_targets=reports.codes.SKIP_OFFLINE_NODES in force_flags,
    )
    com_cmd.set_targets(cluster_nodes_target_list)
    online_cluster_target_list = run_and_raise(
        env.get_node_communicator(), com_cmd
    )

    if not online_cluster_target_list:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.UnableToPerformOperationOnAnyNode()
            )
        )
        if report_processor.has_errors:
            raise LibraryError()

    com_cmd = DistributeFilesWithoutForces(
        env.report_processor,
        node_communication_format.corosync_authkey_file(corosync_authkey),
    )
    com_cmd.set_targets(online_cluster_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = ReloadCorosyncConf(env.report_processor)
    com_cmd.set_targets(online_cluster_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)


def wait_for_pcmk_idle(env: LibraryEnvironment, wait_value: WaitType) -> None:
    """
    Wait for the cluster to settle into stable state.

    env
    wait_value -- value describing the timeout the command
    """
    timeout = env.ensure_wait_satisfiable(wait_value)
    env.wait_for_idle(timeout)


def rename(
    env: LibraryEnvironment,
    new_name: str,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Change the name of the local cluster

    new_name -- new name for the cluster
    """

    def warn_dlm_resources(resources: _Element) -> reports.ReportItemList:
        if find_primitives_by_agent(
            resources, ResourceAgentName("ocf", "pacemaker", "controld")
        ):
            return [
                reports.ReportItem.warning(
                    reports.messages.DlmClusterRenameNeeded()
                )
            ]
        return []

    def warn_gfs2_resources(resources: _Element) -> reports.ReportItemList:
        for resource in find_primitives_by_agent(
            resources, ResourceAgentName("ocf", "heartbeat", "Filesystem")
        ):
            for nvset in find_nvsets(resource, NVSET_INSTANCE):
                if any(
                    (
                        nvpair.get("name") == "fstype"
                        and nvpair.get("value") == "gfs2"
                    )
                    for nvpair in nvset
                ):
                    return [
                        reports.ReportItem.warning(
                            reports.messages.Gfs2LockTableRenameNeeded()
                        )
                    ]
        return []

    ensure_live_env(env)

    if env.report_processor.report_list(
        config_validators.rename_cluster(
            new_name, force_cluster_name=reports.codes.FORCE in force_flags
        )
    ).has_errors:
        raise LibraryError()

    cib = None
    if has_cib_xml():
        cib = get_cib(get_cib_xml(env.cmd_runner(get_cib_file_runner_env())))
        resources = get_resources(cib)
        env.report_processor.report_list(warn_dlm_resources(resources))
        env.report_processor.report_list(warn_gfs2_resources(resources))

    corosync_conf = env.get_corosync_conf()
    skip_offline = reports.codes.SKIP_OFFLINE_NODES in force_flags

    corosync_nodes, report_list = get_existing_nodes_names(corosync_conf, None)
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    target_list = env.get_node_target_factory().get_target_list(
        corosync_nodes,
        allow_skip=skip_offline,
    )

    node_communicator = env.get_node_communicator()
    com_cmd: CommunicationCommandInterface

    com_cmd = CheckCorosyncOffline(env.report_processor, skip_offline)
    com_cmd.set_targets(target_list)
    running_targets = run(node_communicator, com_cmd)
    if running_targets:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.CorosyncNotRunningCheckFinishedRunning(
                    [target.label for target in running_targets]
                )
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()

    # The 'cluster-name' property has to be removed from CIB on all nodes, so
    # that it is initialized with the new cluster name from corosync after the
    # cluster is started
    com_cmd = cluster.RemoveCibClusterName(env.report_processor, skip_offline)
    com_cmd.set_targets(target_list)
    run_and_raise(node_communicator, com_cmd)

    corosync_conf.set_cluster_name(new_name)
    env.push_corosync_conf(corosync_conf, skip_offline)


def set_permissions(
    env: LibraryEnvironment, permissions: Sequence[PermissionEntryDto]
) -> None:
    """
    Replace the current local cluster permissions with provided permissions. If
    local node is in cluster, synchronize the updated pcs_settings file.

    permissions -- new permissions for the local cluster
    """
    # TODO
    # Checking user permissions is done in daemon command executor when calling
    # lib commands through API - GRANT in this case. If the user has GRANT,
    # then this command is called, and the command itself does only "extra"
    # permission checks in case the user is trying to change users with FULL
    # permissions.
    #
    # We need to properly check that user has permissions to call this command
    # when we eventually want to use this command from CLI through lib_wrapper!

    if env.report_processor.report_list(
        validate_set_permissions(permissions)
    ).has_errors:
        raise LibraryError()

    ensure_live_env(env)

    pcs_settings, report_list = read_pcs_settings_conf()
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    # TODO: The user_login and user_groups are None when calling
    # this command from cli through lib_wrapper -> this will break
    auth_user = AuthUser(env.user_login or "", env.user_groups or [])
    permissions_checker = PermissionsChecker(env.logger)

    new_full_users = set()
    new_permission_list = []
    for perm in permissions:
        if PermissionGrantedType.FULL in perm.allow:
            new_full_users.add((perm.name, perm.type))
        # Explicitly save dependant permissions. That way if the dependency is
        # changed in the future, it won't revoke permissions which were once
        # granted
        allow = complete_access_list(set(perm.allow))
        new_permission_list.append(
            PermissionEntry(name=perm.name, type=perm.type, allow=sorted(allow))
        )

    current_full_users = {
        (perm.name, perm.type)
        for perm in pcs_settings.get_entries_with_allow_full()
    }
    if new_full_users != current_full_users:
        if not permissions_checker.is_authorized(
            auth_user, PermissionRequiredType.FULL
        ):
            env.report_processor.report(
                reports.ReportItem.error(
                    reports.messages.NotAuthorizedToChangeFullPermission()
                )
            )
            raise LibraryError()

    # replace all of the the current permissions
    pcs_settings.set_permissions(new_permission_list)

    if not env.has_corosync_conf:
        update_pcs_settings_locally(pcs_settings, env.report_processor)
        if env.report_processor.has_errors:
            raise LibraryError()
        return

    # the node is in cluster, sync the updated config to cluster nodes
    corosync_conf = env.get_corosync_conf()
    local_cluster_name = corosync_conf.get_cluster_name()
    local_corosync_nodes, _ = get_existing_nodes_names(corosync_conf)
    request_targets = env.get_node_target_factory().get_target_list(
        local_corosync_nodes
    )
    node_communicator = env.get_node_communicator_no_privilege_transition()

    sync_pcs_settings_in_cluster(
        pcs_settings,
        local_cluster_name,
        request_targets,
        node_communicator,
        env.report_processor,
    )
    if env.report_processor.has_errors:
        raise LibraryError()

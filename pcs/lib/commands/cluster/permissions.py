from typing import Sequence

from pcs.common import reports
from pcs.common.permissions.dto import (
    PermissionEntryDto,
    PermissionMetadataDependenciesDto,
    PermissionMetadataDto,
    PermissionMetadataPermissionTypeDto,
    PermissionMetadataTargetTypeDto,
)
from pcs.common.permissions.types import PermissionGrantedType
from pcs.lib.auth.types import AuthUser
from pcs.lib.commands.cluster.utils import ensure_live_env
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pcs_cfgsync.sync_files import (
    sync_pcs_settings_in_cluster,
    update_pcs_settings_locally,
)
from pcs.lib.permissions import const
from pcs.lib.permissions.checker import PermissionsChecker
from pcs.lib.permissions.config.types import PermissionEntry
from pcs.lib.permissions.tools import (
    complete_access_list,
    read_pcs_settings_conf,
)
from pcs.lib.permissions.types import PermissionRequiredType
from pcs.lib.permissions.validations import validate_set_permissions


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


def get_permissions(env: LibraryEnvironment) -> list[PermissionEntryDto]:
    """
    Return local cluster permissions
    """
    ensure_live_env(env)

    pcs_settings, report_list = read_pcs_settings_conf()
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    return [
        entry.to_dto()
        for entry in pcs_settings.config.permissions.local_cluster
    ]


def get_permissions_metadata(env: LibraryEnvironment) -> PermissionMetadataDto:
    """
    Return metadata about cluster permissions
    """
    del env

    return PermissionMetadataDto(
        user_types=[
            PermissionMetadataTargetTypeDto(
                target_type, metadata.label, metadata.description
            )
            for target_type, metadata in const.PERMISSION_TARGET_TYPE_METADATA.items()
        ],
        permission_types=[
            PermissionMetadataPermissionTypeDto(
                permission_type, metadata.label, metadata.description
            )
            for permission_type, metadata in const.PERMISSION_GRANTED_TYPE_METADATA.items()
        ],
        permissions_dependencies=PermissionMetadataDependenciesDto(
            {
                permission_type: dependencies
                for permission_type, dependencies in const.PERMISSION_DEPENDENCIES.items()
                if dependencies
            }
        ),
    )

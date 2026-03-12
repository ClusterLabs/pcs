from typing import Optional, Tuple, cast

from pcs import settings
from pcs.common import reports
from pcs.lib import node_communication_format
from pcs.lib.commands.cluster.common import ensure_live_env
from pcs.lib.communication.corosync import ReloadCorosyncConf
from pcs.lib.communication.nodes import (
    DistributeFilesWithoutForces,
    GetOnlineTargets,
)
from pcs.lib.communication.tools import AllSameDataMixin, run_and_raise
from pcs.lib.corosync import config_facade
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.tools import generate_binary_key, generate_uuid


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


def _generate_cluster_uuid(
    corosync_conf: config_facade.ConfigFacade, is_forced: bool
) -> Tuple[reports.ReportItemList, config_facade.ConfigFacade]:
    report_list = []
    if corosync_conf.get_cluster_uuid():
        report_list.append(
            reports.ReportItem(
                severity=reports.item.get_severity(
                    reports.codes.FORCE, is_forced
                ),
                message=reports.messages.ClusterUuidAlreadySet(),
            )
        )
        if not is_forced:
            return report_list, corosync_conf

    corosync_conf.set_cluster_uuid(generate_uuid())
    return report_list, corosync_conf


def generate_cluster_uuid(
    env: LibraryEnvironment,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Add or update cluster UUID in live cluster

    env
    """
    ensure_live_env(env)
    corosync_conf = env.get_corosync_conf()
    report_list, corosync_conf = _generate_cluster_uuid(
        corosync_conf, reports.codes.FORCE in force_flags
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    env.push_corosync_conf(corosync_conf)


def generate_cluster_uuid_local(
    env: LibraryEnvironment,
    corosync_conf_content: bytes,
    force_flags: reports.types.ForceFlags = (),
) -> bytes:
    """
    Add or update cluster UUID in corosync.conf passed as an argument and return
    the updated config

    env
    corosync_conf_content -- corosync.conf to be updated
    """
    ensure_live_env(env)
    corosync_conf_instance = FileInstance.for_corosync_conf()
    try:
        corosync_conf: config_facade.ConfigFacade = cast(
            config_facade.ConfigFacade,
            corosync_conf_instance.raw_to_facade(corosync_conf_content),
        )
    except ParserErrorException as e:
        if env.report_processor.report_list(
            corosync_conf_instance.toolbox.parser.exception_to_report_list(
                e,
                corosync_conf_instance.toolbox.file_type_code,
                None,
                force_code=None,
                is_forced_or_warning=False,
            )
        ).has_errors:
            raise LibraryError() from e

    report_list, corosync_conf = _generate_cluster_uuid(
        corosync_conf, reports.codes.FORCE in force_flags
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    return corosync_conf_instance.facade_to_raw(corosync_conf)

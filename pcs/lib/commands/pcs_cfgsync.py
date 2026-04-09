from typing import Mapping, cast

from pcs.common import reports
from pcs.common.file import RawFileError
from pcs.common.pcs_cfgsync_dto import SyncConfigsDto
from pcs.lib.env import LibraryEnvironment, LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pcs_cfgsync.actions import UPDATE_SYNC_OPTIONS_ACTIONS
from pcs.lib.pcs_cfgsync.config.facade import Facade as CfgsyncCtlFacade
from pcs.lib.pcs_cfgsync.const import SYNCED_CONFIGS
from pcs.lib.pcs_cfgsync.sync_files import (
    sync_pcs_settings_in_cluster,
    update_pcs_settings_locally,
)
from pcs.lib.pcs_cfgsync.validations import validate_update_sync_options
from pcs.lib.permissions.config.facade import FacadeV2 as PcsSettingsFacade


def get_configs(env: LibraryEnvironment, cluster_name: str) -> SyncConfigsDto:
    """
    Get contents of synced configuration files from node

    cluster_name -- expected cluster name. End with an error if the requested
        node is not in the cluster with the expected name.
    """
    current_cluster_name = env.get_corosync_conf().get_cluster_name()
    if current_cluster_name != cluster_name:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.NodeReportsUnexpectedClusterName(cluster_name)
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()

    configs = {}
    for file_type_code in SYNCED_CONFIGS:
        file_instance = FileInstance.for_common(file_type_code)
        if not file_instance.raw_file.exists():
            # it's not an error if the file does not exist locally, we just
            # wont send it back
            continue
        try:
            configs[file_type_code] = file_instance.read_raw().decode("utf-8")
        except RawFileError as e:
            # in case of error when reading some file, we still might be able
            # to read and send the others without issues
            env.report_processor.report(
                raw_file_error_report(e, is_forced_or_warning=True)
            )

    return SyncConfigsDto(current_cluster_name, configs)


def update_sync_options(
    env: LibraryEnvironment, options: Mapping[str, str]
) -> None:
    """
    Update options for pcs cfgsync thread

    options -- options for pcs cfgsync
    """

    if env.report_processor.report_list(
        validate_update_sync_options(options)
    ).has_errors:
        raise LibraryError()

    cfgsync_ctl_instance = FileInstance.for_pcs_cfgsync_ctl()
    if not cfgsync_ctl_instance.raw_file.exists():
        cfgsync_ctl_facade = CfgsyncCtlFacade.create()
    else:
        try:
            cfgsync_ctl_facade = cast(
                CfgsyncCtlFacade, cfgsync_ctl_instance.read_to_facade()
            )
        except RawFileError as e:
            env.report_processor.report(raw_file_error_report(e))
        except ParserErrorException as e:
            env.report_processor.report_list(
                cfgsync_ctl_instance.parser_exception_to_report_list(e)
            )
    if env.report_processor.has_errors:
        raise LibraryError()

    for option_name, option_value in options.items():
        UPDATE_SYNC_OPTIONS_ACTIONS[option_name](
            cfgsync_ctl_facade, option_value
        )

    try:
        cfgsync_ctl_instance.write_facade(
            cfgsync_ctl_facade, can_overwrite=True
        )
    except RawFileError as e:
        env.report_processor.report(raw_file_error_report(e))
    if env.report_processor.has_errors:
        raise LibraryError()


# Internal use only


def save_sync_pcs_settings_internal(
    env: LibraryEnvironment, config_text: str
) -> None:
    """
    Only for internal usage from Ruby code!

    Update pcs_settings with new config_text. If local node is in cluster,
    synchronize the file to all cluster nodes.

    config_text -- the pcs_settings.conf file content to save
    """
    try:
        pcs_settings_conf = cast(
            PcsSettingsFacade,
            FileInstance.for_pcs_settings_config().raw_to_facade(
                config_text.encode("utf-8")
            ),
        )
    except ParserErrorException as e:
        env.report_processor.report_list(
            FileInstance.for_pcs_settings_config().parser_exception_to_report_list(
                e
            )
        )
        raise LibraryError() from e

    if not env.has_corosync_conf:
        update_pcs_settings_locally(pcs_settings_conf, env.report_processor)
        if env.report_processor.has_errors:
            raise LibraryError()
        return

    # Get cluster info
    corosync_conf = env.get_corosync_conf()
    local_cluster_name = corosync_conf.get_cluster_name()
    corosync_nodes, report_list = get_existing_nodes_names(corosync_conf)
    env.report_processor.report_list(report_list)
    report_list, request_targets = (
        env.get_node_target_factory().get_target_list_with_reports(
            corosync_nodes, allow_skip=False
        )
    )
    # report errors about missing tokens, but continue to attempt sync to
    # available nodes
    # compatibility with the original Ruby implemetation
    env.report_processor.report_list(report_list)

    sync_pcs_settings_in_cluster(
        pcs_settings_conf,
        local_cluster_name,
        request_targets,
        env.get_node_communicator_no_privilege_transition(),
        env.report_processor,
    )
    if env.report_processor.has_errors:
        raise LibraryError()

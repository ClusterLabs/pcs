from typing import Mapping, Optional, cast

from pcs import settings
from pcs.common import reports
from pcs.common.file import RawFileError
from pcs.common.file_type_codes import FileTypeCode
from pcs.common.pcs_cfgsync_dto import SyncConfigsDto
from pcs.lib.env import LibraryEnvironment, LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.interface.config import (
    FacadeInterface,
    ParserErrorException,
    SyncVersionFacadeInterface,
)
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pcs_cfgsync.actions import UPDATE_SYNC_OPTIONS_ACTIONS
from pcs.lib.pcs_cfgsync.config.facade import Facade as CfgsyncCtlFacade
from pcs.lib.pcs_cfgsync.const import CONFIGS_WITH_BACKUPS, SYNCED_CONFIGS
from pcs.lib.pcs_cfgsync.sync_files import (
    sync_pcs_settings_in_cluster,
    update_pcs_settings_locally,
)
from pcs.lib.pcs_cfgsync.tools import get_file_hash
from pcs.lib.pcs_cfgsync.validations import validate_update_sync_options
from pcs.lib.permissions.config.facade import FacadeV2 as PcsSettingsFacade


def get_configs(env: LibraryEnvironment, cluster_name: str) -> SyncConfigsDto:
    """
    Get contents of synced configuration files from node

    cluster_name -- expected cluster name. End with an error if the local
        cluster name does not match cluster_name.
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


def set_configs(
    env: LibraryEnvironment,
    cluster_name: str,
    configs: dict[FileTypeCode, str],
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Save configuration files locally.

    cluster_name -- expected cluster name. End with an error if the local
        cluster name does not match cluster_name.
    configs -- contents of files to be saved
    force_flags -- list of flags codes
    """
    # the node is either in cluster (has_corosync_conf) and the cluster names
    # must match, or the node is not in cluster and there is no cluster name to
    # check against - this happens when this command is used on a node that is
    # being added to a cluster.
    if env.has_corosync_conf:
        local_cluster_name = env.get_corosync_conf().get_cluster_name()
        if local_cluster_name != cluster_name:
            env.report_processor.report(
                reports.ReportItem.error(
                    reports.messages.NodeReportsUnexpectedClusterName(
                        cluster_name
                    )
                )
            )
    if env.report_processor.has_errors:
        raise LibraryError()

    # continue even when we cannot read the cfgsync_ctl file, only report
    # warnings and then use default values
    cfgsync_ctl_facade, report_list = __read_cfgsync_ctl(report_warnings=True)
    env.report_processor.report_list(report_list)

    for file_type in sorted(configs):
        if file_type not in SYNCED_CONFIGS:
            env.report_processor.report(
                reports.ReportItem.warning(
                    reports.messages.PcsCfgsyncConfigUnsupported(file_type)
                )
            )
            continue

        file_instance = FileInstance.for_common(file_type)
        raw_text = configs[file_type]

        try:
            remote_file = cast(
                SyncVersionFacadeInterface,
                file_instance.raw_to_facade(raw_text.encode("utf-8")),
            )
        except ParserErrorException as e:
            env.report_processor.report_list(
                file_instance.parser_exception_to_report_list(e)
                + [
                    reports.ReportItem.error(
                        reports.messages.PcsCfgsyncConfigSaveError(file_type)
                    )
                ]
            )
            continue

        # Backwards compatibility: original Ruby implementation ignored file
        # read errors, and treated them the same as if the file was nonexistent
        # This allows us to replace invalid local files.
        #
        # So we report warnings, and treat the file the same as nonexistent.
        local_file: Optional[SyncVersionFacadeInterface]
        local_file, report_list = __read_local_file(
            file_instance, report_warnings=True
        )
        env.report_processor.report_list(report_list)

        if local_file is None:
            report_list = __accept_and_write_file(
                file_instance, remote_file, create_backup=False
            )
            env.report_processor.report_list(report_list)
            continue

        local_file_hash = get_file_hash(file_instance, local_file)
        remote_file_hash = get_file_hash(file_instance, remote_file)
        if (
            remote_file.data_version == local_file.data_version
            and remote_file_hash == local_file_hash
        ):
            # The file is the same, we don't want to backup and save it
            # again, just report success
            env.report_processor.report(
                reports.ReportItem.info(
                    reports.messages.PcsCfgsyncConfigAccepted(file_type)
                )
            )
            continue

        remote_is_newer = (
            remote_file.data_version > local_file.data_version
            or (
                local_file.data_version == remote_file.data_version
                and remote_file_hash > local_file_hash
            )
        )
        if remote_is_newer or reports.codes.FORCE in force_flags:
            report_list = __accept_and_write_file(
                file_instance,
                remote_file,
                create_backup=file_type in CONFIGS_WITH_BACKUPS,
                backup_count=cfgsync_ctl_facade.file_backup_count,
            )
            env.report_processor.report_list(report_list)
            continue

        # no condition for accepting the file was fulfilled, so we reject
        env.report_processor.report(
            reports.ReportItem.warning(
                reports.messages.PcsCfgsyncConfigRejected(file_type)
            )
        )

    if env.report_processor.has_errors:
        raise LibraryError()


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

    cfgsync_ctl_facade, report_list = __read_cfgsync_ctl()
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    for option_name, option_value in options.items():
        UPDATE_SYNC_OPTIONS_ACTIONS[option_name](
            cfgsync_ctl_facade, option_value
        )

    try:
        FileInstance.for_pcs_cfgsync_ctl().write_facade(
            cfgsync_ctl_facade, can_overwrite=True
        )
    except RawFileError as e:
        env.report_processor.report(raw_file_error_report(e))
    if env.report_processor.has_errors:
        raise LibraryError()


def __read_local_file[T: FacadeInterface](
    file_instance: FileInstance,
    report_warnings: bool,
) -> tuple[Optional[T], reports.ReportItemList]:
    report_list: reports.ReportItemList = []

    if not file_instance.raw_file.exists():
        return None, report_list

    try:
        return cast(T, file_instance.read_to_facade()), report_list
    except RawFileError as e:
        report_list.append(
            raw_file_error_report(e, is_forced_or_warning=report_warnings)
        )
    except ParserErrorException as e:
        report_list.extend(
            file_instance.parser_exception_to_report_list(
                e, is_forced_or_warning=report_warnings
            )
        )
    return None, report_list


def __read_cfgsync_ctl(
    report_warnings: bool = False,
) -> tuple[CfgsyncCtlFacade, reports.ReportItemList]:
    local_file: Optional[CfgsyncCtlFacade]
    local_file, report_list = __read_local_file(
        FileInstance.for_pcs_cfgsync_ctl(), report_warnings
    )
    if local_file is None:
        local_file = CfgsyncCtlFacade.create()
    return local_file, report_list


def __accept_and_write_file(
    file_instance: FileInstance,
    file: FacadeInterface,
    create_backup: bool,
    backup_count: int = settings.pcs_cfgsync_file_backup_count_default,
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    file_type = file_instance.toolbox.file_type_code
    try:
        if create_backup:
            file_instance.raw_file.backup()
            file_instance.raw_file.remove_old_backups(backup_count)
        # if any of the backup methods raise RawFileError, we do not
        # want to try overwriting the file
        file_instance.write_facade(file, can_overwrite=True)
        report_list.append(
            reports.ReportItem.info(
                reports.messages.PcsCfgsyncConfigAccepted(file_type)
            )
        )
    except RawFileError as e:
        report_list.extend(
            [
                raw_file_error_report(e),
                reports.ReportItem.error(
                    reports.messages.PcsCfgsyncConfigSaveError(file_type)
                ),
            ]
        )
    return report_list


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
    # compatibility with the original Ruby implementation
    env.report_processor.report_list(report_list)
    nodes_with_missing_token = set(corosync_nodes) - {
        target.label for target in request_targets
    }

    sync_pcs_settings_in_cluster(
        pcs_settings_conf,
        local_cluster_name,
        request_targets,
        env.get_node_communicator_no_privilege_transition(),
        env.report_processor,
        local_nodes_with_missing_token=nodes_with_missing_token,
    )
    if env.report_processor.has_errors:
        raise LibraryError()

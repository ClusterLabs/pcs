from pcs.common import reports
from pcs.common.cfgsync_dto import SyncConfigsDto
from pcs.common.file import RawFileError
from pcs.lib.cfgsync.const import SYNCED_CONFIGS
from pcs.lib.env import LibraryEnvironment, LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report


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

from pcs.common import file_type_codes, reports
from pcs.lib.cib.node_rename import check_corosync_consistency, rename_in_cib
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names


def rename_node_cib(
    env: LibraryEnvironment,
    old_name: str,
    new_name: str,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Rename a cluster node in CIB configuration elements.

    old_name -- current node name
    new_name -- new node name
    """

    if env.is_cib_live:
        if not env.is_corosync_conf_live:
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.LiveEnvironmentNotConsistent(
                        [file_type_codes.COROSYNC_CONF],
                        [file_type_codes.CIB],
                    )
                )
            )
        corosync_node_names, corosync_nodes_report_list = (
            get_existing_nodes_names(env.get_corosync_conf(), None)
        )
        corosync_nodes_report_list.extend(
            check_corosync_consistency(
                corosync_node_names, old_name, new_name, force_flags
            )
        )

        env.report_processor.report_list(corosync_nodes_report_list)

    if env.report_processor.has_errors:
        raise LibraryError()

    cib = env.get_cib()
    cib_updated, report_list = rename_in_cib(cib, old_name, new_name)
    env.report_processor.report_list(report_list)

    if cib_updated:
        env.push_cib()
        return

    env.report_processor.report(
        reports.ReportItem.info(reports.messages.CibNodeRenameNoChange())
    )

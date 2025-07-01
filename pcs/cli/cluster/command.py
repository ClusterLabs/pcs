from typing import (
    Any,
    Optional,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    FUTURE_OPTION,
    Argv,
    InputModifiers,
    KeyValueParser,
)
from pcs.cli.reports.output import (
    deprecation_warning,
    process_library_reports,
    warn,
)
from pcs.cli.resource.parse_args import (
    parse_primitive as parse_primitive_resource,
)
from pcs.common import reports
from pcs.lib.errors import LibraryError


def _node_add_remote_separate_name_and_addr(
    arg_list: Argv,
) -> tuple[str, Optional[str], list[str]]:
    """
    Commandline options: no options
    """
    node_name = arg_list[0]
    if len(arg_list) == 1:
        node_addr = None
        rest_args = []
    elif "=" in arg_list[1] or arg_list[1] in ["op", "meta"]:
        node_addr = None
        rest_args = arg_list[1:]
    else:
        node_addr = arg_list[1]
        rest_args = arg_list[2:]
    return node_name, node_addr, rest_args


def node_add_remote(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --wait
      * --force - allow incomplete distribution of files, allow pcmk remote
        service to fail
      * --skip-offline - skip offline nodes
      * --request-timeout - HTTP request timeout
      * --no-default-ops - do not use default operations
      For tests:
      * --corosync_conf
      * -f
    """
    modifiers.ensure_only_supported(
        "--wait",
        "--force",
        "--skip-offline",
        "--request-timeout",
        "--corosync_conf",
        "-f",
        "--no-default-ops",
    )
    if not arg_list:
        raise CmdLineInputError()

    node_name, node_addr, rest_args = _node_add_remote_separate_name_and_addr(
        arg_list
    )

    parts = parse_primitive_resource(rest_args)
    force = modifiers.get("--force")

    lib.remote_node.node_add_remote(
        node_name,
        node_addr,
        parts.operations,
        parts.meta_attrs,
        parts.instance_attrs,
        skip_offline_nodes=modifiers.get("--skip-offline"),
        allow_incomplete_distribution=force,
        allow_pacemaker_remote_service_fail=force,
        allow_invalid_operation=force,
        allow_invalid_instance_attributes=force,
        use_default_operations=not modifiers.get("--no-default-ops"),
        wait=modifiers.get("--wait"),
    )


def node_remove_remote(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --force - allow multiple nodes removal, allow pcmk remote service
        to fail, (deprecated) don't stop a resource before its deletion
      * --skip-offline - skip offline nodes
      * --request-timeout - HTTP request timeout
      * --no-stop - don't stop resources before deletion
      * --future - specifying '--force' does not skip resource stopping
      For tests:
      * --corosync_conf
      * -f
    """

    def _process_reports(
        report_list: reports.ReportItemList,
        force_flags: reports.types.ForceFlags,
    ) -> reports.ReportItemList:
        filtered_reports = []
        for report in report_list:
            if (
                report.message.code
                == reports.codes.CANNOT_REMOVE_RESOURCES_NOT_STOPPED
            ):
                continue
            if (
                report.severity.level == reports.ReportItemSeverity.ERROR
                and report.severity.force_code in force_flags
            ):
                report.severity = reports.ReportItemSeverity.warning()
            filtered_reports.append(report)
        return filtered_reports

    modifiers.ensure_only_supported(
        "--corosync_conf",
        "-f",
        "--force",
        FUTURE_OPTION,
        "--no-stop",
        "--request-timeout",
        "--skip-offline",
    )
    modifiers.ensure_not_mutually_exclusive("-f", "--no-stop")

    if len(arg_list) != 1:
        raise CmdLineInputError()
    node_identifier = arg_list[0]

    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)

    if modifiers.is_specified("-f"):
        warn(
            "Resources are not going to be stopped before deletion because the "
            "command does not run on a live cluster"
        )
        lib.remote_node.node_remove_remote(node_identifier, force_flags)
        return

    dont_stop_me_now = modifiers.is_specified("--no-stop")
    if (
        not modifiers.is_specified(FUTURE_OPTION)
        and modifiers.is_specified("--force")
        and not dont_stop_me_now
    ):
        # deprecated after pcs-0.12.0
        deprecation_warning(
            "Using '--force' to skip resource stopping is deprecated. Specify "
            "'--future' to switch to the future behavior and use '--no-stop' "
            "to skip resource stopping."
        )
        dont_stop_me_now = True

    if dont_stop_me_now:
        lib.remote_node.node_remove_remote(node_identifier, force_flags)
        return

    original_report_processor = lib.env.report_processor
    # TODO we are catching the reports and printing them after the command
    # finishes. This is problematic with lib.remote_node.node_remove_remote
    # since it communicates with other nodes which can take a lot of time.
    # This means that the user does not see any output and might think that
    # the command is not doing anything.
    # We can start printing the reports when first report about node
    # communication was put into the processor, since we know the "validations"
    # passed and any further fails in the lib command mean that this cli
    # command fails as well
    in_memory_report_processor = reports.processor.ReportProcessorInMemory()
    lib.env.report_processor = in_memory_report_processor

    try:
        temp_force_flags = [
            flag for flag in force_flags if flag != reports.codes.FORCE
        ]
        lib.remote_node.node_remove_remote(node_identifier, temp_force_flags)

        if in_memory_report_processor.reports:
            process_library_reports(
                in_memory_report_processor.reports,
                include_debug=modifiers.is_specified("--debug"),
            )
        return
    except LibraryError as e:
        filtered_reports = _process_reports(
            in_memory_report_processor.reports, force_flags
        )

        if reports.has_errors(filtered_reports) or e.output or e.args:
            if filtered_reports:
                process_library_reports(
                    filtered_reports,
                    include_debug=modifiers.is_specified("--debug"),
                    exit_on_error=False,
                )

            raise e

    lib.env.report_processor = original_report_processor

    resource_ids = lib.remote_node.get_resource_ids(node_identifier)
    lib.resource.stop(resource_ids, force_flags)
    lib.cluster.wait_for_pcmk_idle(None)

    lib.remote_node.node_remove_remote(node_identifier, force_flags)


def node_add_guest(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --wait
      * --force - allow incomplete distribution of files, allow pcmk remote
        service to fail
      * --skip-offline - skip offline nodes
      * --request-timeout - HTTP request timeout
      For tests:
      * --corosync_conf
      * -f
    """
    modifiers.ensure_only_supported(
        "--wait",
        "--force",
        "--skip-offline",
        "--request-timeout",
        "--corosync_conf",
        "-f",
    )
    if len(arg_list) < 2:
        raise CmdLineInputError()

    node_name = arg_list[0]
    resource_id = arg_list[1]
    meta_options = KeyValueParser(arg_list[2:]).get_unique()

    lib.remote_node.node_add_guest(
        node_name,
        resource_id,
        meta_options,
        skip_offline_nodes=modifiers.get("--skip-offline"),
        allow_incomplete_distribution=modifiers.get("--force"),
        allow_pacemaker_remote_service_fail=modifiers.get("--force"),
        wait=modifiers.get("--wait"),
    )


def node_remove_guest(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --wait
      * --force - allow multiple nodes removal, allow pcmk remote service to
        fail
      * --skip-offline - skip offline nodes
      * --request-timeout - HTTP request timeout
      For tests:
      * --corosync_conf
      * -f
    """
    modifiers.ensure_only_supported(
        "--wait",
        "--force",
        "--skip-offline",
        "--request-timeout",
        "--corosync_conf",
        "-f",
    )
    if len(arg_list) != 1:
        raise CmdLineInputError()

    lib.remote_node.node_remove_guest(
        arg_list[0],
        skip_offline_nodes=modifiers.get("--skip-offline"),
        allow_remove_multiple_nodes=modifiers.get("--force"),
        allow_pacemaker_remote_service_fail=modifiers.get("--force"),
        wait=modifiers.get("--wait"),
    )


def node_clear(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --force - allow to clear a cluster node
    """
    modifiers.ensure_only_supported("--force")
    if len(arg_list) != 1:
        raise CmdLineInputError()

    lib.cluster.node_clear(
        arg_list[0], allow_clear_cluster_node=modifiers.get("--force")
    )


def cluster_rename(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --force
      * --skip-offline - skip offline nodes
    """
    modifiers.ensure_only_supported("--force", "--skip-offline")
    if len(argv) != 1:
        raise CmdLineInputError()
    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)

    lib.cluster.rename(argv[0], force_flags)

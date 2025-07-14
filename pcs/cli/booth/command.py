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
    group_by_keywords,
)
from pcs.cli.reports.output import (
    deprecation_warning,
    process_library_reports,
    warn,
)
from pcs.common import reports
from pcs.common.reports import codes as report_codes
from pcs.lib.errors import LibraryError


def config_setup(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    create booth config

    Options:
      * --force - overwrite existing
      * --booth-conf - booth config file
      * --booth-key - booth authkey file
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported(
        "--force",
        "--booth-conf",
        "--booth-key",
        "--name",
    )
    peers = group_by_keywords(arg_list, {"sites", "arbitrators"})
    peers.ensure_unique_keywords()
    if not peers.has_keyword("sites") or not peers.get_args_flat("sites"):
        raise CmdLineInputError()

    lib.booth.config_setup(
        peers.get_args_flat("sites"),
        peers.get_args_flat("arbitrators"),
        instance_name=modifiers.get("--name"),
        overwrite_existing=modifiers.get("--force"),
    )


def config_destroy(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    destroy booth config

    Options:
      --force - ignore config load issues
      --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--force", "--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.config_destroy(
        instance_name=modifiers.get("--name"),
        ignore_config_load_problems=modifiers.get("--force"),
    )


def config_show(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    print booth config

    Options:
      * --name - name of a booth instance
      * --request-timeout - HTTP timeout for getting config from remote host
    """
    modifiers.ensure_only_supported("--name", "--request-timeout")
    if len(arg_list) > 1:
        raise CmdLineInputError()
    node = None if not arg_list else arg_list[0]

    print(
        lib.booth.config_text(
            instance_name=modifiers.get("--name"), node_name=node
        )
        .decode("utf-8")
        .rstrip()
    )


def config_ticket_add(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    add ticket to current configuration

    Options:
      * --force
      * --booth-conf - booth config file
      * --booth-key - booth auth key file
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported(
        "--force", "--booth-conf", "--name", "--booth-key"
    )
    if not arg_list:
        raise CmdLineInputError
    lib.booth.config_ticket_add(
        arg_list[0],
        KeyValueParser(arg_list[1:]).get_unique(),
        instance_name=modifiers.get("--name"),
        allow_unknown_options=modifiers.get("--force"),
    )


def config_ticket_remove(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    add ticket to current configuration

    Options:
      * --booth-conf - booth config file
      * --booth-key - booth auth key file
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--booth-conf", "--name", "--booth-key")
    if len(arg_list) != 1:
        raise CmdLineInputError
    lib.booth.config_ticket_remove(
        arg_list[0],
        instance_name=modifiers.get("--name"),
    )


def enable_authfile(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --booth-conf - booth config file
      * --booth-key - booth auth key file
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--booth-conf", "--name", "--booth-key")
    if len(arg_list):
        raise CmdLineInputError()
    lib.booth.config_set_enable_authfile(instance_name=modifiers.get("--name"))


def enable_authfile_clean(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --booth-conf - booth config file
      * --booth-key - booth auth key file
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--booth-conf", "--name", "--booth-key")
    if len(arg_list):
        raise CmdLineInputError()
    lib.booth.config_unset_enable_authfile(
        instance_name=modifiers.get("--name")
    )


def _parse_ticket_operation(arg_list: Argv) -> tuple[str, Optional[str]]:
    site_ip = None
    if len(arg_list) == 2:
        site_ip = arg_list[1]
    elif len(arg_list) != 1:
        raise CmdLineInputError()
    ticket = arg_list[0]
    return ticket, site_ip


def ticket_revoke(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    ticket, site_ip = _parse_ticket_operation(arg_list)
    lib.booth.ticket_revoke(
        ticket, site_ip=site_ip, instance_name=modifiers.get("--name")
    )


def ticket_grant(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    ticket, site_ip = _parse_ticket_operation(arg_list)
    lib.booth.ticket_grant(
        ticket, site_ip=site_ip, instance_name=modifiers.get("--name")
    )


def ticket_cleanup(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --name - name of a booth instance
    """
    if not arg_list:
        modifiers.ensure_only_supported("--name")
        lib.booth.ticket_cleanup_auto(instance_name=modifiers.get("--name"))
        return

    if len(arg_list) != 1:
        raise CmdLineInputError()
    modifiers.ensure_only_supported()
    lib.booth.ticket_cleanup(arg_list[0])


def ticket_unstandby(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options: None
    """
    modifiers.ensure_only_supported()
    if len(arg_list) != 1:
        raise CmdLineInputError()
    lib.booth.ticket_unstandby(arg_list[0])


def ticket_standby(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options: None
    """
    modifiers.ensure_only_supported()
    if len(arg_list) != 1:
        raise CmdLineInputError()
    lib.booth.ticket_standby(arg_list[0])


def create_in_cluster(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --force - allows to create booth resource even if its agent is not
        installed
      * -f - CIB file
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--force", "-f", "--name")
    if len(arg_list) != 2 or arg_list[0] != "ip":
        raise CmdLineInputError()
    lib.booth.create_in_cluster(
        arg_list[1],
        instance_name=modifiers.get("--name"),
        allow_absent_resource_agent=modifiers.get("--force"),
    )


def remove_from_cluster(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --force - allow remove of multiple, (deprecated) don't stop resources
      * -f - CIB file
      * --name - name of a booth instance
      * --no-stop - don't stop resources before deletion
      * --future - specifying '--force' does not skip resource stopping
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
        "-f", "--force", FUTURE_OPTION, "--name", "--no-stop"
    )
    modifiers.ensure_not_mutually_exclusive("-f", "--no-stop")
    if arg_list:
        raise CmdLineInputError()

    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(report_codes.FORCE)

    instance_name = modifiers.get("--name")

    if modifiers.is_specified("-f"):
        warn(
            "Resources are not going to be stopped before deletion because the "
            "command does not run on a live cluster"
        )
        lib.booth.remove_from_cluster(instance_name, force_flags)
        return

    dont_stop_me_now = modifiers.is_specified("--no-stop")
    if (
        not modifiers.is_specified(FUTURE_OPTION)
        and modifiers.is_specified("--force")
        and not dont_stop_me_now
    ):
        # deprecated after pcs-0.12.0
        deprecation_warning(
            "Using '--force' to skip resource stopping is deprecated and will "
            "be removed in a future release. Specify '--future' to switch to "
            "the future behavior and use '--no-stop' to skip resource stopping."
        )
        dont_stop_me_now = True

    if dont_stop_me_now:
        lib.booth.remove_from_cluster(instance_name, force_flags)
        return

    original_report_processor = lib.env.report_processor
    in_memory_report_processor = reports.processor.ReportProcessorInMemory()
    lib.env.report_processor = in_memory_report_processor

    try:
        lib.booth.remove_from_cluster(instance_name)

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

    resource_ids = lib.booth.get_resource_ids_from_cluster(instance_name)
    lib.resource.stop(resource_ids, force_flags)
    lib.cluster.wait_for_pcmk_idle(None)

    lib.booth.remove_from_cluster(instance_name, force_flags)


def restart(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --force - allow multiple
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--force", "--name")
    if arg_list:
        raise CmdLineInputError()

    lib.booth.restart(
        instance_name=modifiers.get("--name"),
        allow_multiple=modifiers.get("--force"),
    )


def sync(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --skip-offline - skip offline nodes
      * --name - name of a booth instance
      * --booth-conf - booth config file
      * --booth-key - booth authkey file
      * --request-timeout - HTTP timeout for file distribution
    """
    modifiers.ensure_only_supported(
        "--skip-offline",
        "--name",
        "--booth-conf",
        "--booth-key",
        "--request-timeout",
    )
    if arg_list:
        raise CmdLineInputError()
    lib.booth.config_sync(
        instance_name=modifiers.get("--name"),
        skip_offline_nodes=modifiers.get("--skip-offline"),
    )


def enable(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.enable_booth(instance_name=modifiers.get("--name"))


def disable(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.disable_booth(instance_name=modifiers.get("--name"))


def start(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.start_booth(instance_name=modifiers.get("--name"))


def stop(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.stop_booth(instance_name=modifiers.get("--name"))


def pull(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --name - name of a booth instance
      * --request-timeout - HTTP timeout for file distribution
    """
    modifiers.ensure_only_supported("--name", "--request-timeout")
    if len(arg_list) != 1:
        raise CmdLineInputError()
    lib.booth.pull_config(
        arg_list[0],
        instance_name=modifiers.get("--name"),
    )


def status(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --name - name of booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    booth_status = lib.booth.get_status(instance_name=modifiers.get("--name"))
    if booth_status.get("ticket"):
        print("TICKETS:")
        print(booth_status["ticket"])
    if booth_status.get("peers"):
        print("PEERS:")
        print(booth_status["peers"])
    if booth_status.get("status"):
        print("DAEMON STATUS:")
        print(booth_status["status"])

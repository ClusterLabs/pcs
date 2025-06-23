import json
from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import (
    format_cmd_list,
    lines_to_str,
    smart_wrap_text,
)
from pcs.cli.common.parse_args import (
    FUTURE_OPTION,
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    Argv,
    InputModifiers,
    KeyValueParser,
    ensure_unique_args,
    wait_to_timeout,
)
from pcs.cli.reports.output import (
    deprecation_warning,
    process_library_reports,
    warn,
)
from pcs.cli.resource.common import (
    check_is_not_stonith,
    get_resource_status_msg,
)
from pcs.cli.resource.output import (
    ResourcesConfigurationFacade,
    resources_to_cmd,
    resources_to_text,
)
from pcs.common import reports
from pcs.common.interface import dto
from pcs.common.pacemaker.resource.list import (
    CibResourcesDto,
    get_all_resources_ids,
    get_stonith_resources_ids,
)
from pcs.common.str_tools import format_list, format_plural
from pcs.lib.errors import LibraryError


def config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    output = config_common(lib, argv, modifiers, stonith=False)
    if output:
        print(output)


def config_common(
    lib: Any, argv: Argv, modifiers: InputModifiers, stonith: bool
) -> str:
    """
    Also used by stonith commands.

    Options:
      * -f - CIB file
      * --output-format - supported formats: text, cmd, json
    """
    modifiers.ensure_only_supported("-f", output_format_supported=True)
    resources_facade = (
        ResourcesConfigurationFacade.from_resources_dto(
            lib.resource.get_configured_resources()
        )
        .filter_stonith(stonith)
        .filter_resources(argv)
    )
    output_format = modifiers.get_output_format()
    if output_format == OUTPUT_FORMAT_VALUE_CMD:
        output = format_cmd_list(
            [" \\\n".join(cmd) for cmd in resources_to_cmd(resources_facade)]
        )
    elif output_format == OUTPUT_FORMAT_VALUE_JSON:
        output = json.dumps(
            dto.to_dict(
                CibResourcesDto(
                    primitives=resources_facade.primitives,
                    clones=resources_facade.clones,
                    groups=resources_facade.groups,
                    bundles=resources_facade.bundles,
                )
            )
        )
    else:
        output = lines_to_str(
            smart_wrap_text(resources_to_text(resources_facade))
        )
    return output


def meta(lib: Any, argv: list[str], modifiers: InputModifiers) -> None:
    """
    Options:
      * --force - override editing connection attributes for guest nodes
      * --wait - wait for cluster to reach steady state
      * -f
    """
    modifiers.ensure_only_supported("-f", "--force", "--wait")
    modifiers.ensure_not_mutually_exclusive("-f", "--wait")
    wait_timeout = wait_to_timeout(modifiers.get("--wait"))
    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    if not argv:
        raise CmdLineInputError()
    resource_id = argv.pop(0)
    check_is_not_stonith(lib, [resource_id], "pcs stonith meta")
    meta_attrs_dict = KeyValueParser(argv).get_unique()

    lib.resource.update_meta(resource_id, meta_attrs_dict, force_flags)

    if wait_timeout >= 0:
        deprecation_warning(reports.messages.ResourceWaitDeprecated().message)
        lib.cluster.wait_for_pcmk_idle(wait_timeout)
        print(get_resource_status_msg(lib, resource_id))


def remove(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --force - turn validation errors into warnings, (derecated) skip
                  resource stopping
      * --no-stop - don't stop resource before deletion
      * --future - specifying '--force' does not skip resource stopping
    """
    modifiers.ensure_only_supported("-f", "--force", FUTURE_OPTION, "--no-stop")

    if not argv:
        raise CmdLineInputError()
    ensure_unique_args(argv)

    resources_to_remove = set(argv)
    resources_dto = lib.resource.get_configured_resources()
    missing_ids = resources_to_remove - get_all_resources_ids(resources_dto)
    if missing_ids:
        raise CmdLineInputError(
            "Unable to find {resource}: {id_list}".format(
                resource=format_plural(missing_ids, "resource"),
                id_list=format_list(missing_ids),
            )
        )

    stonith_ids = resources_to_remove & get_stonith_resources_ids(resources_dto)
    if stonith_ids:
        raise CmdLineInputError(
            (
                "This command cannot remove stonith {resource}: {id_list}. Use "
                "'pcs stonith remove' instead."
            ).format(
                resource=format_plural(stonith_ids, "resource"),
                id_list=format_list(stonith_ids),
            )
        )

    force_flags = set()
    if modifiers.is_specified("--force"):
        force_flags.add(reports.codes.FORCE)

    if modifiers.is_specified("-f"):
        warn(
            "Resources are not going to be stopped before deletion because the "
            "command does not run on a live cluster"
        )
        lib.cib.remove_elements(resources_to_remove, force_flags)
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
        lib.cib.remove_elements(resources_to_remove, force_flags)
        return

    original_report_processor = lib.env.report_processor
    in_memory_report_processor = reports.processor.ReportProcessorInMemory()
    lib.env.report_processor = in_memory_report_processor

    try:
        # call without force flags the first time, so we really catch the
        # validation errors without deleting anything even when --force
        # was specified
        lib.cib.remove_elements(resources_to_remove)

        # the resources were successfully removed, but we still need to print
        # out the reports, since there could be INFO or DEBUG reports
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

        # if there are other errors than CANNOT_REMOVE_RESOURCES_NOT_STOPPED or
        # errors that would be forced, we can exit, since it does not make sense
        # to try stopping and removing the resources again
        if reports.has_errors(filtered_reports) or e.output or e.args:
            if filtered_reports:
                process_library_reports(
                    filtered_reports,
                    include_debug=modifiers.is_specified("--debug"),
                    exit_on_error=False,
                )
            raise e

    lib.env.report_processor = original_report_processor

    lib.resource.stop(resources_to_remove, force_flags)
    lib.cluster.wait_for_pcmk_idle(None)

    lib.cib.remove_elements(resources_to_remove, force_flags)


def _process_reports(
    report_list: reports.ReportItemList, force_flags: reports.types.ForceFlags
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

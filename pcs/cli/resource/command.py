import json
from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import (
    format_cmd_list,
    lines_to_str,
    smart_wrap_text,
)
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    Argv,
    InputModifiers,
    KeyValueParser,
    wait_to_timeout,
)
from pcs.cli.reports.output import deprecation_warning
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
from pcs.common.pacemaker.resource.list import CibResourcesDto


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

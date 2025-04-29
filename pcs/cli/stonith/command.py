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
from pcs.cli.reports.output import deprecation_warning, warn
from pcs.cli.resource import command as resource_cmd
from pcs.cli.resource.common import get_resource_status_msg
from pcs.cli.stonith.common import check_is_stonith
from pcs.cli.stonith.levels.output import (
    stonith_level_config_to_cmd,
    stonith_level_config_to_text,
)
from pcs.common import reports
from pcs.common.str_tools import indent


def config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --output-format - supported formats: text, cmd, json
      * -f CIB file
    """
    output_format = modifiers.get_output_format()
    output = resource_cmd.config_common(lib, argv, modifiers, stonith=True)

    if output_format == OUTPUT_FORMAT_VALUE_JSON:
        # JSON output format does not include fencing levels because it would
        # change the current JSON structure and break existing user tooling
        warn(
            "Fencing levels are not included because this command could only "
            "export stonith configuration previously. This cannot be changed "
            "to avoid breaking existing tooling. To export fencing levels, run "
            "'pcs stonith level config --output-format=json'"
        )
        print(output)
        return

    fencing_topology_dto = lib.fencing_topology.get_config_dto()
    if output_format == OUTPUT_FORMAT_VALUE_CMD:
        # we can look at the output of config_common as one command
        output = format_cmd_list(
            [output, *stonith_level_config_to_cmd(fencing_topology_dto)]
        )
    else:
        text_output = stonith_level_config_to_text(fencing_topology_dto)
        if text_output:
            output += "\n\nFencing Levels:\n" + lines_to_str(
                smart_wrap_text(indent(text_output))
            )

    if output:
        print(output)


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
    check_is_stonith(lib, [resource_id], "pcs resource meta")
    meta_attrs_dict = KeyValueParser(argv).get_unique()

    lib.resource.update_meta(resource_id, meta_attrs_dict, force_flags)

    if wait_timeout >= 0:
        deprecation_warning(reports.messages.ResourceWaitDeprecated().message)
        lib.cluster.wait_for_pcmk_idle(wait_timeout)
        print(get_resource_status_msg(lib, resource_id))

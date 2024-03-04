from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
    ensure_unique_args,
    parse_typed_arg,
)
from pcs.cli.reports.output import deprecation_warning
from pcs.cli.reports.preprocessor import (
    get_duplicate_constraint_exists_preprocessor,
)
from pcs.common import (
    const,
    reports,
)
from pcs.common.pacemaker.constraint import get_all_location_constraints_ids
from pcs.common.str_tools import format_list

RESOURCE_TYPE_RESOURCE = "resource"
RESOURCE_TYPE_REGEXP = "regexp"
_RESOURCE_TYPE_MAP = {
    RESOURCE_TYPE_RESOURCE: const.RESOURCE_ID_TYPE_PLAIN,
    RESOURCE_TYPE_REGEXP: const.RESOURCE_ID_TYPE_REGEXP,
}


def remove(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
    """
    # deprecated since pcs-0.11.7
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs constraint delete' or 'pcs constraint remove' "
        "instead."
    )
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()
    ensure_unique_args(argv)
    missing_ids = set(argv) - get_all_location_constraints_ids(
        lib.constraint.get_config(evaluate_rules=False)
    )
    if missing_ids:
        raise CmdLineInputError(
            f"Unable to find location constraints: {format_list(missing_ids)}"
        )
    lib.cib.remove_elements(argv)


def _extract_rule_options(
    argv: Argv, extract_constraint_options: bool = True
) -> tuple[dict[str, str], dict[str, str]]:
    rule_options: dict[str, str] = {}
    constraint_options: dict[str, str] = {}

    name_to_result = {
        "id": rule_options,
        "role": rule_options,
        "score": rule_options,
        "score-attribute": rule_options,
    }
    if extract_constraint_options:
        name_to_result["constraint-id"] = constraint_options
        name_to_result["resource-discovery"] = constraint_options

    while argv:
        found = False
        argument = argv.pop(0)
        for name, result in name_to_result.items():
            if argument.startswith(name + "="):
                result[name] = argument.split("=", 1)[1]
                found = True
                break
        if not found:
            argv.insert(0, argument)
            break

    if "constraint-id" in constraint_options:
        constraint_options["id"] = constraint_options["constraint-id"]
        del constraint_options["constraint-id"]

    return rule_options, constraint_options


def create_with_rule(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --force - allow constraint on any resource type, allow duplicate
        constraints
    """
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) < 3:
        raise CmdLineInputError()

    force_flags = set()
    if modifiers.get("--force"):
        force_flags.add(reports.codes.FORCE)

    argv = argv[:]
    rsc_type, rsc_value = parse_typed_arg(
        argv.pop(0), list(_RESOURCE_TYPE_MAP.keys()), RESOURCE_TYPE_RESOURCE
    )
    if argv[0] == "rule":
        argv.pop(0)
    else:
        raise CmdLineInputError()
    rule_options, constraint_options = _extract_rule_options(argv)

    lib.env.report_processor.set_report_item_preprocessor(
        get_duplicate_constraint_exists_preprocessor(lib)
    )
    lib.constraint_location.create_plain_with_rule(
        _RESOURCE_TYPE_MAP[rsc_type],
        rsc_value,
        " ".join(argv),
        rule_options,
        constraint_options,
        force_flags,
    )


def rule_add(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --force - allow duplicate constraints
    """
    modifiers.ensure_only_supported("-f", "--force")
    if not argv:
        raise CmdLineInputError()

    force_flags = set()
    if modifiers.get("--force"):
        force_flags.add(reports.codes.FORCE)

    argv = argv[:]
    constraint_id = argv.pop(0)
    rule_options, _ = _extract_rule_options(
        argv, extract_constraint_options=False
    )

    lib.env.report_processor.set_report_item_preprocessor(
        get_duplicate_constraint_exists_preprocessor(lib)
    )
    lib.constraint_location.add_rule_to_constraint(
        constraint_id,
        " ".join(argv),
        rule_options,
        force_flags,
    )

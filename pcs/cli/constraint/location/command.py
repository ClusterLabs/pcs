from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
    KeyValueParser,
    get_rule_str,
    parse_typed_arg,
)
from pcs.cli.reports.preprocessor import (
    get_duplicate_constraint_exists_preprocessor,
)
from pcs.common import const, reports

RESOURCE_TYPE_RESOURCE = "resource"
RESOURCE_TYPE_REGEXP = "regexp"
_RESOURCE_TYPE_MAP = {
    RESOURCE_TYPE_RESOURCE: const.RESOURCE_ID_TYPE_PLAIN,
    RESOURCE_TYPE_REGEXP: const.RESOURCE_ID_TYPE_REGEXP,
}
_RULE_OPTION_NAMES = ("id", "role", "score", "score-attribute")
_CONSTRAINT_ID_CLI_NAME = "constraint-id"


def _split_rule_and_constraint_options(
    argv: Argv,
) -> tuple[dict[str, str], dict[str, str]]:
    option_args: Argv = []
    while argv and len(argv[0].split()) == 1 and "=" in argv[0]:
        option_args.append(argv.pop(0))

    all_options = KeyValueParser(option_args).get_unique()

    rule_options: dict[str, str] = {}
    constraint_options: dict[str, str] = {}
    for name, value in all_options.items():
        if name in _RULE_OPTION_NAMES:
            rule_options[name] = value
        elif name == _CONSTRAINT_ID_CLI_NAME:
            constraint_options["id"] = value
        else:
            constraint_options[name] = value
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

    argv = argv[:]  # eliminate side-effect - do not modify the original argv
    rsc_type, rsc_value = parse_typed_arg(
        argv.pop(0), list(_RESOURCE_TYPE_MAP.keys()), RESOURCE_TYPE_RESOURCE
    )
    if argv[0] == "rule":
        argv.pop(0)
    else:
        raise CmdLineInputError()
    rule_options, constraint_options = _split_rule_and_constraint_options(argv)
    rule_str = get_rule_str(argv) or ""

    lib.env.report_processor.set_report_item_preprocessor(
        get_duplicate_constraint_exists_preprocessor(lib)
    )
    lib.constraint_location.create_plain_with_rule(
        _RESOURCE_TYPE_MAP[rsc_type],
        rsc_value,
        rule_str,
        rule_options,
        constraint_options,
        force_flags,
    )

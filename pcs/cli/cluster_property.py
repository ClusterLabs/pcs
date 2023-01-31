from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    InputModifiers,
    ensure_unique_args,
    prepare_options,
)
from pcs.common import reports
from pcs.common.types import StringSequence


def set_property(
    lib: Any, argv: StringSequence, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --force - allow unknown options
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "-f")
    if not argv:
        raise CmdLineInputError()
    force_flags = set()
    if modifiers.get("--force"):
        force_flags.add(reports.codes.FORCE)
    cluster_options = prepare_options(argv)
    lib.cluster_property.set_properties(cluster_options, force_flags)


def unset_property(
    lib: Any, argv: StringSequence, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --force - no error when removing not existing properties
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "-f")
    if not argv:
        raise CmdLineInputError()
    force_flags = set()
    if modifiers.get("--force"):
        force_flags.add(reports.codes.FORCE)
    else:
        ensure_unique_args(argv)

    lib.cluster_property.set_properties(
        {name: "" for name in argv}, force_flags
    )

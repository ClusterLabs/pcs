from typing import (
    Any,
    Sequence,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers

def set_recovery_site(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options: None
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError()
    lib.dr.set_recovery_site(argv[0])

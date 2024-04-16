from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
)


def wait_for_pcmk_idle(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()

    if len(argv) > 1:
        raise CmdLineInputError()

    lib.cluster.wait_for_pcmk_idle(argv[0] if argv else None)

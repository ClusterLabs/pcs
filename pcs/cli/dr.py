from typing import (
    Any,
    Sequence,
)

from pcs.cli.common.console_report import error
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.common.dr import DrSiteStatusDto

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

def status(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * --full - show full details, node attributes and failcount
      * --hide-inactive - hide inactive resources
      * --request-timeout - HTTP timeout for node authorization check
    """
    modifiers.ensure_only_supported(
        "--full", "--hide-inactive", "--request-timeout",
    )
    if argv:
        raise CmdLineInputError()

    status_list_raw = lib.dr.status_all_sites_plaintext(
        hide_inactive_resources=modifiers.get("--hide-inactive"),
        verbose=modifiers.get("--full"),
    )
    try:
        status_list = [
            DrSiteStatusDto.from_dict(status_raw)
            for status_raw in status_list_raw
        ]
    except (KeyError, TypeError, ValueError):
        raise error(
            "Unable to communicate with pcsd, received response:\n"
                f"{status_list_raw}"
        )

    has_errors = False
    plaintext_parts = []
    for site_status in status_list:
        plaintext_parts.append(
            "--- {local_remote} cluster - {role} site ---".format(
                local_remote=("Local" if site_status.local_site else "Remote"),
                role=site_status.site_role.capitalize()
            )
        )
        if site_status.status_successfully_obtained:
            plaintext_parts.append(site_status.status_plaintext.strip())
            plaintext_parts.extend(["", ""])
        else:
            has_errors = True
            plaintext_parts.extend([
                "Error: Unable to get status of the cluster from any node",
                ""
            ])
    print("\n".join(plaintext_parts).strip())
    if has_errors:
        raise error("Unable to get status of all sites")

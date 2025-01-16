from typing import (
    Any,
    List,
)

from dacite import DaciteError

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.cli.reports.output import error
from pcs.common.dr import (
    DrConfigDto,
    DrConfigSiteDto,
    DrSiteStatusDto,
)
from pcs.common.interface import dto
from pcs.common.reports import codes as report_codes
from pcs.common.str_tools import indent
from pcs.common.types import StringSequence


def config(
    lib: Any,
    argv: StringSequence,
    modifiers: InputModifiers,
) -> None:
    """
    Options: None
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    config_raw = lib.dr.get_config()
    try:
        config_dto = dto.from_dict(DrConfigDto, config_raw)
    except (
        KeyError,
        TypeError,
        ValueError,
        DaciteError,
        dto.PayloadConversionError,
    ) as e:
        raise error(
            f"Unable to communicate with pcsd, received response:\n{config_raw}"
        ) from e

    lines = ["Local site:"]
    lines.extend(indent(_config_site_lines(config_dto.local_site)))
    for site_dto in config_dto.remote_site_list:
        lines.append("Remote site:")
        lines.extend(indent(_config_site_lines(site_dto)))
    print("\n".join(lines))


def _config_site_lines(site_dto: DrConfigSiteDto) -> List[str]:
    lines = [f"Role: {site_dto.site_role.capitalize()}"]
    if site_dto.node_list:
        lines.append("Nodes:")
        lines.extend(indent(sorted([node.name for node in site_dto.node_list])))
    return lines


def set_recovery_site(
    lib: Any,
    argv: StringSequence,
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * --request-timeout - HTTP timeout for node authorization check
    """
    modifiers.ensure_only_supported("--request-timeout")
    if len(argv) != 1:
        raise CmdLineInputError()
    lib.dr.set_recovery_site(argv[0])


def status(
    lib: Any,
    argv: StringSequence,
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * --full - show full details, node attributes and failcount
      * --hide-inactive - hide inactive resources
      * --request-timeout - HTTP timeout for node authorization check
    """
    modifiers.ensure_only_supported(
        "--full",
        "--hide-inactive",
        "--request-timeout",
    )
    if argv:
        raise CmdLineInputError()

    status_list_raw = lib.dr.status_all_sites_plaintext(
        hide_inactive_resources=modifiers.get("--hide-inactive"),
        verbose=modifiers.get("--full"),
    )
    try:
        status_list = [
            dto.from_dict(DrSiteStatusDto, status_raw)
            for status_raw in status_list_raw
        ]
    except (
        KeyError,
        TypeError,
        ValueError,
        DaciteError,
        dto.PayloadConversionError,
    ) as e:
        raise error(
            "Unable to communicate with pcsd, received response:\n"
            f"{status_list_raw}"
        ) from e

    has_errors = False
    plaintext_parts = []
    for site_status in status_list:
        plaintext_parts.append(
            "--- {local_remote} cluster - {role} site ---".format(
                local_remote=("Local" if site_status.local_site else "Remote"),
                role=site_status.site_role.capitalize(),
            )
        )
        if site_status.status_successfully_obtained:
            plaintext_parts.append(site_status.status_plaintext.strip())
            plaintext_parts.extend(["", ""])
        else:
            has_errors = True
            plaintext_parts.extend(
                ["Error: Unable to get status of the cluster from any node", ""]
            )
    print("\n".join(plaintext_parts).strip())
    if has_errors:
        raise error("Unable to get status of all sites")


def destroy(
    lib: Any,
    argv: StringSequence,
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * --skip-offline - skip unreachable nodes (including missing auth token)
      * --request-timeout - HTTP timeout for node authorization check
    """
    modifiers.ensure_only_supported("--skip-offline", "--request-timeout")
    if argv:
        raise CmdLineInputError()
    force_flags = []
    if modifiers.get("--skip-offline"):
        force_flags.append(report_codes.SKIP_OFFLINE_NODES)
    lib.dr.destroy(force_flags=force_flags)

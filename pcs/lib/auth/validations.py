from dataclasses import asdict
from typing import Mapping, Sequence

from pcs import settings
from pcs.common import reports
from pcs.common.auth import HostAuthData, HostWithTokenAuthData
from pcs.common.host import Destination
from pcs.lib import validate

# TODO This is a temporary solution for validation of input "dto" data.
# What we really need is a validator for the input "dto" data - that it matches
# the dto structure (dacite does that for us) and that the structure complies
# to additional constraints, like a sequence cannot be empty, or some element of
# a sequence is not valid. The problem with the current solution is that the
# reports do not convey the information about which addr in which hostname is
# not valid.


def _validate_destinations(
    host_name: str, destinations: Sequence[Destination]
) -> reports.ReportItemList:
    report_list = []
    if not destinations:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "dest_list",
                    str(destinations),
                    f"non-empty list of destinations for node '{host_name}'",
                    cannot_be_empty=True,
                )
            )
        )
    for dest in destinations:
        report_list.extend(
            validate.ValidatorAll(
                [
                    validate.ValueNotEmpty(
                        "addr", f"address for node '{host_name}'"
                    ),
                    validate.ValuePortNumber(
                        "port", f"port for node '{host_name}'"
                    ),
                ]
            ).validate(asdict(dest))
        )

    return report_list


def validate_hosts_with_token(
    hosts: Mapping[str, HostWithTokenAuthData],
) -> reports.ReportItemList:
    report_list = []
    if not hosts:
        report_list.append(
            reports.ReportItem.error(reports.messages.NoHostSpecified())
        )
    for host_name, host_data in hosts.items():
        report_list.extend(
            validate.ValueNotEmpty("host name", "").validate(
                {"host name": host_name}
            )
        )
        report_list.extend(
            validate.ValidatorAll(
                [
                    # token is parsed in utils.get_token_from_file, where the
                    # token size is max 256 bytes to stay backwards compatible.
                    # library always gets the bytes as base64 encoded string
                    # max (~345 chars), so settings.pcsd_token_max_chars needs
                    # to be at least that big.
                    validate.ValueStringLength(
                        "token",
                        min_len=1,
                        max_len=settings.pcsd_token_max_chars,
                    ),
                ]
            ).validate(asdict(host_data))
        )
        report_list.extend(
            _validate_destinations(host_name, host_data.dest_list)
        )

    return report_list


def validate_hosts(
    hosts: Mapping[str, HostAuthData],
) -> reports.ReportItemList:
    report_list = []
    if not hosts:
        report_list.append(
            reports.ReportItem.error(reports.messages.NoHostSpecified())
        )
    for host_name, host_data in hosts.items():
        report_list.extend(
            validate.ValueNotEmpty("host name", "").validate(
                {"host name": host_name}
            )
        )

        report_list.extend(
            _validate_destinations(host_name, host_data.dest_list)
        )

    return report_list

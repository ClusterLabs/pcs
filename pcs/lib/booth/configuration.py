from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re

from pcs.lib.booth import reports
from pcs.lib.errors import LibraryError


def validate_participants(site_list, arbitrator_list):
    report = []

    if len(site_list) < 2:
        report.append(reports.booth_lack_of_sites(site_list))

    participants_list = site_list + arbitrator_list

    if len(participants_list) % 2 == 0:
        report.append(reports.booth_even_paticipants_num(
            len(participants_list)
        ))

    address_set = set()
    duplicate_addresses = []
    for address in participants_list:
        if address in address_set:
            duplicate_addresses.append(address)
        else:
            address_set.add(address)
    if duplicate_addresses:
        report.append(reports.booth_address_duplication(duplicate_addresses))

    if report:
        raise LibraryError(*report)

def build(booth_configuration):
    return (
        [
            "site = {0}".format(site)
            for site in sorted(booth_configuration["sites"])
        ]
        +
        [
            "arbitrator = {0}".format(arbitrator)
            for arbitrator in sorted(booth_configuration["arbitrators"])
        ]
    )

def parse(line_list):
    keywords = {
        "site": [],
        "arbitrator": [],
    }
    line_pattern = re.compile(
        r"^\s*({0})\s*=(.*)".format("|".join(keywords.keys()))
    )
    unexpected_lines = []
    for line in line_list:
        match = line_pattern.search(line)
        if match:
            if match.group(1) in list(keywords.keys()):
                keywords[match.group(1)].append(match.group(2).strip())
                continue
        unexpected_lines.append(line)
    if unexpected_lines:
        raise LibraryError(
            reports.booth_config_unexpected_lines(unexpected_lines)
        )
    return {
        "sites": keywords["site"],
        "arbitrators": keywords["arbitrator"],
    }

from collections import Counter
import re

from pcs.common import reports
from pcs.lib import validate
from pcs.lib.booth import constants


__TICKET_NAME_RE = re.compile(r"^[a-zA-Z0-9-]{1,63}$")


def check_instance_name(name):
    """
    Check that specified booth instance name is valid

    string name -- booth instance name
    """
    report_list = []
    if "/" in name:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.BoothInvalidName(
                    name, forbidden_characters="/"
                )
            )
        )
    return report_list


def create(site_list, arbitrator_list):
    """
    Validate creating a minimal booth config

    iterable site_list -- list of booth sites' addresses
    iterable arbitrator_list -- list of arbitrators' addresses
    """
    report_list = []
    peer_list = site_list + arbitrator_list

    if len(site_list) < 2:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.BoothLackOfSites(sorted(site_list))
            )
        )

    if len(peer_list) % 2 == 0:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.BoothEvenPeersNumber(len(peer_list))
            )
        )

    duplicate_addresses = {
        address for address, count in Counter(peer_list).items() if count > 1
    }
    if duplicate_addresses:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.BoothAddressDuplication(
                    sorted(duplicate_addresses)
                )
            )
        )

    return report_list


def add_ticket(
    conf_facade, ticket_name, ticket_options, allow_unknown_options=False
):
    """
    Validate adding a ticket to an existing booth config

    pcs.lib.booth.config_facade.ConfigFacade conf_facade -- a booth config
    string ticket_name -- the name of the ticket
    dict ticket_options -- ticket options
    bool allow_unknown_options -- if True, report unknown options as warnings
        instead of errors
    """
    return (
        validate_ticket_name(ticket_name)
        + _validate_ticket_unique(conf_facade, ticket_name)
        + _validate_ticket_options(ticket_options, allow_unknown_options)
    )


def remove_ticket(conf_facade, ticket_name):
    """
    Validate removing a ticket from an existing booth config

    pcs.lib.booth.config_facade.ConfigFacade conf_facade -- a booth config
    string ticket_name -- the name of the ticket
    """
    if not conf_facade.has_ticket(ticket_name):
        return [
            reports.ReportItem.error(
                reports.messages.BoothTicketDoesNotExist(ticket_name)
            )
        ]
    return []


def validate_ticket_name(ticket_name: str) -> reports.ReportItemList:
    if not __TICKET_NAME_RE.search(ticket_name):
        return [
            reports.ReportItem.error(
                reports.messages.BoothTicketNameInvalid(ticket_name)
            )
        ]
    return []


def _validate_ticket_unique(conf_facade, ticket_name):
    if conf_facade.has_ticket(ticket_name):
        return [
            reports.ReportItem.error(
                reports.messages.BoothTicketDuplicate(ticket_name)
            )
        ]
    return []


def _validate_ticket_options(options, allow_unknown_options):
    validator_list = [
        validate.NamesIn(
            constants.TICKET_KEYS,
            option_type="booth ticket",
            banned_name_list=constants.GLOBAL_KEYS,
            severity=reports.item.get_severity(
                reports.codes.FORCE, allow_unknown_options
            ),
        ),
    ] + [validate.ValueNotEmpty(option, None) for option in options]
    normalized_options = validate.values_to_pairs(
        options, lambda key, value: value.strip()
    )
    return validate.ValidatorAll(validator_list).validate(normalized_options)

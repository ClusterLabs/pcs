from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes as codes

def format_booth_default(value, template):
    return "" if value in ("booth", "", None) else template.format(value)

#Each value (callable taking report_item.info) returns string template.
#Optionaly the template can contain placehodler {force} for next processing.
#Placeholder {force} will be appended if is necessary and if is not presset
CODE_TO_MESSAGE_BUILDER_MAP = {
    codes.BOOTH_LACK_OF_SITES: lambda info:
        "lack of sites for booth configuration (need 2 at least): sites {0}"
        .format(", ".join(info["sites"]) if info["sites"] else "missing")
    ,

    codes.BOOTH_EVEN_PEERS_NUM: lambda info:
        "odd number of peers is required (entered {number} peers)"
        .format(**info)
    ,

    codes.BOOTH_ADDRESS_DUPLICATION: lambda info:
        "duplicate address for booth configuration: {0}"
        .format(", ".join(info["addresses"]))
    ,

    codes.BOOTH_CONFIG_UNEXPECTED_LINES: lambda info:
        "unexpected line appeard in config: \n{0}"
        .format("\n".join(info["line_list"]))
    ,

    codes.BOOTH_INVALID_NAME: lambda info:
        "booth name '{name}' is not valid ({reason})"
        .format(**info)
    ,

    codes.BOOTH_TICKET_NAME_INVALID: lambda info:
        "booth ticket name '{0}' is not valid, use alphanumeric chars or dash"
        .format(info["ticket_name"])
    ,

    codes.BOOTH_TICKET_DUPLICATE: lambda info:
        "booth ticket name '{ticket_name}' already exists in configuration"
        .format(**info)
    ,

    codes.BOOTH_TICKET_DOES_NOT_EXIST: lambda info:
        "booth ticket name '{ticket_name}' does not exist"
        .format(**info)
    ,

    codes.BOOTH_ALREADY_IN_CIB: lambda info:
        "booth instance '{name}' is already created as cluster resource"
        .format(**info)
    ,

    codes.BOOTH_NOT_EXISTS_IN_CIB: lambda info:
        "booth instance '{name}' not found in cib"
        .format(**info)
    ,

    codes.BOOTH_CONFIG_IS_USED: lambda info:
        "booth instance '{0}' is used{1}".format(
            info["name"],
            " {0}".format(info["detail"]) if info["detail"] else "",
        )
    ,

    codes.BOOTH_MULTIPLE_TIMES_IN_CIB: lambda info:
        "found more than one booth instance '{name}' in cib"
        .format(**info)
    ,

    codes.BOOTH_CONFIG_DISTRIBUTION_STARTED: lambda info:
        "Sending booth configuration to cluster nodes..."
    ,

    codes.BOOTH_CONFIG_ACCEPTED_BY_NODE: lambda info:
        "{node_info}Booth config{desc} saved.".format(
            desc=(
                "" if info["name_list"] in [None, [], ["booth"]]
                else "(s) ({0})".format(", ".join(info["name_list"]))
            ),
            node_info="{0}: ".format(info["node"]) if info["node"] else ""
        )
    ,

    codes.BOOTH_CONFIG_DISTRIBUTION_NODE_ERROR: lambda info:
        "Unable to save booth config{desc} on node '{node}': {reason}".format(
            desc=format_booth_default(info["name"], " ({0})"),
            **info
        )
    ,

    codes.BOOTH_CONFIG_READ_ERROR: lambda info:
        "Unable to read booth config{desc}.".format(
            desc=format_booth_default(info["name"], " ({0})")
        )
    ,

    codes.BOOTH_FETCHING_CONFIG_FROM_NODE: lambda info:
        "Fetching booth config{desc} from node '{node}'...".format(
            desc=format_booth_default(info["config"], " '{0}'"),
            **info
        )
    ,

    codes.BOOTH_DAEMON_STATUS_ERROR: lambda info:
        "unable to get status of booth daemon: {reason}".format(**info)
    ,

    codes.BOOTH_TICKET_STATUS_ERROR: "unable to get status of booth tickets",

    codes.BOOTH_PEERS_STATUS_ERROR: "unable to get status of booth peers",

    codes.BOOTH_CANNOT_DETERMINE_LOCAL_SITE_IP: lambda info:
        "cannot determine local site ip, please specify site parameter"
    ,

    codes.BOOTH_TICKET_OPERATION_FAILED: lambda info:
        (
            "unable to {operation} booth ticket '{ticket_name}'"
            " for site '{site_ip}', reason: {reason}"
        ).format(**info)

    ,

    codes.BOOTH_SKIPPING_CONFIG: lambda info:
        "Skipping config file '{config_file}': {reason}".format(**info)
    ,

    codes.BOOTH_CANNOT_IDENTIFY_KEYFILE:
        "cannot identify authfile in booth configuration"
    ,
}

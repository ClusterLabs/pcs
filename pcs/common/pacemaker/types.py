from typing import cast


class CibResourceDiscovery(str):
    ALWAYS = cast("CibResourceDiscovery", "always")
    NEVER = cast("CibResourceDiscovery", "never")
    EXCLUSIVE = cast("CibResourceDiscovery", "exclusive")


class CibResourceSetOrdering(str):
    GROUP = cast("CibResourceSetOrdering", "group")
    LISTED = cast("CibResourceSetOrdering", "listed")


class CibResourceSetOrderType(str):
    OPTIONAL = cast("CibResourceSetOrderType", "Optional")
    MANDATORY = cast("CibResourceSetOrderType", "Mandatory")
    SERIALIZE = cast("CibResourceSetOrderType", "Serialize")


class CibTicketLossPolicy(str):
    STOP = cast("CibTicketLossPolicy", "stop")
    DEMOTE = cast("CibTicketLossPolicy", "demote")
    FENCE = cast("CibTicketLossPolicy", "fence")
    FREEZE = cast("CibTicketLossPolicy", "freeze")

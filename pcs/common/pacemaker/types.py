from typing import cast


class CibResourceDiscovery(str):
    __slots__ = ()
    ALWAYS = cast("CibResourceDiscovery", "always")
    NEVER = cast("CibResourceDiscovery", "never")
    EXCLUSIVE = cast("CibResourceDiscovery", "exclusive")


class CibResourceSetOrdering(str):
    __slots__ = ()
    GROUP = cast("CibResourceSetOrdering", "group")
    LISTED = cast("CibResourceSetOrdering", "listed")


class CibResourceSetOrderType(str):
    __slots__ = ()
    OPTIONAL = cast("CibResourceSetOrderType", "Optional")
    MANDATORY = cast("CibResourceSetOrderType", "Mandatory")
    SERIALIZE = cast("CibResourceSetOrderType", "Serialize")


class CibTicketLossPolicy(str):
    __slots__ = ()
    STOP = cast("CibTicketLossPolicy", "stop")
    DEMOTE = cast("CibTicketLossPolicy", "demote")
    FENCE = cast("CibTicketLossPolicy", "fence")
    FREEZE = cast("CibTicketLossPolicy", "freeze")

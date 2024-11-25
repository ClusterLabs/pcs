from typing import (
    Optional,
    cast,
)

from lxml.etree import _Element

from pcs.lib.booth.constants import DEFAULT_INSTANCE_NAME

_BOOTH_ATTRIBUTE = "booth-cfg-name"


def get_booth_ticket_names(
    cib: _Element, booth_instance: Optional[str] = None
) -> list[str]:
    """
    Return names of booth tickets present in CIB for the specified booth
    instance

    cib -- element representing the CIB
    booth_instance -- name of the booth instance, default instance name is used
        if name is not provided
    """
    return cast(
        list[str],
        cib.xpath(
            f"status/tickets/ticket_state[@{_BOOTH_ATTRIBUTE}=$instance]/@id",
            instance=booth_instance or DEFAULT_INSTANCE_NAME,
        ),
    )


def get_ticket_names(cib: _Element) -> list[str]:
    """
    Return names of all tickets present in CIB

    cib -- element representing the CIB
    """
    return cast(list[str], cib.xpath("status/tickets/ticket_state/@id"))

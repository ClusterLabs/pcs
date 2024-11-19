from typing import cast

from lxml.etree import _Element


def get_ticket_names(cib: _Element) -> list[str]:
    """
    Return names of all tickets present in CIB

    cib -- element representing the CIB
    """
    return cast(list[str], cib.xpath("status/tickets/ticket_state/@id"))

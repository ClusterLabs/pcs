import os.path
from dataclasses import dataclass
from typing import cast

from lxml import etree
from lxml.etree import _Element

from pcs import settings
from pcs.common.tools import xml_fromstring
from pcs.common.types import StringSequence


@dataclass(frozen=True)
class Status:
    code: int
    message: str
    errors: StringSequence


def get_api_result_dom(xml: str) -> _Element:
    # raises etree.XMLSyntaxError and etree.DocumentInvalid
    rng = settings.pacemaker_api_result_schema
    dom = xml_fromstring(xml)
    if os.path.isfile(rng):
        etree.RelaxNG(file=rng).assertValid(dom)
    return dom


def get_status_from_api_result(dom: _Element) -> Status:
    errors = []
    status_el = cast(_Element, dom.find("./status"))
    errors_el = status_el.find("errors")
    if errors_el is not None:
        errors = [
            str((error_el.text or "")).strip()
            for error_el in errors_el.iterfind("error")
        ]
    return Status(
        code=int(str(status_el.get("code"))),
        message=str(status_el.get("message")),
        errors=errors,
    )

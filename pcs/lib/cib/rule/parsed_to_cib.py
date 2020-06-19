from typing import cast
from xml.etree.ElementTree import Element

from lxml import etree
from lxml.etree import _Element

from pcs.lib.cib.tools import (
    IdProvider,
    create_subelement_id,
)

from .expression_part import (
    BoolExpr,
    OpExpr,
    RscExpr,
    RuleExprPart,
)


def export(
    parent_el: Element, id_provider: IdProvider, expr_tree: BoolExpr,
) -> Element:
    """
    Export parsed rule to a CIB element

    parent_el -- element to place the rule into
    id_provider -- elements' ids generator
    expr_tree -- parsed rule tree root
    """
    element = __export_part(parent_el, expr_tree, id_provider)
    # Add score only to the top level rule element (which is represented by
    # BoolExpr class). This is achieved by this function not being called for
    # child nodes.
    # TODO This was implemented originaly only for rules in resource and
    # operation defaults. In those cases, score is the only rule attribute and
    # it is always INFINITY. Once this code is used for other rules, modify
    # this behavior as needed.
    if isinstance(expr_tree, BoolExpr):
        element.set("score", "INFINITY")
    return element


def __export_part(
    parent_el: Element, expr_tree: RuleExprPart, id_provider: IdProvider
) -> Element:
    part_export_map = {
        BoolExpr: __export_bool,
        OpExpr: __export_op,
        RscExpr: __export_rsc,
    }
    func = part_export_map[type(expr_tree)]
    # mypy doesn't handle this dynamic call
    return func(parent_el, expr_tree, id_provider)  # type: ignore


def __export_bool(
    parent_el: Element, boolean: BoolExpr, id_provider: IdProvider
) -> Element:
    element = etree.SubElement(
        cast(_Element, parent_el),
        "rule",
        {
            "id": create_subelement_id(parent_el, "rule", id_provider),
            "boolean-op": boolean.operator.lower(),
        },
    )
    for child in boolean.children:
        __export_part(cast(Element, element), child, id_provider)
    return cast(Element, element)


def __export_op(
    parent_el: Element, op: OpExpr, id_provider: IdProvider
) -> Element:
    element = etree.SubElement(
        cast(_Element, parent_el),
        "op_expression",
        {
            "id": create_subelement_id(parent_el, f"op-{op.name}", id_provider),
            "name": op.name,
        },
    )
    if op.interval:
        element.attrib["interval"] = op.interval
    return cast(Element, element)


def __export_rsc(
    parent_el: Element, rsc: RscExpr, id_provider: IdProvider
) -> Element:
    id_part = "-".join(filter(None, [rsc.standard, rsc.provider, rsc.type]))
    element = etree.SubElement(
        cast(_Element, parent_el),
        "rsc_expression",
        {"id": create_subelement_id(parent_el, f"rsc-{id_part}", id_provider)},
    )
    if rsc.standard:
        element.attrib["class"] = rsc.standard
    if rsc.provider:
        element.attrib["provider"] = rsc.provider
    if rsc.type:
        element.attrib["type"] = rsc.type
    return cast(Element, element)

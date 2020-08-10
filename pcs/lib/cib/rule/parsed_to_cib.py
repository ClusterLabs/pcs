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
    parent_el: _Element, id_provider: IdProvider, expr_tree: BoolExpr,
) -> _Element:
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
        element.attrib["score"] = "INFINITY"
    return element


def __export_part(
    parent_el: _Element, expr_tree: RuleExprPart, id_provider: IdProvider
) -> _Element:
    part_export_map = {
        BoolExpr: __export_bool,
        OpExpr: __export_op,
        RscExpr: __export_rsc,
    }
    func = part_export_map[type(expr_tree)]
    # mypy doesn't handle this dynamic call
    return func(parent_el, expr_tree, id_provider)  # type: ignore


def __export_bool(
    parent_el: _Element, boolean: BoolExpr, id_provider: IdProvider
) -> _Element:
    element = etree.SubElement(
        parent_el,
        "rule",
        {
            "id": create_subelement_id(parent_el, "rule", id_provider),
            "boolean-op": boolean.operator.lower(),
            # Score or score-attribute is required for nested rules, otherwise
            # the CIB is not valid. Pacemaker doesn't use the score of nested
            # rules. Score for the top rule, which is used by pacemaker, is
            # supposed to be set in the export function above.
            "score": "0",
        },
    )
    for child in boolean.children:
        __export_part(element, child, id_provider)
    return element


def __export_op(
    parent_el: _Element, op: OpExpr, id_provider: IdProvider
) -> _Element:
    element = etree.SubElement(
        parent_el,
        "op_expression",
        {
            "id": create_subelement_id(parent_el, f"op-{op.name}", id_provider),
            "name": op.name,
        },
    )
    if op.interval:
        element.attrib["interval"] = op.interval
    return element


def __export_rsc(
    parent_el: _Element, rsc: RscExpr, id_provider: IdProvider
) -> _Element:
    id_part = "-".join(filter(None, [rsc.standard, rsc.provider, rsc.type]))
    element = etree.SubElement(
        parent_el,
        "rsc_expression",
        {"id": create_subelement_id(parent_el, f"rsc-{id_part}", id_provider)},
    )
    if rsc.standard:
        element.attrib["class"] = rsc.standard
    if rsc.provider:
        element.attrib["provider"] = rsc.provider
    if rsc.type:
        element.attrib["type"] = rsc.type
    return element

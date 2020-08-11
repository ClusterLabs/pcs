from lxml import etree
from lxml.etree import _Element

from pcs.lib.cib.tools import (
    IdProvider,
    create_subelement_id,
)

from .expression_part import (
    DATE_OP_GT,
    DATE_OP_LT,
    BoolExpr,
    DateInRangeExpr,
    DatespecExpr,
    DateUnaryExpr,
    NodeAttrExpr,
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
        DateInRangeExpr: __export_date_inrange,
        DatespecExpr: __export_datespec,
        DateUnaryExpr: __export_date_unary,
        NodeAttrExpr: __export_node_attr,
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


def __export_date_inrange(
    parent_el: _Element, expr: DateInRangeExpr, id_provider: IdProvider
) -> _Element:
    element = etree.SubElement(
        parent_el,
        "date_expression",
        {
            "id": create_subelement_id(parent_el, "expr", id_provider),
            "operation": "in_range",
        },
    )
    if expr.date_start:
        element.attrib["start"] = expr.date_start
    if expr.duration_parts:
        duration_attrs = dict(expr.duration_parts)
        duration_attrs["id"] = create_subelement_id(
            element, "duration", id_provider
        )
        etree.SubElement(element, "duration", duration_attrs)
    elif expr.date_end:
        element.attrib["end"] = expr.date_end
    return element


def __export_datespec(
    parent_el: _Element, expr: DatespecExpr, id_provider: IdProvider
) -> _Element:
    element = etree.SubElement(
        parent_el,
        "date_expression",
        {
            "id": create_subelement_id(parent_el, "expr", id_provider),
            "operation": "date_spec",
        },
    )
    datespec_attrs = dict(expr.date_parts)
    datespec_attrs["id"] = create_subelement_id(
        element, "datespec", id_provider
    )
    etree.SubElement(element, "date_spec", datespec_attrs)
    return element


def __export_date_unary(
    parent_el: _Element, expr: DateUnaryExpr, id_provider: IdProvider
) -> _Element:
    element = etree.SubElement(
        parent_el,
        "date_expression",
        {
            "id": create_subelement_id(parent_el, "expr", id_provider),
            "operation": expr.operator.lower(),
        },
    )
    if expr.operator == DATE_OP_GT:
        element.attrib["start"] = expr.date
    elif expr.operator == DATE_OP_LT:
        element.attrib["end"] = expr.date
    return element


def __export_node_attr(
    parent_el: _Element, expr: NodeAttrExpr, id_provider: IdProvider
) -> _Element:
    element = etree.SubElement(
        parent_el,
        "expression",
        {
            "id": create_subelement_id(parent_el, "expr", id_provider),
            "attribute": expr.attr_name,
            "operation": expr.operator.lower(),
        },
    )
    if expr.attr_value:
        element.attrib["value"] = expr.attr_value
    if expr.attr_type:
        element.attrib["type"] = expr.attr_type.lower()
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

from typing import Optional

from lxml import etree
from lxml.etree import _Element

from pcs.common.tools import Version
from pcs.lib.cib.tools import (
    IdProvider,
    create_subelement_id,
)

from .expression_part import (
    DATE_OP_GT,
    DATE_OP_LT,
    NODE_ATTR_TYPE_INTEGER,
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
    parent_el: _Element,
    id_provider: IdProvider,
    cib_schema_version: Version,
    expr_tree: BoolExpr,
    rule_id: Optional[str] = None,
) -> _Element:
    """
    Export parsed rule to a CIB element

    parent_el -- element to place the rule into
    id_provider -- elements' ids generator
    cib_schema_version -- makes the export compatible with specified CIB schema
    expr_tree -- parsed rule tree root
    rule_id -- custom rule element id
    """
    return _Exporter(id_provider, cib_schema_version).export(
        parent_el, expr_tree, rule_id
    )


class _Exporter:
    def __init__(
        self,
        id_provider: IdProvider,
        cib_schema_version: Version,
    ):
        self.part_export_map = {
            BoolExpr: self._export_bool,
            DateInRangeExpr: self._export_date_inrange,
            DatespecExpr: self._export_datespec,
            DateUnaryExpr: self._export_date_unary,
            NodeAttrExpr: self._export_node_attr,
            OpExpr: self._export_op,
            RscExpr: self._export_rsc,
        }
        self.id_provider = id_provider
        self.cib_schema_version = cib_schema_version

    def export(
        self,
        parent_el: _Element,
        expr_tree: BoolExpr,
        rule_id: Optional[str] = None,
    ) -> _Element:
        element = self._export_part(parent_el, expr_tree, rule_id)
        # Adjust top level rule element (which is represented by BoolExpr
        # class). This is achieved by this function not being called for child
        # nodes.
        # Remove score set by self._export_part. It is a responsibility of the
        # caller to set it properly.
        element.attrib.pop("score", "")
        return element

    def _export_part(
        self,
        parent_el: _Element,
        expr_tree: RuleExprPart,
        id_: Optional[str] = None,
    ) -> _Element:
        func = self.part_export_map[type(expr_tree)]
        # pylint: disable=comparison-with-callable
        if func == self._export_bool:
            # mypy doesn't handle this dynamic call
            return func(parent_el, expr_tree, id_)  # type: ignore
        # mypy doesn't handle this dynamic call
        return func(parent_el, expr_tree)  # type: ignore

    def _export_bool(
        self, parent_el: _Element, boolean: BoolExpr, id_: Optional[str] = None
    ) -> _Element:
        element = etree.SubElement(
            parent_el,
            "rule",
            {
                "id": (
                    id_
                    if id_
                    else create_subelement_id(
                        parent_el, "rule", self.id_provider
                    )
                ),
                "boolean-op": boolean.operator.lower(),
            },
        )
        if self.cib_schema_version < Version(3, 9, 0):
            # Score or score-attribute is required for nested rules,
            # otherwise the CIB is not valid. Pacemaker doesn't use the
            # score of nested rules. Score for the top rule, which is used
            # by pacemaker, is supposed to be set by the caller of the
            # export function.
            element.attrib["score"] = "0"
        for child in boolean.children:
            self._export_part(element, child)
        return element

    def _export_date_inrange(
        self, parent_el: _Element, expr: DateInRangeExpr
    ) -> _Element:
        element = etree.SubElement(
            parent_el,
            "date_expression",
            {
                "id": create_subelement_id(parent_el, "expr", self.id_provider),
                "operation": "in_range",
            },
        )
        if expr.date_start:
            element.attrib["start"] = expr.date_start
        if expr.duration_parts:
            duration_attrs = dict(expr.duration_parts)
            duration_attrs["id"] = create_subelement_id(
                element, "duration", self.id_provider
            )
            etree.SubElement(element, "duration", duration_attrs)
        elif expr.date_end:
            element.attrib["end"] = expr.date_end
        return element

    def _export_datespec(
        self, parent_el: _Element, expr: DatespecExpr
    ) -> _Element:
        element = etree.SubElement(
            parent_el,
            "date_expression",
            {
                "id": create_subelement_id(parent_el, "expr", self.id_provider),
                "operation": "date_spec",
            },
        )
        datespec_attrs = dict(expr.date_parts)
        datespec_attrs["id"] = create_subelement_id(
            element, "datespec", self.id_provider
        )
        etree.SubElement(element, "date_spec", datespec_attrs)
        return element

    def _export_date_unary(
        self, parent_el: _Element, expr: DateUnaryExpr
    ) -> _Element:
        element = etree.SubElement(
            parent_el,
            "date_expression",
            {
                "id": create_subelement_id(parent_el, "expr", self.id_provider),
                "operation": expr.operator.lower(),
            },
        )
        if expr.operator == DATE_OP_GT:
            element.attrib["start"] = expr.date
        elif expr.operator == DATE_OP_LT:
            element.attrib["end"] = expr.date
        return element

    def _export_node_attr(
        self, parent_el: _Element, expr: NodeAttrExpr
    ) -> _Element:
        element = etree.SubElement(
            parent_el,
            "expression",
            {
                "id": create_subelement_id(parent_el, "expr", self.id_provider),
                "attribute": expr.attr_name,
                "operation": expr.operator.lower(),
            },
        )
        if expr.attr_value:
            element.attrib["value"] = expr.attr_value
        if expr.attr_type:
            # rhbz#1869399
            # Pcs was always accepting 'integer', while CIB was only supporting
            # 'number' (and 'string' and 'version'). Pacemaker was documenting
            # it as 'integer' and was treating it as integer (not float). With
            # CIB schema 3.5.0, both 'integer' and 'number' are accepted by
            # CIB. For older schemas, we turn 'integer' to 'number'.
            if (
                self.cib_schema_version < Version(3, 5, 0)
                and expr.attr_type == NODE_ATTR_TYPE_INTEGER
            ):
                element.attrib["type"] = "number"
            else:
                element.attrib["type"] = expr.attr_type.lower()
        return element

    def _export_op(self, parent_el: _Element, op: OpExpr) -> _Element:
        element = etree.SubElement(
            parent_el,
            "op_expression",
            {
                "id": create_subelement_id(
                    parent_el, f"op-{op.name}", self.id_provider
                ),
                "name": op.name,
            },
        )
        if op.interval:
            element.attrib["interval"] = op.interval
        return element

    def _export_rsc(self, parent_el: _Element, rsc: RscExpr) -> _Element:
        id_part = "-".join(filter(None, [rsc.standard, rsc.provider, rsc.type]))
        element = etree.SubElement(
            parent_el,
            "rsc_expression",
            {
                "id": create_subelement_id(
                    parent_el, f"rsc-{id_part}", self.id_provider
                )
            },
        )
        if rsc.standard:
            element.attrib["class"] = rsc.standard
        if rsc.provider:
            element.attrib["provider"] = rsc.provider
        if rsc.type:
            element.attrib["type"] = rsc.type
        return element

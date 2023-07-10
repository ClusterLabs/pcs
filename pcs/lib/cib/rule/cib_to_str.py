import re
from typing import (
    Dict,
    cast,
)

from lxml.etree import _Element

from pcs.common.str_tools import (
    format_name_value_list,
    quote,
)
from pcs.lib.xml_tools import export_attributes


class RuleToStr:
    """
    Export a rule XML element to a string which creates the same element
    """

    _date_separators_re = re.compile(r"\s*([TZ:.+-])\s*")

    def __init__(self) -> None:
        # The cache prevents evaluating subtrees repeatedly.
        self._cache: Dict[str, str] = {}

    def get_str(self, rule_part_element: _Element) -> str:
        """
        Export a rule XML element to a string which creates the same element

        rule_part_element -- a rule or rule expression element to be exported
        """
        element_id = str(rule_part_element.get("id", ""))
        if element_id not in self._cache:
            self._cache[element_id] = self._export_element(rule_part_element)
        return self._cache[element_id]

    def _export_element(self, rule_el: _Element) -> str:
        return self._tag_to_export[str(rule_el.tag)](self, rule_el)

    @staticmethod
    def _attrs_to_str(el: _Element) -> str:
        return " ".join(
            format_name_value_list(
                sorted(export_attributes(el, with_id=False).items())
            )
        )

    @staticmethod
    def _date_to_str(date: str) -> str:
        # remove spaces around separators
        result = re.sub(RuleToStr._date_separators_re, r"\1", date)
        # if there are any spaces left, replace the first one with T
        result = re.sub(r"\s+", "T", result, count=1)
        # keep all other spaces in place
        # the date wouldn't be valid, but there is nothing more we can do
        return result

    def _rule_to_str(self, rule_el: _Element) -> str:
        # "and" is a documented pacemaker default
        # https://clusterlabs.org/pacemaker/doc/en-US/Pacemaker/2.0/html-single/Pacemaker_Explained/index.html#_rule_properties
        boolean_op = str(rule_el.get("boolean-op", "and"))
        string_parts = []
        for child in cast(_Element, rule_el.xpath(self._xpath_for_export)):
            if child.tag == "rule":
                string_parts.append(f"({self.get_str(child)})")
            else:
                string_parts.append(self.get_str(child))
        return f" {boolean_op} ".join(string_parts)

    def _simple_expr_to_str(self, expr_el: _Element) -> str:
        # pylint - all *_to_str methods must have the same interface
        # pylint: disable=no-self-use
        string_parts = []
        if "value" in expr_el.attrib:
            # "attribute" and "operation" are defined as mandatory in CIB schema
            string_parts.extend(
                [
                    str(expr_el.get("attribute", "")),
                    str(expr_el.get("operation", "")),
                ]
            )
            if "type" in expr_el.attrib:
                string_parts.append(str(expr_el.get("type", "")))
            string_parts.append(quote(str(expr_el.get("value", "")), " "))
        else:
            # "attribute" and "operation" are defined as mandatory in CIB schema
            string_parts.extend(
                [
                    str(expr_el.get("operation", "")),
                    str(expr_el.get("attribute", "")),
                ]
            )
        return " ".join(string_parts)

    def _date_expr_to_str(self, expr_el: _Element) -> str:
        date_spec = expr_el.find("./date_spec")
        duration = expr_el.find("./duration")

        string_parts = []
        # "operation" is defined as mandatory in CIB schema
        operation = expr_el.get("operation", "")
        if operation == "date_spec":
            string_parts.append("date-spec")
            if date_spec is not None:
                string_parts.append(self._attrs_to_str(date_spec))
        elif operation == "in_range":
            string_parts.extend(["date", "in_range"])
            # CIB schema allows "start" + "duration" or optional "start" + "end"
            if "start" in expr_el.attrib:
                string_parts.append(self._date_to_str(expr_el.get("start", "")))
            string_parts.append("to")
            if "end" in expr_el.attrib:
                string_parts.append(self._date_to_str(expr_el.get("end", "")))
            if duration is not None:
                string_parts.append("duration")
                string_parts.append(self._attrs_to_str(duration))
        else:
            # CIB schema allows operation=="gt" + "start" or
            # operation=="lt" + "end"
            string_parts.extend(["date", str(expr_el.get("operation", ""))])
            if "start" in expr_el.attrib:
                string_parts.append(self._date_to_str(expr_el.get("start", "")))
            if "end" in expr_el.attrib:
                string_parts.append(self._date_to_str(expr_el.get("end", "")))
        return " ".join(string_parts)

    def _op_expr_to_str(self, expr_el: _Element) -> str:
        # pylint - all *_to_str methods must have the same interface
        # pylint: disable=no-self-use
        string_parts = ["op", str(expr_el.get("name", ""))]
        if "interval" in expr_el.attrib:
            string_parts.append(
                "interval={0}".format(expr_el.get("interval", ""))
            )
        return " ".join(string_parts)

    def _rsc_expr_to_str(self, expr_el: _Element) -> str:
        # pylint - all *_to_str methods must have the same interface
        # pylint: disable=no-self-use
        return "resource " + ":".join(
            [
                str(expr_el.get(attr, ""))
                for attr in ["class", "provider", "type"]
            ]
        )

    _tag_to_export = {
        "rule": _rule_to_str,
        "expression": _simple_expr_to_str,
        "date_expression": _date_expr_to_str,
        "op_expression": _op_expr_to_str,
        "rsc_expression": _rsc_expr_to_str,
    }

    _xpath_for_export = "./*[{export_tags}]".format(
        export_tags=" or ".join(f"self::{tag}" for tag in _tag_to_export)
    )

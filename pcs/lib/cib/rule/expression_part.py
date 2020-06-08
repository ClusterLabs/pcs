"""
Provides classes used as nodes of a semantic tree of a parsed rule expression.
"""
from typing import (
    NewType,
    Optional,
    Sequence,
)

from pcs.common.str_tools import indent


class RuleExprPart:
    def _token_str(self) -> str:
        raise NotImplementedError()


class SimpleExpr(RuleExprPart):
    """
    Base for all RuleExprPart classes not holding other RuleExprPart objects.
    """

    _attrs: Sequence[str] = tuple()

    def __str__(self):
        parts = [self._token_str()]
        for attr in self._attrs:
            value = getattr(self, attr)
            if value is not None:
                parts.append(f"{attr}={value}")
        return " ".join(parts)

    def _token_str(self) -> str:
        raise NotImplementedError()


BoolOperator = NewType("BoolOperator", str)
BOOL_AND = BoolOperator("AND")
BOOL_OR = BoolOperator("OR")


class BoolExpr(RuleExprPart):
    """
    Represents rule combining SimpleExpr objects by AND or OR operation.
    """

    def __init__(
        self, operator: BoolOperator, expr_part_list: Sequence[RuleExprPart]
    ):
        self.operator = operator
        self.children = expr_part_list

    def _token_str(self) -> str:
        return f"BOOL {self.operator}"

    def __str__(self) -> str:
        str_args = []
        for arg in self.children:
            str_args.extend(str(arg).splitlines())
        return "\n".join([self._token_str()] + indent(str_args))


class RscExpr(SimpleExpr):
    """
    Represents resource expression in a rule.
    """

    _attrs = ("standard", "provider", "type")

    def __init__(
        self,
        r_standard: Optional[str],
        r_provider: Optional[str],
        r_type: Optional[str],
    ):
        self.standard = r_standard
        self.provider = r_provider
        self.type = r_type

    def _token_str(self) -> str:
        return "RESOURCE"


class OpExpr(SimpleExpr):
    """
    Represents op expression in a rule.
    """

    _attrs = ("name", "interval")

    def __init__(self, name: str, interval: Optional[str]):
        self.name = name
        self.interval = interval

    def _token_str(self) -> str:
        return "OPERATION"

"""
Provides classes used as nodes of a semantic tree of a parsed rule expression.
"""
from dataclasses import dataclass
from typing import (
    NewType,
    Optional,
    Sequence,
)


class RuleExprPart:
    pass


BoolOperator = NewType("BoolOperator", str)
BOOL_AND = BoolOperator("AND")
BOOL_OR = BoolOperator("OR")


@dataclass(frozen=True)
class BoolExpr(RuleExprPart):
    """
    Represents a rule combining RuleExprPart objects by AND or OR operation.
    """

    operator: BoolOperator
    children: Sequence[RuleExprPart]


@dataclass(frozen=True)
class RscExpr(RuleExprPart):
    """
    Represents a resource expression in a rule.
    """

    standard: Optional[str]
    provider: Optional[str]
    type: Optional[str]


@dataclass(frozen=True)
class OpExpr(RuleExprPart):
    """
    Represents an op expression in a rule.
    """

    name: str
    interval: Optional[str]

"""
Provides classes used as nodes of a semantic tree of a parsed rule expression.
"""

from dataclasses import dataclass
from typing import (
    NewType,
    Optional,
    Sequence,
)

BoolOperator = NewType("BoolOperator", str)
BOOL_AND = BoolOperator("AND")
BOOL_OR = BoolOperator("OR")

DateUnaryOperator = NewType("DateUnaryOperator", str)
DATE_OP_GT = DateUnaryOperator("GT")
DATE_OP_LT = DateUnaryOperator("LT")

NodeAttrOperator = NewType("NodeAttrOperator", str)
NODE_ATTR_OP_DEFINED = NodeAttrOperator("DEFINED")
NODE_ATTR_OP_NOT_DEFINED = NodeAttrOperator("NOT_DEFINED")
NODE_ATTR_OP_EQ = NodeAttrOperator("EQ")
NODE_ATTR_OP_NE = NodeAttrOperator("NE")
NODE_ATTR_OP_GTE = NodeAttrOperator("GTE")
NODE_ATTR_OP_GT = NodeAttrOperator("GT")
NODE_ATTR_OP_LTE = NodeAttrOperator("LTE")
NODE_ATTR_OP_LT = NodeAttrOperator("LT")

NodeAttrType = NewType("NodeAttrType", str)
NODE_ATTR_TYPE_INTEGER = NodeAttrType("INTEGER")
NODE_ATTR_TYPE_NUMBER = NodeAttrType("NUMBER")
NODE_ATTR_TYPE_STRING = NodeAttrType("STRING")
NODE_ATTR_TYPE_VERSION = NodeAttrType("VERSION")


class RuleExprPart:
    pass


@dataclass(frozen=True)
class BoolExpr(RuleExprPart):
    """
    Represents a rule combining RuleExprPart objects by AND or OR operation.
    """

    operator: BoolOperator
    children: Sequence[RuleExprPart]


@dataclass(frozen=True)
class DateUnaryExpr(RuleExprPart):
    """
    Represents a date expression with a single date
    """

    operator: DateUnaryOperator
    date: str


@dataclass(frozen=True)
class DateInRangeExpr(RuleExprPart):
    """
    Represents a 'date in range' expression
    """

    date_start: Optional[str]
    date_end: Optional[str]
    duration_parts: Optional[Sequence[tuple[str, str]]]


@dataclass(frozen=True)
class DatespecExpr(RuleExprPart):
    """
    Represents a date-spec expression
    """

    date_parts: Sequence[tuple[str, str]]


@dataclass(frozen=True)
class NodeAttrExpr(RuleExprPart):
    """
    Represents a node attribute expression in a rule.
    """

    operator: NodeAttrOperator
    attr_name: str
    attr_value: Optional[str]
    attr_type: Optional[NodeAttrType]


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

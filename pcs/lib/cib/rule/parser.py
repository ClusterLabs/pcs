from typing import (
    Any,
    Iterator,
    Optional,
    Tuple,
)

import pyparsing

from .expression_part import (
    BOOL_AND,
    BOOL_OR,
    NODE_ATTR_TYPE_NUMBER,
    NODE_ATTR_TYPE_STRING,
    NODE_ATTR_TYPE_VERSION,
    NODE_ATTR_OP_DEFINED,
    NODE_ATTR_OP_NOT_DEFINED,
    NODE_ATTR_OP_EQ,
    NODE_ATTR_OP_NE,
    NODE_ATTR_OP_GTE,
    NODE_ATTR_OP_GT,
    NODE_ATTR_OP_LTE,
    NODE_ATTR_OP_LT,
    BoolExpr,
    NodeAttrExpr,
    OpExpr,
    RscExpr,
    RuleExprPart,
)

_token_to_node_expr_unary_op = {
    "defined": NODE_ATTR_OP_DEFINED,
    "not_defined": NODE_ATTR_OP_NOT_DEFINED,
}

_token_to_node_expr_binary_op = {
    "eq": NODE_ATTR_OP_EQ,
    "ne": NODE_ATTR_OP_NE,
    "gte": NODE_ATTR_OP_GTE,
    "gt": NODE_ATTR_OP_GT,
    "lte": NODE_ATTR_OP_LTE,
    "lt": NODE_ATTR_OP_LT,
}

_token_to_node_expr_type = {
    # TODO deprecated, remove
    # in old pcs versions, "number" was called "integer"
    "integer": NODE_ATTR_TYPE_NUMBER,
    "number": NODE_ATTR_TYPE_NUMBER,
    "string": NODE_ATTR_TYPE_STRING,
    "version": NODE_ATTR_TYPE_VERSION,
}


pyparsing.ParserElement.enablePackrat()


class RuleParseError(Exception):
    def __init__(
        self,
        rule_string: str,
        rule_line: str,
        lineno: int,
        colno: int,
        pos: int,
        msg: str,
    ):
        super().__init__()
        self.rule_string = rule_string
        self.rule_line = rule_line
        self.lineno = lineno
        self.colno = colno
        self.pos = pos
        self.msg = msg


def parse_rule(
    rule_string: str, allow_rsc_expr: bool = False, allow_op_expr: bool = False
) -> BoolExpr:
    """
    Parse a rule string and return a corresponding semantic tree

    rule_string -- the whole rule expression
    allow_rsc_expr -- allow resource expressions in the rule
    allow_op_expr -- allow resource operation expressions in the rule
    """
    if not rule_string:
        return BoolExpr(BOOL_AND, [])

    try:
        parsed = __get_rule_parser(
            allow_rsc_expr=allow_rsc_expr, allow_op_expr=allow_op_expr
        ).parseString(rule_string, parseAll=True)[0]
    except pyparsing.ParseException as e:
        raise RuleParseError(
            rule_string, e.line, e.lineno, e.col, e.loc, e.args[2],
        )

    if not isinstance(parsed, BoolExpr):
        # If we only got a representation on an inner rule element instead of a
        # rule element itself, wrap the result in a default AND-rule. (There is
        # only one expression so "and" vs. "or" doesn't really matter.)
        parsed = BoolExpr(BOOL_AND, [parsed])

    return parsed


def __operator_operands(
    token_list: pyparsing.ParseResults,
) -> Iterator[Tuple[Any, Any]]:
    # See pyparsing examples
    # https://github.com/pyparsing/pyparsing/blob/master/examples/eval_arith.py
    token_iterator = iter(token_list)
    while True:
        try:
            yield (next(token_iterator), next(token_iterator))
        except StopIteration:
            break


def __build_bool_tree(token_list: pyparsing.ParseResults) -> RuleExprPart:
    # See pyparsing examples
    # https://github.com/pyparsing/pyparsing/blob/master/examples/eval_arith.py
    token_to_operator = {
        "and": BOOL_AND,
        "or": BOOL_OR,
    }
    operand_left = token_list[0][0]
    last_operator: Optional[str] = None
    operand_list = []
    for operator, operand_right in __operator_operands(token_list[0][1:]):
        # In each iteration, we get a bool_op ("and" or "or") and the right
        # operand.
        if last_operator == operator or last_operator is None:
            # If we got the same operator as last time (or this is the first
            # one), stack all the operads so we can put them all into one
            # BoolExpr class.
            operand_list.append(operand_right)
        else:
            # The operator has changed. Put all the stacked operands into the
            # correct BoolExpr class and start the stacking again. The created
            # class is the left operand of the current operator.
            operand_left = BoolExpr(
                token_to_operator[last_operator], [operand_left] + operand_list
            )
            operand_list = [operand_right]
        last_operator = operator
    if operand_list and last_operator:
        # Use any of the remaining stacked operands.
        operand_left = BoolExpr(
            token_to_operator[last_operator], [operand_left] + operand_list
        )
    return operand_left


def __build_node_attr_unary_expr(
    parse_result: pyparsing.ParseResults,
) -> RuleExprPart:
    # Those attrs are defined by setResultsName in node_attr_unary_expr grammar
    # rule
    return NodeAttrExpr(
        _token_to_node_expr_unary_op[parse_result.operator],
        parse_result.attr_name,
        None,
        None,
    )


def __build_node_attr_binary_expr(
    parse_result: pyparsing.ParseResults,
) -> RuleExprPart:
    # TODO report when deprecated "integer" is used
    # Those attrs are defined by setResultsName in node_attr_binary_expr
    # grammar rule
    return NodeAttrExpr(
        _token_to_node_expr_binary_op[parse_result.operator],
        parse_result.attr_name,
        parse_result.attr_value,
        _token_to_node_expr_type[parse_result.attr_type]
        if parse_result.attr_type
        else None,
    )


def __build_op_expr(parse_result: pyparsing.ParseResults) -> RuleExprPart:
    # Those attrs are defined by setResultsName in op_expr grammar rule
    return OpExpr(
        parse_result.name,
        # pyparsing-2.1.0 puts "interval_value" into parse_result.interval as
        # defined in the grammar AND it also puts "interval_value" into
        # parse_result. pyparsing-2.4.0 only puts "interval_value" into
        # parse_result. Not sure why, maybe it's a bug, maybe it's intentional.
        parse_result.interval_value if parse_result.interval_value else None,
    )


def __build_rsc_expr(parse_result: pyparsing.ParseResults) -> RuleExprPart:
    # Those attrs are defined by the regexp in rsc_expr grammar rule
    return RscExpr(
        parse_result.standard, parse_result.provider, parse_result.type
    )


def __get_rule_parser(
    allow_rsc_expr: bool = False, allow_op_expr: bool = False
) -> pyparsing.ParserElement:
    # This function defines the rule grammar

    # How to add new rule expressions:
    #   1 Create new grammar rules in a way similar to existing rsc_expr and
    #     op_expr. Use setName for better description of a grammar when printed.
    #     Use setResultsName for an easy access to parsed parts.
    #   2 Create new classes in expression_part module, probably one for each
    #     type of expression. Those are data containers holding the parsed data
    #     independent of the parser.
    #   3 Create builders for the new classes and connect them to created
    #     grammar rules using setParseAction.
    #   4 Add the new expressions into simple_expr_list.
    #   5 Test and debug the whole thing.

    node_attr_unary_expr = pyparsing.And(
        [
            # operator
            pyparsing.Or(
                [
                    pyparsing.CaselessKeyword(op)
                    for op in _token_to_node_expr_unary_op
                ]
            ).setResultsName("operator"),
            # attribute name
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets).
            pyparsing.Regex(r"[^\s()]+")
            .setName("<attribute name>")
            .setResultsName("attr_name"),
        ]
    )
    node_attr_unary_expr.setParseAction(__build_node_attr_unary_expr)

    node_attr_binary_expr = pyparsing.And(
        [
            # attribute name
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets).
            pyparsing.Regex(r"[^\s()]+")
            .setName("<attribute name>")
            .setResultsName("attr_name"),
            # operator
            pyparsing.Or(
                [
                    pyparsing.CaselessKeyword(op)
                    for op in _token_to_node_expr_binary_op
                ]
            ).setResultsName("operator"),
            # attribute type
            pyparsing.Optional(
                pyparsing.Or(
                    [
                        pyparsing.CaselessKeyword(type_)
                        for type_ in _token_to_node_expr_type
                    ]
                )
            )
            .setName("<attribute type>")
            .setResultsName("attr_type"),
            # attribute value
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets).
            pyparsing.Regex(r"[^\s()]+")
            .setName("<attribute value>")
            .setResultsName("attr_value"),
        ]
    )
    node_attr_binary_expr.setParseAction(__build_node_attr_binary_expr)

    rsc_expr = pyparsing.And(
        [
            pyparsing.CaselessKeyword("resource"),
            # resource name
            # Up to three parts seperated by ":". The parts can contain any
            # characters except whitespace (token separator), ":" (parts
            # separator) and "()" (brackets).
            pyparsing.Regex(
                r"(?P<standard>[^\s:()]+)?:(?P<provider>[^\s:()]+)?:(?P<type>[^\s:()]+)?"
            ).setName("<resource name>"),
        ]
    )
    rsc_expr.setParseAction(__build_rsc_expr)

    op_interval = pyparsing.And(
        [
            pyparsing.CaselessKeyword("interval"),
            # no spaces allowed around the "="
            pyparsing.Literal("=").leaveWhitespace(),
            # interval value: number followed by a time unit, no spaces allowed
            # between the number and the unit thanks to Combine being used
            pyparsing.Combine(
                pyparsing.And(
                    [
                        pyparsing.Word(pyparsing.nums),
                        pyparsing.Optional(pyparsing.Word(pyparsing.alphas)),
                    ]
                )
            )
            .setName("<integer>[<time unit>]")
            .setResultsName("interval_value"),
        ]
    )
    op_expr = pyparsing.And(
        [
            pyparsing.CaselessKeyword("op"),
            # operation name
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets). Operations are defined in
            # agents' metadata which we do not have access to (e.g. when the
            # user sets operation "my_check" and doesn't even specify agent's
            # name).
            pyparsing.Regex(r"[^\s()]+")
            .setName("<operation name>")
            .setResultsName("name"),
            pyparsing.Optional(op_interval).setResultsName("interval"),
        ]
    )
    op_expr.setParseAction(__build_op_expr)

    simple_expr_list = [node_attr_unary_expr, node_attr_binary_expr]
    if allow_rsc_expr:
        simple_expr_list.append(rsc_expr)
    if allow_op_expr:
        simple_expr_list.append(op_expr)
    simple_expr = pyparsing.Or(simple_expr_list)

    # See pyparsing examples
    # https://github.com/pyparsing/pyparsing/blob/master/examples/simpleBool.py
    # https://github.com/pyparsing/pyparsing/blob/master/examples/eval_arith.py
    bool_operator = pyparsing.Or(
        [pyparsing.CaselessKeyword("and"), pyparsing.CaselessKeyword("or")]
    )
    bool_expr = pyparsing.infixNotation(
        simple_expr,
        # By putting both "and" and "or" in one tuple we say they have the same
        # priority. This is consistent with legacy pcs parsers. And it is how
        # it should be, they work as a glue between "simple_expr"s.
        [(bool_operator, 2, pyparsing.opAssoc.LEFT, __build_bool_tree)],
    )

    return pyparsing.Or([bool_expr, simple_expr])

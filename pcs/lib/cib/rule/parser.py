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
    DATE_OP_GT,
    DATE_OP_LT,
    NODE_ATTR_OP_DEFINED,
    NODE_ATTR_OP_EQ,
    NODE_ATTR_OP_GT,
    NODE_ATTR_OP_GTE,
    NODE_ATTR_OP_LT,
    NODE_ATTR_OP_LTE,
    NODE_ATTR_OP_NE,
    NODE_ATTR_OP_NOT_DEFINED,
    NODE_ATTR_TYPE_INTEGER,
    NODE_ATTR_TYPE_NUMBER,
    NODE_ATTR_TYPE_STRING,
    NODE_ATTR_TYPE_VERSION,
    BoolExpr,
    DateInRangeExpr,
    DatespecExpr,
    DateUnaryExpr,
    NodeAttrExpr,
    OpExpr,
    RscExpr,
    RuleExprPart,
)

_token_to_date_expr_unary_op = {
    "gt": DATE_OP_GT,
    "lt": DATE_OP_LT,
}

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
    "integer": NODE_ATTR_TYPE_INTEGER,
    "number": NODE_ATTR_TYPE_NUMBER,
    "string": NODE_ATTR_TYPE_STRING,
    "version": NODE_ATTR_TYPE_VERSION,
}


pyparsing.ParserElement.enable_packrat()


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


def parse_rule(rule_string: str) -> BoolExpr:
    """
    Parse a rule string and return a corresponding semantic tree

    rule_string -- the whole rule expression
    """
    if not rule_string:
        return BoolExpr(BOOL_AND, [])

    try:
        parsed = __get_rule_parser().parse_string(rule_string, parse_all=True)[
            0
        ]
    except pyparsing.ParseException as e:
        raise RuleParseError(
            rule_string,
            e.line,
            e.lineno,
            e.col,
            e.loc,
            e.args[2] if e.args[2] is not None else "",
        ) from e

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


def __build_date_unary_expr(
    parse_result: pyparsing.ParseResults,
) -> RuleExprPart:
    # Those attrs are defined by setResultsName in date_unary_expr grammar rule
    return DateUnaryExpr(
        _token_to_date_expr_unary_op[parse_result.operator], parse_result.date
    )


def __build_date_inrange_expr(
    parse_result: pyparsing.ParseResults,
) -> RuleExprPart:
    # Those attrs are defined by setResultsName in date_inrange_expr grammar
    # rule
    return DateInRangeExpr(
        parse_result.date1 if parse_result.date1 else None,
        parse_result.date2 if parse_result.date2 else None,
        parse_result.duration.as_list() if parse_result.duration else None,
    )


def __build_datespec_expr(parse_result: pyparsing.ParseResults) -> RuleExprPart:
    # Those attrs are defined by setResultsName in datespec_expr grammar rule
    return DatespecExpr(
        parse_result.datespec.as_list() if parse_result.datespec else None
    )


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
    # Those attrs are defined by setResultsName in node_attr_binary_expr
    # grammar rule
    return NodeAttrExpr(
        _token_to_node_expr_binary_op[parse_result.operator],
        parse_result.attr_name,
        parse_result.attr_value,
        (
            _token_to_node_expr_type[parse_result.attr_type]
            if parse_result.attr_type
            else None
        ),
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


def __get_date_common_parser_part() -> pyparsing.ParserElement:
    # This only checks for <name>=<value> and returns a list of 2-tuples. The
    # tuples are expected to be validated elsewhere.
    return pyparsing.OneOrMore(
        pyparsing.Group(
            pyparsing.And(
                [
                    # name
                    # It can by any string containing any characters except
                    # whitespace (token separator), '=' (name-value separator)
                    # and "()" (brackets).
                    pyparsing.Regex(r"[^=\s()]+").set_name("<date part name>"),
                    # Suppress is needed so the '=' doesn't pollute the
                    # resulting structure produced automatically by pyparsing.
                    pyparsing.Suppress(
                        # no spaces allowed around the "="
                        pyparsing.Literal("=").leave_whitespace()
                    ),
                    # value
                    # It can by any string containing any characters except
                    # whitespace (token separator) and "()" (brackets).
                    pyparsing.Regex(r"[^\s()]+").set_name("<date part value>"),
                ]
            )
        )
    )


def __get_rule_parser() -> pyparsing.ParserElement:
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
    #   4 Add the new expressions into simple_expr definition.
    #   5 Test and debug the whole thing.

    node_attr_unary_expr = pyparsing.And(
        [
            # operator
            pyparsing.Or(
                [
                    pyparsing.CaselessKeyword(op).set_name(f"'{op}'")
                    for op in _token_to_node_expr_unary_op
                ]
            ).set_results_name("operator"),
            # attribute name
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets).
            pyparsing.Regex(r"[^\s()]+")
            .set_name("<attribute name>")
            .set_results_name("attr_name"),
        ]
    )
    node_attr_unary_expr.set_parse_action(__build_node_attr_unary_expr)

    node_attr_binary_expr = pyparsing.And(
        [
            # attribute name
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets).
            pyparsing.Regex(r"[^\s()]+")
            .set_name("<attribute name>")
            .set_results_name("attr_name"),
            # operator
            pyparsing.Or(
                [
                    pyparsing.CaselessKeyword(op).set_name(f"'{op}'")
                    for op in _token_to_node_expr_binary_op
                ]
            ).set_results_name("operator"),
            # attribute type
            pyparsing.Optional(
                pyparsing.Or(
                    [
                        pyparsing.CaselessKeyword(type_).set_name(f"'{type_}'")
                        for type_ in _token_to_node_expr_type
                    ]
                ),
            )
            .set_name("<attribute type>")
            .set_results_name("attr_type"),
            # attribute value
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets).
            pyparsing.Regex(r"[^\s()]+")
            .set_name("<attribute value>")
            .set_results_name("attr_value"),
        ]
    )
    node_attr_binary_expr.set_parse_action(__build_node_attr_binary_expr)

    date_unary_expr = pyparsing.And(
        [
            pyparsing.CaselessKeyword("date").set_name("'date'"),
            # operator
            pyparsing.Or(
                [
                    pyparsing.CaselessKeyword(op).set_name(f"'{op}'")
                    for op in _token_to_date_expr_unary_op
                ]
            ).set_results_name("operator"),
            # date
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets).
            # The actual value should be validated elsewhere.
            pyparsing.Regex(r"[^\s()]+")
            .set_name("<date>")
            .set_results_name("date"),
        ]
    )
    date_unary_expr.set_parse_action(__build_date_unary_expr)

    date_inrange_expr = pyparsing.And(
        [
            pyparsing.CaselessKeyword("date").set_name("'date'"),
            pyparsing.CaselessKeyword("in_range").set_name("'in_range'"),
            # date
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets).
            # The actual value should be validated elsewhere.
            # The Regex matches 'to'. In order to prevent that, FollowedBy is
            # used.
            pyparsing.Optional(
                pyparsing.And(
                    [
                        pyparsing.Regex(r"[^\s()]+")
                        .set_name("[<date>]")
                        .set_results_name("date1"),
                        pyparsing.FollowedBy(
                            pyparsing.CaselessKeyword("to").set_name("'to'")
                        ),
                    ]
                )
            ),
            pyparsing.CaselessKeyword("to").set_name("'to'"),
            pyparsing.Or(
                [
                    # date
                    # It can by any string containing any characters except
                    # whitespace (token separator) and "()" (brackets).
                    # The actual value should be validated elsewhere.
                    pyparsing.Regex(r"[^\s()]+")
                    .set_name("<date>")
                    .set_results_name("date2"),
                    # duration
                    pyparsing.And(
                        [
                            pyparsing.CaselessKeyword("duration").set_name(
                                "'duration'"
                            ),
                            __get_date_common_parser_part().set_results_name(
                                "duration"
                            ),
                        ]
                    ),
                ]
            ),
        ]
    )
    date_inrange_expr.set_parse_action(__build_date_inrange_expr)

    datespec_expr = pyparsing.And(
        [
            pyparsing.CaselessKeyword("date-spec").set_name("'date-spec'"),
            __get_date_common_parser_part().set_results_name("datespec"),
        ]
    )
    datespec_expr.set_parse_action(__build_datespec_expr)

    rsc_expr = pyparsing.And(
        [
            pyparsing.CaselessKeyword("resource").set_name("'resource'"),
            # resource name
            # Up to three parts separated by ":". The parts can contain any
            # characters except whitespace (token separator), ":" (parts
            # separator) and "()" (brackets).
            pyparsing.Regex(
                r"(?P<standard>[^\s:()]+)?:(?P<provider>[^\s:()]+)?:(?P<type>[^\s:()]+)?"
            ).set_name("<resource name>"),
        ]
    )
    rsc_expr.set_parse_action(__build_rsc_expr)

    op_interval = pyparsing.And(
        [
            pyparsing.CaselessKeyword("interval").set_name("'interval'"),
            # no spaces allowed around the "="
            pyparsing.Literal("=").leave_whitespace(),
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
            .set_name("<integer>[<time unit>]")
            .set_results_name("interval_value"),
        ]
    )
    op_expr = pyparsing.And(
        [
            pyparsing.CaselessKeyword("op").set_name("'op'"),
            # operation name
            # It can by any string containing any characters except whitespace
            # (token separator) and "()" (brackets). Operations are defined in
            # agents' metadata which we do not have access to (e.g. when the
            # user sets operation "my_check" and doesn't even specify agent's
            # name).
            pyparsing.Regex(r"[^\s()]+")
            .set_name("<operation name>")
            .set_results_name("name"),
            pyparsing.Optional(op_interval).set_results_name("interval"),
        ]
    )
    op_expr.set_parse_action(__build_op_expr)

    # Ordering matters here as the first expression which matches wins. This is
    # mostly not an issue as the expressions don't overlap and the grammar is
    # not ambiguous. There are, exceptions, however:
    # 1) date gt something
    #   This can be either a date_unary_expr or a node_attr_binary_expr. We
    #   want it to be a date expression. If the user wants it to be a node
    #   attribute expression, they can do it like this: 'date gt <type>
    #   something' where <type> is an item of _token_to_node_expr_type. That
    #   way, both date and node attribute expression can be realized.
    simple_expr = pyparsing.Or(
        [
            date_unary_expr,
            date_inrange_expr,
            datespec_expr,
            node_attr_unary_expr,
            node_attr_binary_expr,
            rsc_expr,
            op_expr,
        ]
    )

    # See pyparsing examples
    # https://github.com/pyparsing/pyparsing/blob/master/examples/simpleBool.py
    # https://github.com/pyparsing/pyparsing/blob/master/examples/eval_arith.py
    bool_operator = pyparsing.Or(
        [
            pyparsing.CaselessKeyword("and").set_name("'and'"),
            pyparsing.CaselessKeyword("or").set_name("'or'"),
        ]
    )
    bool_expr = pyparsing.infix_notation(
        simple_expr,
        # By putting both "and" and "or" in one tuple we say they have the same
        # priority. This is consistent with legacy pcs parsers. And it is how
        # it should be, they work as a glue between "simple_expr"s.
        [(bool_operator, 2, pyparsing.OpAssoc.LEFT, __build_bool_tree)],
    )

    return pyparsing.Or([bool_expr, simple_expr])

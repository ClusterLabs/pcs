from typing import (
    Any,
    Iterator,
    Optional,
    Tuple,
)

import pyparsing

from pcs.common.str_tools import indent

# TODO fix todos in functions
# TODO handle exceptions from pyparsing
# TODO write more tests?
# TODO make all the classes private if not used anywhere outside of the module
#       or write their doctexts


def parse_rule(
    rule_string: str, allow_rsc_expr: bool = False, allow_op_expr: bool = False
) -> "RuleExprPart":
    """
    Parse a rule string and return a corresponding semantic tree

    rule_string -- the whole rule expression
    allow_rsc_expr -- allow resource expressions in the rule
    allow_op_expr -- allow resource operation expressions in the rule
    """
    if not rule_string:
        return BoolAndExpr([])

    parsed = __get_rule_parser(
        allow_rsc_expr=allow_rsc_expr, allow_op_expr=allow_op_expr
    ).parseString(rule_string, parseAll=True)[0]

    if not isinstance(parsed, BoolExpr):
        # If we only got a representation on an inner rule element instead of a
        # rule element itself, wrap the result in a default AND-rule. (There is
        # only one expression so "and" vs. "or" doesn't really matter.)
        parsed = BoolAndExpr([parsed])

    return parsed


class RuleExprPart:
    def __init__(self, token_list: pyparsing.ParseResults):
        self._args = token_list

    def _token_str(self) -> str:
        raise NotImplementedError()

    def __str__(self) -> str:
        # This is used for visualizing the parsed tree for purposes of testing
        # and debugging.
        str_args = []
        for arg in self._args:
            str_args.extend(str(arg).splitlines())
        return "\n".join([self._token_str()] + indent(str_args))


class RscExpr(RuleExprPart):
    def _token_str(self) -> str:
        return "RESOURCE"


class OpExpr(RuleExprPart):
    def _token_str(self) -> str:
        return "OPERATION"


class NameValuePair(RuleExprPart):
    def _token_str(self) -> str:
        return "NAME-VALUE"


class BoolExpr(RuleExprPart):
    def _token_str(self) -> str:
        raise NotImplementedError()


class BoolAndExpr(BoolExpr):
    def _token_str(self) -> str:
        return "BOOL AND"


class BoolOrExpr(BoolExpr):
    def _token_str(self) -> str:
        return "BOOL OR"


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
    token_to_class = {
        "and": BoolAndExpr,
        "or": BoolOrExpr,
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
            operand_left = token_to_class[last_operator](
                [operand_left] + operand_list
            )
            operand_list = [operand_right]
        last_operator = operator
    if operand_list and last_operator:
        # Use any of the remaining stacked operands.
        operand_left = token_to_class[last_operator](
            [operand_left] + operand_list
        )
    return operand_left


def __get_rule_parser(
    allow_rsc_expr: bool = False, allow_op_expr: bool = False
) -> pyparsing.ParserElement:
    # This function defines the rule grammar

    # It was created for 'pcs resource [op] defaults' commands to be able to
    # set defaults for specified resources and/or operation using rules. When
    # implementing that feature, there was no time to reimplement all the other
    # rule expressions from old code. The plan is to move old rule parser code
    # here once there is time / need to do it. To do that, create new date_expr
    # and attr_expr in a way similar to existing rsc_expr and op_expr. Then,
    # add the new expressions into simple_expr_list and test the whole thing.

    rsc_expr = pyparsing.And(
        [
            pyparsing.Suppress(pyparsing.CaselessKeyword("resource")),
            # resource name
            # Up to three parts seperated by ":". The parts can contain any
            # characters except whitespace (token separator), ":" (parts
            # separator) and ")(" (brackets).
            pyparsing.Regex(
                r"((?P<standard>[^\s:)(]+):((?P<provider>[^\s:)(]+):)?)?(?P<type>[^\s:)(]+)"
            ),
        ]
    )
    rsc_expr.setParseAction(RscExpr)

    # TODO do not allow any whitespace between any parts of this expr
    op_interval = pyparsing.And(
        [
            pyparsing.CaselessKeyword("interval"),
            pyparsing.Suppress("="),
            # interval value: number followed by a time unit
            pyparsing.Combine(
                pyparsing.And(
                    [
                        pyparsing.Word(pyparsing.nums),
                        pyparsing.Optional(pyparsing.Word(pyparsing.alphas)),
                    ]
                )
            ),
        ]
    )
    op_interval.setParseAction(NameValuePair)
    op_expr = pyparsing.And(
        [
            pyparsing.Suppress(pyparsing.CaselessKeyword("op")),
            # operation name
            # It can by any string containing any characters except whitespace
            # (token separator) and ")(" (brackets). Operations are defined in
            # agents' metadata which we do not have access to (e.g. when the
            # user sets operation "my_check" and doesn't even specify agent's
            # name).
            pyparsing.Regex(r"[^\s)(]+"),
            pyparsing.Optional(op_interval),
        ]
    )
    op_expr.setParseAction(OpExpr)

    simple_expr_list = []
    if allow_rsc_expr:
        simple_expr_list.append(rsc_expr)
    if allow_op_expr:
        simple_expr_list.append(op_expr)
    simple_expr = pyparsing.Or(simple_expr_list)

    # See pyparsing examples
    # https://github.com/pyparsing/pyparsing/blob/master/examples/simpleBool.py
    # https://github.com/pyparsing/pyparsing/blob/master/examples/eval_arith.py
    bool_operator = pyparsing.Or(
        [pyparsing.CaselessKeyword("and"), pyparsing.CaselessKeyword("or"),]
    )
    bool_expr = pyparsing.infixNotation(
        simple_expr,
        # By putting both "and" and "or" in one tuple we say they have the same
        # priority. This is consistent with legacy pcs parsers. And it is how
        # it should be, they work as a glue between "simple_expr"s.
        [(bool_operator, 2, pyparsing.opAssoc.LEFT, __build_bool_tree)],
    )

    return pyparsing.Or([bool_expr, simple_expr])

import re
import xml.dom.minidom
import utils

# main functions

def parse_argv(argv, extra_options=None):
    options = {
        "id": None,
        "role": None,
        "score": None,
        "score-attribute": None
    }
    if extra_options:
        options.update(dict(extra_options))

    # parse options
    while argv:
        found = False
        option = argv.pop(0)
        for name in options:
            if option.startswith(name + "="):
                options[name] = option.split("=", 1)[1]
                found = True
                break
        if not found:
            argv.insert(0, option)
            break
    return options, argv

def dom_rule_add(dom_element, options, rule_argv):
    # validate options
    if options.get("score") and options.get("score-attribute"):
        utils.err("can not specify both score and score-attribute")
    if options.get("score") and not utils.is_score(options["score"]):
        # preserving legacy behaviour
        print (
            "Warning: invalid score '%s', setting score-attribute=pingd instead"
            % options["score"]
        )
        options["score-attribute"] = "pingd"
        options["score"] = None
    if options.get("role") and options["role"] not in ["master", "slave"]:
        utils.err(
            "invalid role '%s', use 'master' or 'slave'" % options["role"]
        )
    if options.get("id"):
        id_valid, id_error = utils.validate_xml_id(options["id"], 'rule id')
        if not id_valid:
            utils.err(id_error)
        if utils.does_id_exist(dom_element.ownerDocument, options["id"]):
            utils.err(
                "id '%s' is already in use, please specify another one"
                % options["id"]
            )

    # parse rule
    if not rule_argv:
        utils.err("no rule expression was specified")
    try:
        dom_rule = CibBuilder().build(
            dom_element,
            RuleParser().parse(TokenPreprocessor().run(rule_argv)),
            options.get("id")
        )
    except SyntaxError as e:
        utils.err(
            "'%s' is not a valid rule expression: %s"
            % (" ".join(rule_argv), e)
        )
    except UnexpectedEndOfInput as e:
        utils.err(
            "'%s' is not a valid rule expression: unexpected end of rule"
            % " ".join(rule_argv)
        )
    except (ParserException, CibBuilderException) as e:
        utils.err("'%s' is not a valid rule expression" % " ".join(rule_argv))

    # add options into rule xml
    if not options.get("score") and not options.get("score-attribute"):
        options["score"] = "INFINITY"
    for name, value in options.iteritems():
        if name != "id" and value is not None:
            dom_rule.setAttribute(name, value)
    # score or score-attribute is required for the nested rules in order to have
    # valid CIB, pacemaker does not use the score of the nested rules
    for rule in dom_rule.getElementsByTagName("rule"):
        rule.setAttribute("score", "0")
    if dom_element.hasAttribute("score"):
        dom_element.removeAttribute("score")
    if dom_element.hasAttribute("node"):
        dom_element.removeAttribute("node")
    return dom_element


class ExportDetailed(object):

    def __init__(self):
        self.show_detail = False

    def get_string(self, rule, show_detail, indent=""):
        self.show_detail = show_detail
        return indent + ("\n" + indent).join(self.list_rule(rule))

    def list_rule(self, rule):
        rule_parts = ["Rule: %s" % " ".join(self.list_attributes(rule))]
        for child in rule.childNodes:
            if child.nodeType == xml.dom.minidom.Node.TEXT_NODE:
                continue
            if child.tagName == "expression":
                self.indent_append(rule_parts, self.list_expression(child))
            elif child.tagName == "date_expression":
                self.indent_append(rule_parts, self.list_date_expression(child))
            elif child.tagName == "rule":
                self.indent_append(rule_parts, self.list_rule(child))
        return rule_parts

    def list_expression(self, expression):
        if "value" in expression.attributes.keys():
            exp_parts = [
                expression.getAttribute("attribute"),
                expression.getAttribute("operation")
            ]
            if expression.hasAttribute("type"):
                exp_parts.append(expression.getAttribute("type"))
            exp_parts.append(expression.getAttribute("value"))
        else:
            exp_parts = [
                expression.getAttribute("operation"),
                expression.getAttribute("attribute")
            ]
        if self.show_detail:
            exp_parts.append(" (id:%s)" % expression.getAttribute("id"))
        return ["Expression: %s" % " ".join(exp_parts)]

    def list_date_expression(self, expression):
        operation = expression.getAttribute("operation")
        if operation == "date_spec":
            date_spec_parts = self.list_attributes(
                expression.getElementsByTagName("date_spec")[0]
            )
            exp_parts = ["Expression:"]
            if self.show_detail:
                exp_parts.append(" (id:%s)" % expression.getAttribute("id"))
            return self.indent_append(
                [" ".join(exp_parts)],
                ["Date Spec: %s" % " ".join(date_spec_parts)]
            )
        elif operation == "in_range":
            exp_parts = ["date", "in_range"]
            if expression.hasAttribute("start"):
                exp_parts.extend([expression.getAttribute("start"), "to"])
            if expression.hasAttribute("end"):
                exp_parts.append(expression.getAttribute("end"))
            durations = expression.getElementsByTagName("duration")
            if durations:
                exp_parts.append("duration")
                duration_parts = self.list_attributes(durations[0])
            if self.show_detail:
                exp_parts.append(" (id:%s)" % expression.getAttribute("id"))
            result = ["Expression: %s" % " ".join(exp_parts)]
            if durations:
                self.indent_append(
                    result,
                    ["Duration: %s" % " ".join(duration_parts)]
                )
            return result
        else:
            exp_parts = ["date", expression.getAttribute("operation")]
            if expression.hasAttribute("start"):
                exp_parts.append(expression.getAttribute("start"))
            if expression.hasAttribute("end"):
                exp_parts.append(expression.getAttribute("end"))
            if self.show_detail:
                exp_parts.append(" (id:%s)" % expression.getAttribute("id"))
            return ["Expression: " + " ".join(exp_parts)]

    def list_attributes(self, element):
        attributes = utils.dom_attrs_to_list(element, with_id=False)
        if self.show_detail:
            attributes.append(" (id:%s)" % (element.getAttribute("id")))
        return attributes

    def indent_append(self, target, source, indent="  "):
        for part in source:
            target.append(indent + part)
        return target

class ExportAsExpression(object):

    def __init__(self):
        self.normalize = False

    def get_string(self, rule, normalize=False):
        self.normalize = normalize
        return self.string_rule(rule)

    def string_rule(self, rule):
        boolean_op = rule.getAttribute("boolean-op") or "or"
        rule_parts = []
        for child in rule.childNodes:
            if child.nodeType == xml.dom.minidom.Node.TEXT_NODE:
                continue
            if child.tagName == "expression":
                rule_parts.append(self.string_expression(child))
            elif child.tagName == "date_expression":
                rule_parts.append(self.string_date_expression(child))
            elif child.tagName == "rule":
                rule_parts.append("(%s)" % self.string_rule(child))
        if self.normalize:
            rule_parts.sort()
        return (" %s " % boolean_op).join(rule_parts)

    def string_expression(self, expression):
        if "value" in expression.attributes.keys():
            exp_parts = [
                expression.getAttribute("attribute"),
                expression.getAttribute("operation")
            ]
            if expression.hasAttribute("type"):
                exp_parts.append(expression.getAttribute("type"))
            elif self.normalize:
                exp_parts.append("string")
            value = expression.getAttribute("value")
            if " " in value:
                value = '"%s"' % value
            exp_parts.append(value)
        else:
            exp_parts = [
                expression.getAttribute("operation"),
                expression.getAttribute("attribute")
            ]
        return " ".join(exp_parts)

    def string_date_expression(self, expression):
        operation = expression.getAttribute("operation")
        if operation == "date_spec":
            exp_parts = ["date-spec"] + self.list_attributes(
                expression.getElementsByTagName("date_spec")[0]
            )
            return " ".join(exp_parts)
        elif operation == "in_range":
            exp_parts = ["date", "in_range"]
            if expression.hasAttribute("start"):
                exp_parts.extend([expression.getAttribute("start"), "to"])
            if expression.hasAttribute("end"):
                exp_parts.append(expression.getAttribute("end"))
            durations = expression.getElementsByTagName("duration")
            if durations:
                exp_parts.append("duration")
                exp_parts.extend(self.list_attributes(durations[0]))
            return " ".join(exp_parts)
        else:
            exp_parts = ["date", expression.getAttribute("operation")]
            if expression.hasAttribute("start"):
                exp_parts.append(expression.getAttribute("start"))
            if expression.hasAttribute("end"):
                exp_parts.append(expression.getAttribute("end"))
            return " ".join(exp_parts)

    def list_attributes(self, element):
        attributes = utils.dom_attrs_to_list(element, with_id=False)
        if self.normalize:
            attributes.sort()
        return attributes


# generic parser

class SymbolBase(object):

    END = "{end}"
    LITERAL = "{literal}"

    symbol_id = None
    left_binding_power = 0

    def null_denotation(self):
        raise SyntaxError("unexpected '%s'" % self.label())

    def left_denotation(self, left):
        raise SyntaxError(
            "unexpected '%s' after '%s'" % (self.label(), left.label())
        )

    def is_end(self):
        return self.symbol_id == SymbolBase.END

    def is_literal(self):
        return self.symbol_id == SymbolBase.LITERAL

    def label(self):
        return self.symbol_id

    def __str__(self):
        return "(%s)" % self.symbol_id


class SymbolLiteral(SymbolBase):

    def __init__(self, value):
        self.value = value

    def null_denotation(self):
        return self

    def label(self):
        return "end" if self.is_end() else str(self.value)

    def __str__(self):
        return "(end)" if self.is_end() else "(literal %s)" % self.value


class SymbolParenthesisOpen(SymbolBase):

    expression_func = None
    advance_func = None
    close_symbol_id = None

    def null_denotation(self):
        expression = self.expression_func()
        self.advance_func(self.close_symbol_id)
        return expression


class SymbolOperator(SymbolBase):

    expression_func = None
    allowed_child_ids = None

    def __init__(self):
        self.children = []

    def is_allowed_child(self, child_symbol, child_position):
        return (
            not self.allowed_child_ids
            or
            not self.allowed_child_ids[child_position]
            or
            child_symbol.symbol_id in self.allowed_child_ids[child_position]
        )

    def __str__(self):
        string = " ".join([
            str(part)
            for part in [self.symbol_id] + self.children
        ])
        return "(" + string + ")"


class SymbolPrefix(SymbolOperator):

    def null_denotation(self):
        self.children.append(self.expression_func(self.left_binding_power))
        if not self.is_allowed_child(self.children[0], 0):
            raise SyntaxError(
                "unexpected '%s' after '%s'"
                % (self.children[0].label(), self.symbol_id)
            )
        return self


class SymbolType(SymbolPrefix):

    value_re = None

    def null_denotation(self):
        super(SymbolType, self).null_denotation()
        if self.value_re and not self.value_re.match(self.children[0].value):
            raise SyntaxError(
                "invalid %s value '%s'"
                % (self.symbol_id, self.children[0].value)
            )
        return self


class SymbolInfix(SymbolOperator):

    def left_denotation(self, left):
        self.children.append(left)
        if not self.is_allowed_child(self.children[0], 0):
            raise SyntaxError(
                "unexpected '%s' before '%s'" % (left.label(), self.symbol_id)
            )
        self.children.append(self.expression_func(self.left_binding_power))
        if not self.is_allowed_child(self.children[1], 1):
            raise SyntaxError(
                "unexpected '%s' after '%s'"
                % (self.children[1].label(), self.symbol_id)
            )
        return self


class SymbolTernary(SymbolOperator):

    advance_func = None
    symbol_second_id = None

    def left_denotation(self, left):
        self.children.append(left)
        if not self.is_allowed_child(self.children[0], 0):
            raise SyntaxError(
                "unexpected '%s' before '%s'" % (left.label(), self.symbol_id)
            )
        self.children.append(self.expression_func(self.left_binding_power))
        if not self.is_allowed_child(self.children[1], 1):
            raise SyntaxError(
                "unexpected '%s' after '%s'"
                % (self.children[1].label(), self.symbol_id)
            )
        self.advance_func(self.symbol_second_id)
        self.children.append(self.expression_func(self.left_binding_power))
        if not self.is_allowed_child(self.children[2], 2):
            raise SyntaxError(
                "unexpected '%s' after '%s ... %s'"
                % (
                    self.children[2].label(),
                    self.symbol_id,
                    self.symbol_second_id
                  )
            )
        return self


class SymbolTable(object):

    def __init__(self):
        self.table = dict()

    def has_symbol(self, symbol_id):
        return symbol_id in self.table

    def get_symbol(self, symbol_id):
        return self.table[symbol_id]

    def new_symbol(
        self, symbol_id, superclass, binding_power=0, expression_func=None,
        advance_func=None
    ):
        if not self.has_symbol(symbol_id):
            class SymbolClass(superclass):
                pass
            SymbolClass.__name__ = "symbol_" + symbol_id
            SymbolClass.symbol_id = symbol_id
            SymbolClass.left_binding_power = binding_power
            if expression_func:
                SymbolClass.expression_func = expression_func
            if advance_func:
                SymbolClass.advance_func = advance_func
            self.table[symbol_id] = SymbolClass
            return SymbolClass
        return self.get_symbol(symbol_id)


class Parser(object):

    def __init__(self):
        self.current_symbol = None
        self.current_symbol_index = -1
        self.program = list()
        self.symbol_table = SymbolTable()
        self.new_symbol_literal(SymbolBase.LITERAL)
        self.new_symbol_literal(SymbolBase.END)

    def new_symbol_literal(self, symbol_id):
        return self.symbol_table.new_symbol(symbol_id, SymbolLiteral)

    def new_symbol_prefix(self, symbol_id, binding_power):
        return self.symbol_table.new_symbol(
            symbol_id, SymbolPrefix, binding_power, self.expression
        )

    def new_symbol_type(self, symbol_id, binding_power):
        return self.symbol_table.new_symbol(
            symbol_id, SymbolType, binding_power, self.expression
        )

    def new_symbol_infix(self, symbol_id, binding_power):
        return self.symbol_table.new_symbol(
            symbol_id, SymbolInfix, binding_power, self.expression
        )

    def new_symbol_ternary(self, symbol_id, second_id, binding_power):
        self.symbol_table.new_symbol(second_id, SymbolBase)
        symbol_class = self.symbol_table.new_symbol(
            symbol_id, SymbolTernary, binding_power, self.expression,
            self.advance
        )
        symbol_class.symbol_second_id = second_id
        return symbol_class

    def new_symbol_parenthesis(self, symbol_id, closing_id):
        self.symbol_table.new_symbol(closing_id, SymbolBase)
        symbol_class = self.symbol_table.new_symbol(
            symbol_id, SymbolParenthesisOpen, 0, self.expression, self.advance
        )
        symbol_class.close_symbol_id = closing_id
        return symbol_class

    def symbolize(self, program):
        symbolized_program = list()
        literal_class = self.symbol_table.get_symbol(SymbolBase.LITERAL)
        for token in program:
            if (
                self.symbol_table.has_symbol(token)
                and
                (
                    len(symbolized_program) < 1
                    or
                    not isinstance(symbolized_program[-1], SymbolType)
                )
            ):
                symbolized = self.symbol_table.get_symbol(token)()
            else:
                symbolized = literal_class(token)
            symbolized_program.append(symbolized)
        symbolized_program.append(
            self.symbol_table.get_symbol(SymbolBase.END)(None)
        )
        return symbolized_program

    def advance(self, expected_symbol_id=None):
        if (
            expected_symbol_id
            and
            self.current_symbol.symbol_id != expected_symbol_id
        ):
            if self.current_symbol.is_end():
                raise SyntaxError("missing '%s'" % expected_symbol_id)
            raise SyntaxError(
                "expecting '%s', got '%s'"
                % (expected_symbol_id, self.current_symbol.label())
            )
        self.current_symbol_index += 1
        if self.current_symbol_index >= len(self.program):
            raise UnexpectedEndOfInput()
        self.current_symbol = self.program[self.current_symbol_index]
        return self

    def expression(self, right_binding_power=0):
        symbol = self.current_symbol
        self.advance()
        left = symbol.null_denotation()
        while right_binding_power < self.current_symbol.left_binding_power:
            symbol = self.current_symbol
            self.advance()
            left = symbol.left_denotation(left)
        return left

    def parse(self, program):
        self.current_symbol = None
        self.current_symbol_index = -1
        self.program = self.symbolize(program)
        self.advance()
        result = self.expression()
        symbol = self.current_symbol
        if not symbol.is_end():
            raise SyntaxError("unexpected '%s'" % symbol.label())
        return result


class ParserException(Exception):
    pass


class UnexpectedEndOfInput(ParserException):
    pass


class SyntaxError(ParserException):
    pass


# rule parser specific code

class DateCommonValue(object):

    allowed_items = [
        "hours", "monthdays", "weekdays", "yeardays", "months", "weeks",
        "years", "weekyears", "moon",
    ]
    KEYWORD = None

    def __init__(self, parts_string, keyword=None):
        self.parts = dict()
        for part in parts_string.split():
            if not self.accepts_part(part):
                raise SyntaxError(
                    "unexpected '%s' in %s" % (part, keyword)
                )
            if "=" not in part:
                raise SyntaxError(
                    "missing =value after '%s' in %s" % (part, keyword)
                )
            name, value = part.split("=", 1)
            if value == "":
                raise SyntaxError(
                    "missing value after '%s' in %s" % (part, keyword)
                )
            self.parts[name] = value
        if not self.parts:
            raise SyntaxError(
                "missing one of '%s=' in %s"
                % ("=', '".join(DateCommonValue.allowed_items), keyword)
            )
        self.validate()

    def validate(self):
        return self

    @classmethod
    def accepts_part(cls, part):
        for name in cls.allowed_items:
            if part == name or part.startswith(name + "="):
                return True
        return False

    def __str__(self):
        return " ".join(
            ["%s=%s" % (name, value) for name, value in self.parts.iteritems()]
        )


class DateSpecValue(DateCommonValue):

    KEYWORD = "date-spec"
    part_re = re.compile("^(?P<since>\d+)(-(?P<until>\d+))?$")
    part_limits = {
        "hours" : (0, 23),
        "monthdays" : (0, 31),
        "weekdays" : (1, 7),
        "yeardays" : (1, 366),
        "months" : (1, 12),
        "weeks" : (1, 53),
        "weekyears" : (1, 53),
        "moon" : (0, 7),
    }

    def __init__(self, parts_string):
        super(DateSpecValue, self).__init__(parts_string, self.KEYWORD)

    def validate(self):
        for name, value in self.parts.iteritems():
            if not self.valid_part(name, value):
                raise SyntaxError(
                    "invalid %s '%s' in '%s'"
                    % (name, value, DateSpecValue.KEYWORD)
                )
        return self

    def valid_part(self, name, value):
        match = DateSpecValue.part_re.match(value)
        if not match:
            return False
        match_dict = match.groupdict()
        if not self.valid_part_limits(name, match_dict["since"]):
            return False
        if match_dict["until"]:
            if not self.valid_part_limits(name, match_dict["since"]):
                return False
            if int(match_dict["since"]) >= int(match_dict["until"]):
                return False
        return True

    def valid_part_limits(self, name, value):
        if name not in DateSpecValue.part_limits:
            return True
        limits = DateSpecValue.part_limits[name]
        return limits[0] <= int(value) <= limits[1]


class DateDurationValue(DateCommonValue):

    KEYWORD = "duration"

    def __init__(self, parts_string):
        super(DateDurationValue, self).__init__(parts_string, self.KEYWORD)

    def validate(self):
        for name, value in self.parts.iteritems():
            if not value.isdigit():
                raise SyntaxError(
                    "invalid %s '%s' in '%s'"
                    % (name, value, DateDurationValue.KEYWORD)
                )
        return self


class SymbolTypeDateCommon(SymbolType):

    date_value_class = None

    def null_denotation(self):
        symbol = self.expression_func(self.left_binding_power)
        symbol.value = self.date_value_class(symbol.value)
        self.children.append(symbol)
        return self


class SymbolTernaryInRange(SymbolTernary):

    allowed_child_ids = [
        [SymbolBase.LITERAL],
        [SymbolBase.LITERAL],
        [SymbolBase.LITERAL, DateDurationValue.KEYWORD]
    ]
    symbol_second_id = "to"

    def is_allowed_child(self, child_symbol, child_position):
        return (
            super(SymbolTernaryInRange, self).is_allowed_child(
                child_symbol, child_position
            )
            and
            (child_position != 0 or child_symbol.value == "date")
        )

    def left_denotation(self, left):
        super(SymbolTernaryInRange, self).left_denotation(left)
        for child in self.children[1:]:
            if child.is_literal() and not utils.is_iso8601_date(child.value):
                raise SyntaxError(
                    "invalid date '%s' in 'in_range ... to'" % child.value
                )
        return self


class RuleParser(Parser):

    comparison_list = ["eq", "ne", "lt", "gt", "lte", "gte", "in_range"]
    date_comparison_list = ["gt", "lt", "in_range"]
    prefix_list = ["defined", "not_defined"]
    boolean_list = ["and", "or"]
    simple_type_list = ["string", "integer", "version"]
    parenthesis_open = "("
    parenthesis_close = ")"

    def __init__(self):
        super(RuleParser, self).__init__()

        for operator in RuleParser.comparison_list:
            if operator == "in_range":
                continue
            symbol_class = self.new_symbol_infix(operator, 50)
            symbol_class.allowed_child_ids = [
                [SymbolBase.LITERAL],
                [SymbolBase.LITERAL] + RuleParser.simple_type_list
            ]

        self.symbol_table.new_symbol(
            "in_range", SymbolTernaryInRange, 50, self.expression, self.advance
        )
        self.symbol_table.new_symbol("to", SymbolBase)

        for operator in RuleParser.prefix_list:
            symbol_class = self.new_symbol_prefix(operator, 60)
            symbol_class.allowed_child_ids = [[SymbolBase.LITERAL]]

        for operator in RuleParser.simple_type_list:
            symbol_class = self.new_symbol_type(operator, 70)
        self.symbol_table.get_symbol("integer").value_re = re.compile("^-?\d+$")
        self.symbol_table.get_symbol("version").value_re = re.compile(
            "^\d+(\.\d+)*$"
        )
        symbol_class = self.new_symbol_type_date(DateSpecValue, 70)
        symbol_class = self.new_symbol_type_date(DateDurationValue, 70)

        for operator in RuleParser.boolean_list:
            symbol_class = self.new_symbol_infix(operator, 40)
            symbol_class.allowed_child_ids = [
                RuleParser.comparison_list
                + RuleParser.prefix_list
                + [DateSpecValue.KEYWORD]
                + RuleParser.boolean_list
            ] * 2

        self.new_symbol_parenthesis(
            RuleParser.parenthesis_open, RuleParser.parenthesis_close
        )

    def parse(self, program):
        syntactic_tree = super(RuleParser, self).parse(program)
        if (
            syntactic_tree.is_literal()
            or
            (
                isinstance(syntactic_tree, SymbolType)
                and not
                (
                    isinstance(syntactic_tree, SymbolTypeDateCommon)
                    and
                    syntactic_tree.date_value_class == DateSpecValue
                )
            )
        ):
            raise SyntaxError(
                "missing one of '%s'"
                % "', '".join(
                    RuleParser.comparison_list + RuleParser.prefix_list
                    + [DateSpecValue.KEYWORD]
                )
            )
        return syntactic_tree

    def new_symbol_type_date(self, date_value_class, binding_power):
        symbol_class = self.symbol_table.new_symbol(
            date_value_class.KEYWORD, SymbolTypeDateCommon, binding_power,
            self.expression
        )
        symbol_class.date_value_class = date_value_class
        return symbol_class


# cib builder

class CibBuilder(object):

    def build(self, dom_element, syntactic_tree, rule_id=None):
        dom_rule = self.add_element(
            dom_element,
            "rule",
            rule_id if rule_id else dom_element.getAttribute("id") + "-rule"
        )
        self.build_rule(dom_rule, syntactic_tree)
        return dom_rule

    def build_rule(self, dom_rule, syntactic_tree):
        if isinstance(syntactic_tree, SymbolOperator):
            if syntactic_tree.symbol_id in RuleParser.boolean_list:
                self.build_boolean(dom_rule, syntactic_tree)
            elif (
                syntactic_tree.symbol_id in RuleParser.date_comparison_list
                and
                syntactic_tree.children[0].value == 'date'
                and
                syntactic_tree.children[1].is_literal()
            ):
                self.build_date_expression(dom_rule, syntactic_tree)
            elif (
                isinstance(syntactic_tree, SymbolTypeDateCommon)
                and
                syntactic_tree.date_value_class == DateSpecValue
            ):
                self.build_datespec(dom_rule, syntactic_tree)
            else:
                self.build_expression(dom_rule, syntactic_tree)
        else:
            raise InvalidSyntacticTree(syntactic_tree)

    def build_datespec(self, dom_element, syntactic_tree):
        dom_expression = self.add_element(
            dom_element,
            "date_expression",
            dom_element.getAttribute("id") + "-expr"
        )
        dom_expression.setAttribute("operation", "date_spec")
        dom_datespec = self.add_element(
            dom_expression,
            "date_spec",
            dom_expression.getAttribute("id") + "-datespec"
        )
        for key, value in syntactic_tree.children[0].value.parts.iteritems():
            dom_datespec.setAttribute(key, value)

    def build_expression(self, dom_element, syntactic_tree):
        dom_expression = self.add_element(
            dom_element,
            "expression",
            dom_element.getAttribute("id") + "-expr"
        )
        dom_expression.setAttribute("operation", syntactic_tree.symbol_id)
        dom_expression.setAttribute(
            "attribute", syntactic_tree.children[0].value
        )
        if not isinstance(syntactic_tree, SymbolPrefix):
            child = syntactic_tree.children[1]
            if isinstance(child, SymbolType):
                dom_expression.setAttribute(
                    "type",
                    "number" if child.symbol_id == "integer" else child.symbol_id
                )
                child = child.children[0]
            dom_expression.setAttribute("value", child.value)

    def build_date_expression(self, dom_element, syntactic_tree):
        dom_expression = self.add_element(
            dom_element,
            "date_expression",
            dom_element.getAttribute("id") + "-expr"
        )
        dom_expression.setAttribute("operation", syntactic_tree.symbol_id)
        if syntactic_tree.symbol_id == 'gt':
            dom_expression.setAttribute(
                "start", syntactic_tree.children[1].value
            )
        elif syntactic_tree.symbol_id == 'lt':
            dom_expression.setAttribute(
                "end", syntactic_tree.children[1].value
            )
        elif syntactic_tree.symbol_id == 'in_range':
            dom_expression.setAttribute(
                "start", syntactic_tree.children[1].value
            )
            if (
                isinstance(syntactic_tree.children[2], SymbolTypeDateCommon)
                and
                syntactic_tree.children[2].date_value_class == DateDurationValue
            ):
                dom_duration = self.add_element(
                    dom_expression,
                    "duration",
                    dom_expression.getAttribute("id") + "-duration"
                )
                duration = syntactic_tree.children[2].children[0].value
                for key, value in duration.parts.iteritems():
                    dom_duration.setAttribute(key, value)
            else:
                dom_expression.setAttribute(
                    "end", syntactic_tree.children[2].value
                )

    def build_boolean(self, dom_element, syntactic_tree):
        dom_element.setAttribute("boolean-op", syntactic_tree.symbol_id)
        for subtree in syntactic_tree.children:
            if (
                subtree.symbol_id in RuleParser.boolean_list
                and
                subtree.symbol_id != syntactic_tree.symbol_id
            ):
                self.build(
                    dom_element,
                    subtree,
                    dom_element.getAttribute("id") + "-rule"
                )
            else:
                self.build_rule(dom_element, subtree)

    def add_element(self, parent, tag_name, element_id):
        dom = parent.ownerDocument
        child = parent.appendChild(dom.createElement(tag_name))
        child.setAttribute("id", utils.find_unique_id(dom, element_id))
        return child


class CibBuilderException(Exception):
    pass


class InvalidSyntacticTree(CibBuilderException):
    pass


# token preprocessing

class TokenPreprocessor(object):

    def run(self, token_list):
        return self.convert_legacy_date(
            self.join_date_common(
                self.separate_parenthesis(token_list)
            )
        )

    def separate_parenthesis(self, input_list):
        output_list = []
        for token in input_list:
            if not (
                RuleParser.parenthesis_open in token
                or
                RuleParser.parenthesis_close in token
            ):
                output_list.append(token)
            else:
                part = []
                for char in token:
                    if char in [
                        RuleParser.parenthesis_open,
                        RuleParser.parenthesis_close
                    ]:
                        if part:
                            output_list.append("".join(part))
                            part = []
                        output_list.append(char)
                    else:
                        part.append(char)
                if part:
                    output_list.append("".join(part))
        return output_list

    def join_date_common(self, input_list):
        output_list = []
        token_parts = []
        in_datecommon = False
        for token in input_list:
            if in_datecommon:
                if DateCommonValue.accepts_part(token):
                    token_parts.append(token)
                elif (
                    token == "operation=date_spec"
                    and
                    token_parts[0] == DateSpecValue.KEYWORD
                ):
                    pass # gracefully ignoring for backwards compatibility
                else:
                    in_datecommon = False
                    output_list.append(token_parts[0])
                    if len(token_parts) > 1:
                        output_list.append(" ".join(token_parts[1:]))
                    output_list.append(token)
                    token_parts = []
            elif token in [DateSpecValue.KEYWORD, DateDurationValue.KEYWORD]:
                in_datecommon = True
                token_parts = [token]
            else:
                output_list.append(token)
        if token_parts:
            output_list.append(token_parts[0])
            if len(token_parts) > 1:
                output_list.append(" ".join(token_parts[1:]))
        return output_list

    def convert_legacy_date(self, input_list):
        output_list = []
        in_date = False
        date_start = ""
        date_end = ""
        token_parts = []
        for token in input_list:
            if in_date:
                token_parts.append(token)
                if token.startswith("start="):
                    date_start = token[len("start="):]
                elif token.startswith("end="):
                    date_end = token[len("end="):]
                else:
                    if token == "gt" and date_start and not date_end:
                        output_list.extend(["date", "gt", date_start])
                    elif token == "lt" and not date_start and date_end:
                        output_list.extend(["date", "lt", date_end])
                    elif token == "in_range" and date_start and date_end:
                        output_list.extend(
                            ["date", "in_range", date_start, "to", date_end]
                        )
                    else:
                        output_list.extend(token_parts)
                    token_parts = []
                    date_start = date_end = ""
                    in_date = False
            elif token == 'date':
                token_parts = ['date']
                in_date = True
            else:
                output_list.append(token)
        if token_parts:
            output_list.extend(token_parts)
        return output_list


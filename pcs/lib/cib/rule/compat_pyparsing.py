from typing import (
    Any,
    Callable,
    Union,
)

import pyparsing

# pylint: disable=unused-import
from pyparsing import (
    And,
    CaselessKeyword,
    Combine,
    FollowedBy,
    Group,
    Literal,
    OneOrMore,
    Optional,
    Or,
    ParseException,
    ParserElement,
    ParseResults,
    Regex,
    Suppress,
    Word,
    alphas,
    nums,
)

if pyparsing.__version__.startswith("3."):
    from pyparsing import (  # pylint: disable=no-name-in-module
        OpAssoc,
        infix_notation,
    )
else:

    class ParserElementMixin:
        @staticmethod
        def enable_packrat(
            cache_size_limit: Union[int, None] = 128, *, force: bool = False
        ) -> None:
            del force
            # pylint: disable=too-many-function-args
            pyparsing.ParserElement.enablePackrat(cache_size_limit)  # type: ignore

        def leave_whitespace(self) -> pyparsing.ParserElement:
            return self.leaveWhitespace()  # type: ignore

        def parse_string(
            self, instring: str, parse_all: bool = False
        ) -> pyparsing.ParserElement:
            return self.parseString(instring, parseAll=parse_all)  # type: ignore

        def set_name(self, name: str) -> pyparsing.ParserElement:
            # pylint: disable=redefined-outer-name
            return self.setName(name)  # type: ignore

        def set_parse_action(
            self, *fns: Callable[..., Any], **kwargs: Any
        ) -> pyparsing.ParserElement:
            return self.setParseAction(*fns, **kwargs)  # type: ignore

        def set_results_name(
            self, name: str, list_all_matches: bool = False
        ) -> pyparsing.ParserElement:
            # pylint: disable=redefined-outer-name
            return self.setResultsName(name, listAllMatches=list_all_matches)  # type: ignore

    pyparsing.ParseResults.as_list = pyparsing.ParseResults.asList  # type: ignore
    OpAssoc = pyparsing.opAssoc  # type: ignore

    # pylint: disable=function-redefined
    def infix_notation(  # type: ignore
        base_expr: pyparsing.ParserElement,
        op_list: list[Any],
        lpar: Union[str, pyparsing.ParserElement] = Suppress("("),
        rpar: Union[str, pyparsing.ParserElement] = Suppress(")"),
    ) -> pyparsing.ParserElement:
        # pylint: disable=too-many-function-args
        return pyparsing.infixNotation(base_expr, op_list, lpar, rpar)  # type: ignore

    class ParseResults(pyparsing.ParseResults):  # type: ignore
        def as_list(self) -> list:
            return super().asList()

    class And(pyparsing.And, ParserElementMixin):  # type: ignore
        pass

    class CaselessKeyword(pyparsing.CaselessKeyword, ParserElementMixin):  # type: ignore
        pass

    class Combine(pyparsing.Combine, ParserElementMixin):  # type: ignore
        pass

    class Literal(pyparsing.Literal, ParserElementMixin):  # type: ignore
        pass

    class OneOrMore(pyparsing.OneOrMore, ParserElementMixin):  # type: ignore
        pass

    class Optional(pyparsing.Optional, ParserElementMixin):  # type: ignore
        pass

    class Or(pyparsing.Or, ParserElementMixin):  # type: ignore
        pass

    class ParserElement(pyparsing.ParserElement, ParserElementMixin):  # type: ignore
        pass

    class Regex(pyparsing.Regex, ParserElementMixin):  # type: ignore
        pass

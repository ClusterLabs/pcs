from collections import Counter
import dataclasses
from typing import (
    List,
    Set,
)

from pcs.common import reports
from pcs.common.types import CibRuleExpressionType

from pcs.lib import validate
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.live import parse_isodate

from .expression_part import (
    NODE_ATTR_TYPE_NUMBER,
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


class Validator:
    def __init__(
        self,
        parsed_rule: BoolExpr,
        runner: CommandRunner,
        allow_rsc_expr: bool = False,
        allow_op_expr: bool = False,
    ):
        """
        parsed_rule -- a rule to be validated
        runner -- a class for running external processes
        allow_op_expr -- are op expressions allowed in the rule?
        allow_rsc_expr -- are resource expressions allowed in the rule?
        """
        self._rule = parsed_rule
        self._runner = runner
        self._allow_op_expr = allow_op_expr
        self._allow_rsc_expr = allow_rsc_expr
        self._disallowed_expr_list: Set[CibRuleExpressionType] = set()

    def get_reports(self) -> reports.ReportItemList:
        report_list = self._call_validate(self._rule)
        for expr_type in self._disallowed_expr_list:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.RuleExpressionNotAllowed(expr_type)
                )
            )
        return report_list

    def _call_validate(self, expr: RuleExprPart) -> reports.ReportItemList:
        # pylint: disable=too-many-return-statements
        if isinstance(expr, BoolExpr):
            return self._validate_bool_expr(expr)
        if isinstance(expr, DateInRangeExpr):
            return self._validate_date_inrange_expr(expr)
        if isinstance(expr, DatespecExpr):
            return self._validate_datespec_expr(expr)
        if isinstance(expr, DateUnaryExpr):
            return self._validate_date_unary_expr(expr)
        if isinstance(expr, NodeAttrExpr):
            return self._validate_node_attr_expr(expr)
        if isinstance(expr, OpExpr):
            return self._validate_op_expr(expr)
        if isinstance(expr, RscExpr):
            return self._validate_rsc_expr(expr)
        return []

    def _validate_bool_expr(self, expr: BoolExpr) -> reports.ReportItemList:
        report_list = []
        for child in expr.children:
            report_list.extend(self._call_validate(child))
        return report_list

    def _validate_date_inrange_expr(
        self, expr: DateInRangeExpr
    ) -> reports.ReportItemList:
        # TODO This is taken from the CIB schema. There is an ongoing
        # discussion that the schema doesn't match Pacemaker Explained. Based
        # on the result of the discussion, this might need to be updated.
        duration_parts = {
            "hours",
            "monthdays",
            "weekdays",
            "yearsdays",
            "months",
            "weeks",
            "years",
            "weekyears",
            "moon",
        }
        start_timestamp, end_timestamp = None, None
        report_list = []

        if expr.date_start is not None:
            start_timestamp = parse_isodate(self._runner, expr.date_start)
            if start_timestamp is None:
                report_list.append(
                    reports.item.ReportItem.error(
                        message=reports.messages.InvalidOptionValue(
                            "date", expr.date_start, "ISO8601 date"
                        ),
                    )
                )
        if expr.date_end is not None:
            end_timestamp = parse_isodate(self._runner, expr.date_end)
            if end_timestamp is None:
                report_list.append(
                    reports.item.ReportItem.error(
                        message=reports.messages.InvalidOptionValue(
                            "date", expr.date_end, "ISO8601 date"
                        ),
                    )
                )
        if (
            expr.date_start is not None
            and expr.date_end is not None
            and start_timestamp is not None
            and end_timestamp is not None
            and start_timestamp >= end_timestamp
        ):
            report_list.append(
                reports.item.ReportItem.error(
                    message=reports.messages.RuleExpressionSinceGreaterThanUntil(
                        expr.date_start, expr.date_end
                    ),
                )
            )

        if expr.duration_parts:
            duplicate_keys = {
                key
                for key, count in Counter(
                    [pair[0] for pair in expr.duration_parts]
                ).items()
                if count > 1
            }
            validator_list: List[validate.ValidatorInterface] = [
                validate.ValuePositiveInteger(name)
                for name in sorted(duration_parts)
            ]
            validator_list.append(
                validate.NamesIn(duration_parts, option_type="duration")
            )
            report_list += validate.ValidatorAll(validator_list).validate(
                dict(expr.duration_parts)
            )
            if duplicate_keys:
                report_list.append(
                    reports.item.ReportItem.error(
                        message=reports.messages.RuleExpressionOptionsDuplication(
                            sorted(duplicate_keys)
                        ),
                    )
                )

        return report_list

    @staticmethod
    def _validate_datespec_expr(expr: DatespecExpr) -> reports.ReportItemList:
        # TODO This is taken from the CIB schema. There is an ongoing
        # discussion that the schema doesn't match Pacemaker Explained. Based
        # on the result of the discussion, this might need to be updated.
        part_limits = {
            "hours": (0, 23),
            "monthdays": (1, 31),
            "weekdays": (1, 7),
            "yearsdays": (1, 366),
            "months": (1, 12),
            "weeks": (1, 53),
            "years": (None, None),
            "weekyears": (None, None),
            "moon": (0, 7),
        }

        duplicate_keys = {
            key
            for key, count in Counter(
                [pair[0] for pair in expr.date_parts]
            ).items()
            if count > 1
        }
        validator_list: List[validate.ValidatorInterface] = [
            validate.ValuePcmkDatespecPart(name, limits[0], limits[1])
            for name, limits in sorted(part_limits.items())
        ]
        validator_list.append(
            validate.NamesIn(part_limits.keys(), option_type="datespec")
        )

        report_list = validate.ValidatorAll(validator_list).validate(
            dict(expr.date_parts)
        )
        if duplicate_keys:
            report_list.append(
                reports.item.ReportItem.error(
                    message=reports.messages.RuleExpressionOptionsDuplication(
                        sorted(duplicate_keys)
                    ),
                )
            )
        return report_list

    def _validate_date_unary_expr(
        self, expr: DateUnaryExpr
    ) -> reports.ReportItemList:
        report_list: reports.ReportItemList = []
        timestamp = parse_isodate(self._runner, expr.date)
        if timestamp is None:
            report_list.append(
                reports.item.ReportItem.error(
                    message=reports.messages.InvalidOptionValue(
                        "date", expr.date, "ISO8601 date"
                    ),
                )
            )
        return report_list

    @staticmethod
    def _validate_node_attr_expr(expr: NodeAttrExpr) -> reports.ReportItemList:
        validator_list: List[validate.ValidatorInterface] = []
        if expr.attr_type == NODE_ATTR_TYPE_NUMBER:
            validator_list.append(
                validate.ValueInteger(
                    "attr_value", option_name_for_report="attribute"
                )
            )
        if expr.attr_type == NODE_ATTR_TYPE_VERSION:
            validator_list.append(
                validate.ValueVersion(
                    "attr_value", option_name_for_report="attribute"
                )
            )
        return validate.ValidatorAll(validator_list).validate(
            dataclasses.asdict(expr)
        )

    def _validate_op_expr(self, expr: OpExpr) -> reports.ReportItemList:
        del expr
        if not self._allow_op_expr:
            self._disallowed_expr_list.add(CibRuleExpressionType.OP_EXPRESSION)
        return []

    def _validate_rsc_expr(self, expr: RscExpr) -> reports.ReportItemList:
        del expr
        if not self._allow_rsc_expr:
            self._disallowed_expr_list.add(CibRuleExpressionType.RSC_EXPRESSION)
        return []

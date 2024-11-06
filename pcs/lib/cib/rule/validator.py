import dataclasses
from collections import (
    Counter,
    OrderedDict,
)
from typing import Optional

from dateutil import parser as dateutil_parser

from pcs.common import reports
from pcs.common.types import CibRuleExpressionType
from pcs.lib import validate

from .expression_part import (
    NODE_ATTR_TYPE_INTEGER,
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
        allow_rsc_expr: bool = False,
        allow_op_expr: bool = False,
        allow_node_attr_expr: bool = False,
    ):
        """
        parsed_rule -- a rule to be validated
        allow_op_expr -- are op expressions allowed in the rule?
        allow_rsc_expr -- are resource expressions allowed in the rule?
        allow_node_attr_expr -- are node attribute expressions allowed in rule?
        """
        self._rule = parsed_rule
        self._allow_op_expr = allow_op_expr
        self._allow_rsc_expr = allow_rsc_expr
        self._allow_node_attr_expr = allow_node_attr_expr
        self._disallowed_expr_list: set[CibRuleExpressionType] = set()

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

    @staticmethod
    def _validate_date_inrange_expr(
        expr: DateInRangeExpr,
    ) -> reports.ReportItemList:
        duration_parts = [
            "years",
            "months",
            "weeks",
            "days",
            "hours",
            "minutes",
            "seconds",
        ]
        start_date, end_date = None, None
        report_list = []

        if expr.date_start is not None:
            try:
                start_date = dateutil_parser.isoparse(expr.date_start)
            except ValueError:
                report_list.append(
                    reports.item.ReportItem.error(
                        message=reports.messages.InvalidOptionValue(
                            "date", expr.date_start, "ISO 8601 date"
                        ),
                    )
                )
        if expr.date_end is not None:
            try:
                end_date = dateutil_parser.isoparse(expr.date_end)
            except ValueError:
                report_list.append(
                    reports.item.ReportItem.error(
                        message=reports.messages.InvalidOptionValue(
                            "date", expr.date_end, "ISO 8601 date"
                        ),
                    )
                )
        if (
            # start and end dates have been specified
            expr.date_start is not None
            and expr.date_end is not None
            # start and end dates are valid dates
            and start_date is not None
            and end_date is not None
            # start happens later than end
            and start_date >= end_date
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
            validator_list: list[validate.ValidatorInterface] = [
                validate.ValuePositiveInteger(name) for name in duration_parts
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
        part_limits: dict[str, tuple[Optional[int], Optional[int]]] = (
            OrderedDict(
                years=(None, None),
                weekyears=(None, None),
                months=(1, 12),
                weeks=(1, 53),
                yeardays=(1, 366),
                monthdays=(1, 31),
                weekdays=(1, 7),
                hours=(0, 23),
                minutes=(0, 59),
                seconds=(0, 59),
            )
        )

        duplicate_keys = {
            key
            for key, count in Counter(
                [pair[0] for pair in expr.date_parts]
            ).items()
            if count > 1
        }
        validator_list: list[validate.ValidatorInterface] = [
            validate.ValuePcmkDatespecPart(name, limits[0], limits[1])
            for name, limits in part_limits.items()
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

    @staticmethod
    def _validate_date_unary_expr(
        expr: DateUnaryExpr,
    ) -> reports.ReportItemList:
        report_list: reports.ReportItemList = []
        try:
            dateutil_parser.isoparse(expr.date)
        except ValueError:
            report_list.append(
                reports.item.ReportItem.error(
                    message=reports.messages.InvalidOptionValue(
                        "date", expr.date, "ISO 8601 date"
                    ),
                )
            )
        return report_list

    def _validate_node_attr_expr(
        self, expr: NodeAttrExpr
    ) -> reports.ReportItemList:
        if not self._allow_node_attr_expr:
            self._disallowed_expr_list.add(CibRuleExpressionType.EXPRESSION)
            return []

        validator_list: list[validate.ValidatorInterface] = []
        if expr.attr_type == NODE_ATTR_TYPE_INTEGER:
            validator_list.append(
                validate.ValueInteger(
                    "attr_value", option_name_for_report="integer attribute"
                )
            )
        elif expr.attr_type == NODE_ATTR_TYPE_NUMBER:
            # rhbz#1869399
            # Originally, pacemaker only supported 'number', treated it as an
            # integer and documented it as 'integer'. With CIB schema 3.5.0+,
            # 'integer' is supported as well. With crm_feature_set 3.5.0+,
            # 'number' is treated as a floating point number.
            # Since pcs never supported 'number' until the above changes in
            # pacemaker happened and pacemaker was able to handle floating
            # point numbers before (even though truncating them to integers),
            # we'll just check for a float here. If that's not good enough, we
            # can fix it later and validate the value as integer when
            # crm_feature_set < 3.5.0.
            validator_list.append(
                validate.ValueFloat(
                    "attr_value", option_name_for_report="number attribute"
                )
            )
        elif expr.attr_type == NODE_ATTR_TYPE_VERSION:
            validator_list.append(
                validate.ValueVersion(
                    "attr_value", option_name_for_report="version attribute"
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

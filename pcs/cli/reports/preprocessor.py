from typing import (
    Any,
    Optional,
    cast,
)

from pcs.cli.common.output import INDENT_STEP
from pcs.cli.common.tools import print_to_stderr
from pcs.cli.constraint import output
from pcs.common import reports
from pcs.common.pacemaker.constraint import CibConstraintsDto
from pcs.common.str_tools import indent
from pcs.common.types import StringIterable

from .processor import ReportItemPreprocessor


def get_duplicate_constraint_exists_preprocessor(
    lib: Any,
) -> ReportItemPreprocessor:
    def _report_item_preprocessor(
        report_item: reports.ReportItem,
    ) -> Optional[reports.ReportItem]:
        """
        Provide additional info based on DuplicateConstraintsExist message

        Drop deprecated DuplicateConstraintsList message. This message
        contained structured info about duplicate constraints.
        Intercept DuplicateConstraintsExist message and extract constraint IDs
        from it. Load constraints from CIB using library and print those
        matching IDs from the message.
        """

        # pylint: disable=too-many-branches
        def my_print(lines: StringIterable) -> None:
            print_to_stderr("\n".join(indent(lines, INDENT_STEP)))

        if (
            report_item.message.code
            == reports.deprecated_codes.DUPLICATE_CONSTRAINTS_LIST
        ):
            return None

        if isinstance(
            report_item.message, reports.messages.DuplicateConstraintsExist
        ):
            print_to_stderr("Duplicate constraints:")
            duplicate_id_list = report_item.message.constraint_ids
            constraints_dto = cast(
                CibConstraintsDto,
                lib.constraint.get_config(evaluate_rules=False),
            )
            for dto_lp in constraints_dto.location:
                if dto_lp.attributes.constraint_id in duplicate_id_list:
                    my_print(
                        output.location.plain_constraint_to_text(dto_lp, True)
                    )
            for dto_ls in constraints_dto.location_set:
                if dto_ls.attributes.constraint_id in duplicate_id_list:
                    my_print(
                        output.location.set_constraint_to_text(dto_ls, True)
                    )
            for dto_cp in constraints_dto.colocation:
                if dto_cp.attributes.constraint_id in duplicate_id_list:
                    my_print(
                        output.colocation.plain_constraint_to_text(dto_cp, True)
                    )
            for dto_cs in constraints_dto.colocation_set:
                if dto_cs.attributes.constraint_id in duplicate_id_list:
                    my_print(
                        output.colocation.set_constraint_to_text(dto_cs, True)
                    )
            for dto_op in constraints_dto.order:
                if dto_op.attributes.constraint_id in duplicate_id_list:
                    my_print(
                        output.order.plain_constraint_to_text(dto_op, True)
                    )
            for dto_os in constraints_dto.order_set:
                if dto_os.attributes.constraint_id in duplicate_id_list:
                    my_print(output.order.set_constraint_to_text(dto_os, True))
            for dto_tp in constraints_dto.ticket:
                if dto_tp.attributes.constraint_id in duplicate_id_list:
                    my_print(
                        output.ticket.plain_constraint_to_text(dto_tp, True)
                    )
            for dto_ts in constraints_dto.ticket_set:
                if dto_ts.attributes.constraint_id in duplicate_id_list:
                    my_print(output.ticket.set_constraint_to_text(dto_ts, True))

        return report_item

    return _report_item_preprocessor

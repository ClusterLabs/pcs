from typing import Sequence

from pcs.common import reports
from pcs.common.permissions.dto import PermissionEntryDto
from pcs.common.permissions.types import (
    PermissionGrantedType,
    PermissionTargetType,
)

__ALLOWED_TYPES = [e.value for e in PermissionTargetType]
__ALLOWED_ACCESS_TYPES = [e.value for e in PermissionGrantedType]


def validate_set_permissions(
    permissions: Sequence[PermissionEntryDto],
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    user_set: set[tuple[str, PermissionTargetType]] = set()
    duplicate_set: set[tuple[str, PermissionTargetType]] = set()
    for perm in permissions:
        if not perm.name:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.InvalidOptionValue(
                        "name", "", allowed_values=None, cannot_be_empty=True
                    )
                )
            )

        # TODO: we really need dedicated dto validation
        # This doesn't provide the information about which of the dtos has wrong
        # data
        if perm.type not in PermissionTargetType:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.InvalidOptionValue(
                        "type", perm.type, allowed_values=__ALLOWED_TYPES
                    )
                )
            )
        for allow in perm.allow:
            if allow not in PermissionGrantedType:
                report_list.append(
                    reports.ReportItem.error(
                        reports.messages.InvalidOptionValue(
                            "allow",
                            allow,
                            allowed_values=__ALLOWED_ACCESS_TYPES,
                        )
                    )
                )

        if (perm.name, perm.type) in user_set:
            duplicate_set.add((perm.name, perm.type))
        user_set.add((perm.name, perm.type))
    if duplicate_set:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.PermissionDuplication(sorted(duplicate_set))
            )
        )
    return report_list

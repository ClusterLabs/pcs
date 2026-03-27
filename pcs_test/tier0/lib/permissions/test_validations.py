from unittest import TestCase

from pcs.common import reports
from pcs.common.permissions.dto import PermissionEntryDto
from pcs.common.permissions.types import (
    PermissionGrantedType,
    PermissionTargetType,
)
from pcs.lib.permissions import validations

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class ValidateSetPermissions(TestCase):
    def test_success(self):
        report_list = validations.validate_set_permissions(
            [
                PermissionEntryDto(
                    "hacluster",
                    type=PermissionTargetType.USER,
                    allow=[PermissionGrantedType.FULL],
                ),
                PermissionEntryDto(
                    "haclient",
                    type=PermissionTargetType.GROUP,
                    allow=[
                        PermissionGrantedType.GRANT,
                        PermissionGrantedType.READ,
                        PermissionGrantedType.WRITE,
                    ],
                ),
            ]
        )

        assert_report_item_list_equal(report_list, [])

    def test_empty_name(self):
        report_list = validations.validate_set_permissions(
            [
                PermissionEntryDto(
                    "hacluster",
                    type=PermissionTargetType.USER,
                    allow=[PermissionGrantedType.FULL],
                ),
                PermissionEntryDto(
                    "",
                    type=PermissionTargetType.GROUP,
                    allow=[PermissionGrantedType.READ],
                ),
            ]
        )

        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="name",
                    option_value="",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_duplicates(self):
        report_list = validations.validate_set_permissions(
            [
                PermissionEntryDto(
                    "john",
                    type=PermissionTargetType.USER,
                    allow=[PermissionGrantedType.GRANT],
                ),
                PermissionEntryDto(
                    "john",
                    type=PermissionTargetType.USER,
                    allow=[PermissionGrantedType.WRITE],
                ),
                # same name, but different 'type' are not duplicates
                PermissionEntryDto(
                    "martin",
                    type=PermissionTargetType.USER,
                    allow=[PermissionGrantedType.READ],
                ),
                PermissionEntryDto(
                    "martin",
                    type=PermissionTargetType.GROUP,
                    allow=[PermissionGrantedType.READ],
                ),
            ]
        )

        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.PERMISSION_DUPLICATION,
                    target_list=[("john", PermissionTargetType.USER)],
                )
            ],
        )

    def test_invalid_type(self):
        report_list = validations.validate_set_permissions(
            [
                PermissionEntryDto(
                    "hacluster",
                    type="foobar",
                    allow=[PermissionGrantedType.FULL],
                ),
            ]
        )

        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="type",
                    option_value="foobar",
                    allowed_values=["user", "group"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_invalid_allow(self):
        report_list = validations.validate_set_permissions(
            [
                PermissionEntryDto(
                    "hacluster",
                    type=PermissionTargetType.USER,
                    allow=[PermissionGrantedType.FULL, "foobar"],
                ),
            ]
        )

        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="allow",
                    option_value="foobar",
                    allowed_values=["read", "write", "grant", "full"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

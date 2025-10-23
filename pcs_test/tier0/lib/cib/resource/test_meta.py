from unittest import TestCase

from pcs.common import reports
from pcs.lib.cib.resource import meta as lib_meta
from pcs.lib.resource_agent import ResourceAgentParameter

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal
from pcs_test.tools.metadata_dto import get_fixture_meta_attributes_dto

FIXTURE_METADATA_PARAMETERS = [
    ResourceAgentParameter(
        name=parameter_dto.name,
        shortdesc=parameter_dto.shortdesc,
        longdesc=parameter_dto.longdesc,
        type=type,
        default=parameter_dto.default,
        enum_values=parameter_dto.enum_values,
        required=parameter_dto.required,
        advanced=parameter_dto.advanced,
        deprecated=parameter_dto.deprecated,
        deprecated_by=parameter_dto.deprecated_by,
        deprecated_desc=parameter_dto.deprecated_desc,
        unique_group=parameter_dto.unique_group,
        reloadable=parameter_dto.reloadable,
    )
    for parameter_dto in get_fixture_meta_attributes_dto().parameters
]

FIXTURE_DEFINED_NAMES = sorted(
    parameter.name for parameter in FIXTURE_METADATA_PARAMETERS
)


class TestValidateMetaAttributes(TestCase):
    def test_empty(self):
        assert_report_item_list_equal(
            lib_meta.validate_meta_attributes(FIXTURE_METADATA_PARAMETERS, {}),
            [],
        )

    def test_valid_names(self):
        meta_attrs = {
            "priority": "INFINITY",
            "critical": "true",
            "target-role": "Stopped",
            "failure-timeout": "10s",
            "remote-node": "some-remote-node",
            "remote-port": "1234",
            "remote-connect-timeout": "60s",
        }
        assert_report_item_list_equal(
            lib_meta.validate_meta_attributes(
                FIXTURE_METADATA_PARAMETERS,
                meta_attrs,
            ),
            [],
        )

    def test_invalid_names(self):
        meta_attrs = {
            "target_role": "Stopped",
            "non-existent-name": "10s",
            "remote-pot": "1234",
        }
        invalid_names = sorted(meta_attrs.keys())
        assert_report_item_list_equal(
            lib_meta.validate_meta_attributes(
                FIXTURE_METADATA_PARAMETERS, meta_attrs
            ),
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=invalid_names,
                    allowed=FIXTURE_DEFINED_NAMES,
                    option_type="meta attribute",
                    allowed_patterns=[],
                )
            ],
        )

    def test_mixed_valid_invalid_names(self):
        meta_attrs = {
            "target-role": "Stopped",
            "non-existent-name": "10s",
            "remote-pot": "",
        }
        invalid_names = ["non-existent-name"]
        assert_report_item_list_equal(
            lib_meta.validate_meta_attributes(
                FIXTURE_METADATA_PARAMETERS, meta_attrs
            ),
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=invalid_names,
                    allowed=FIXTURE_DEFINED_NAMES,
                    option_type="meta attribute",
                    allowed_patterns=[],
                )
            ],
        )

    def test_names_with_empty_values(self):
        meta_attrs = {
            "target-role": "",
            "non-existent-name": "",
            "remote-pot": "",
        }
        assert_report_item_list_equal(
            lib_meta.validate_meta_attributes(
                FIXTURE_METADATA_PARAMETERS, meta_attrs
            ),
            [],
        )

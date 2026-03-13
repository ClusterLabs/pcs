from unittest import TestCase

from pcs.common import reports
from pcs.lib.pcs_cfgsync import validations

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class ValidateUpdateSyncOptions(TestCase):
    _ALLOWED_OPTIONS = [
        "sync_thread_disable",
        "sync_thread_enable",
        "sync_thread_pause",
        "sync_thread_resume",
    ]

    def test_empty_options(self):
        assert_report_item_list_equal(
            validations.validate_update_sync_options({}),
            [
                fixture.error(
                    reports.codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    option_names=self._ALLOWED_OPTIONS,
                    deprecated_names=[],
                    option_type=None,
                )
            ],
        )

    def test_invalid_options(self):
        assert_report_item_list_equal(
            validations.validate_update_sync_options(
                {"sync_thread_disable": True, "sync_thread_super_disable": True}
            ),
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["sync_thread_super_disable"],
                    allowed=self._ALLOWED_OPTIONS,
                    option_type=None,
                    allowed_patterns=[],
                )
            ],
        )

    def test_mutually_exclusive(self):
        option_values = [
            {"sync_thread_pause": "1", "sync_thread_resume": True},
            {"sync_thread_enable": True, "sync_thread_disable": True},
        ]
        for options in option_values:
            with self.subTest(value=options):
                assert_report_item_list_equal(
                    validations.validate_update_sync_options(options),
                    [
                        fixture.error(
                            reports.codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                            option_names=sorted(options.keys()),
                            option_type=None,
                        )
                    ],
                )

    def test_invalid_pause_interval(self):
        timeout_values = ["-10", "3.14", "timeout", ""]
        for timeout in timeout_values:
            with self.subTest(value=timeout):
                assert_report_item_list_equal(
                    validations.validate_update_sync_options(
                        {"sync_thread_pause": timeout}
                    ),
                    [
                        fixture.error(
                            reports.codes.INVALID_OPTION_VALUE,
                            option_name="sync_thread_pause",
                            option_value=timeout,
                            allowed_values="an integer greater than or equal to 0",
                            cannot_be_empty=False,
                            forbidden_characters=None,
                        )
                    ],
                )

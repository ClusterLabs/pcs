from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.booth import config_structure
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.pcs_mock import mock


class ValidateTicketExistsTest(TestCase):
    def test_raises_on_duplicate_ticket(self):
        assert_raise_library_error(
            lambda: config_structure.validate_ticket_exists(
                [config_structure.ConfigItem("ticket", "B")], "A"
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_TICKET_DOES_NOT_EXIST,
                {
                    "ticket_name": "A",
                },
            ),
        )

class ValidateTicketUniqueTest(TestCase):
    def test_raises_on_duplicate_ticket(self):
        assert_raise_library_error(
            lambda: config_structure.validate_ticket_unique(
                [config_structure.ConfigItem("ticket", "A")], "A"
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_TICKET_DUPLICATE,
                {
                    "ticket_name": "A",
                },
            ),
        )

    def test_do_not_raises_when_no_duplicated_ticket(self):
        config_structure.validate_ticket_unique([], "A")

class TicketExistsTest(TestCase):
    def test_returns_true_if_ticket_in_structure(self):
        self.assertTrue(config_structure.ticket_exists(
            [config_structure.ConfigItem("ticket", "A")], "A"
        ))

    def test_returns_false_if_ticket_in_structure(self):
        self.assertFalse(config_structure.ticket_exists(
            [config_structure.ConfigItem("ticket", "A")], "B"
        ))

class ValidateTicketNameTest(TestCase):
    def test_accept_valid_ticket_name(self):
        config_structure.validate_ticket_name("abc")

    def test_refuse_bad_ticket_name(self):
        assert_raise_library_error(
            lambda: config_structure.validate_ticket_name("@ticket"),
            (
                severities.ERROR,
                report_codes.BOOTH_TICKET_NAME_INVALID,
                {
                    "ticket_name": "@ticket",
                },
            ),
        )

class ValidatePeersTest(TestCase):
    def test_do_no_raises_on_correct_args(self):
        config_structure.validate_peers(
            site_list=["1.1.1.1", "2.2.2.2"],
            arbitrator_list=["3.3.3.3"]
        )

    def test_refuse_less_than_2_sites(self):
        assert_raise_library_error(
            lambda: config_structure.validate_peers(
                site_list=["1.1.1.1"],
                arbitrator_list=["3.3.3.3", "4.4.4.4"]
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_LACK_OF_SITES,
                {
                    "sites": ["1.1.1.1"],
                }
            ),
        )

    def test_refuse_even_number_peers(self):
        assert_raise_library_error(
            lambda: config_structure.validate_peers(
                site_list=["1.1.1.1", "2.2.2.2"],
                arbitrator_list=[]
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_EVEN_PEERS_NUM,
                {
                    "number": 2,
                }
            ),
        )

    def test_refuse_address_duplication(self):
        assert_raise_library_error(
            lambda: config_structure.validate_peers(
                site_list=["1.1.1.1", "1.1.1.1"],
                arbitrator_list=["3.3.3.3"]
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_ADDRESS_DUPLICATION,
                {
                    "addresses": ["1.1.1.1"],
                }
            ),
        )

    def test_refuse_problem_combination(self):
        assert_raise_library_error(
            lambda: config_structure.validate_peers(
                site_list=["1.1.1.1"],
                arbitrator_list=["1.1.1.1"]
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_LACK_OF_SITES,
                {
                    "sites": ["1.1.1.1"],
                }
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_EVEN_PEERS_NUM,
                {
                    "number": 2,
                }
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_ADDRESS_DUPLICATION,
                {
                    "addresses": ["1.1.1.1"],
                }
            ),
        )

class RemoveTicketTest(TestCase):
    @mock.patch("pcs.lib.booth.config_structure.validate_ticket_exists")
    def test_successfully_remove_ticket(self, mock_validate_ticket_exists):
        configuration = [
            config_structure.ConfigItem("ticket", "some-ticket"),
            config_structure.ConfigItem("ticket", "deprecated-ticket"),
        ]
        self.assertEqual(
            config_structure.remove_ticket(configuration, "deprecated-ticket"),
            [
                config_structure.ConfigItem("ticket", "some-ticket"),
            ]
        )
        mock_validate_ticket_exists.assert_called_once_with(
            configuration,
            "deprecated-ticket"
        )

class AddTicketTest(TestCase):
    @mock.patch("pcs.lib.booth.config_structure.validate_ticket_unique")
    @mock.patch("pcs.lib.booth.config_structure.validate_ticket_name")
    def test_successfully_add_ticket(
        self, mock_validate_name, mock_validate_uniq
    ):
        configuration = [
            config_structure.ConfigItem("ticket", "some-ticket"),
        ]
        self.assertEqual(
            config_structure.add_ticket(configuration, "new-ticket"),
            [
                config_structure.ConfigItem("ticket", "some-ticket"),
                config_structure.ConfigItem("ticket", "new-ticket"),
            ],
        )

        mock_validate_name.assert_called_once_with("new-ticket")
        mock_validate_uniq.assert_called_once_with(configuration, "new-ticket")

class SetAuthfileTest(TestCase):
    def test_add_authfile(self):
        self.assertEqual(
            [
                config_structure.ConfigItem("authfile", "/path/to/auth.file"),
                config_structure.ConfigItem("site", "1.1.1.1"),
            ],
            config_structure.set_authfile(
                [
                    config_structure.ConfigItem("site", "1.1.1.1"),
                ],
                "/path/to/auth.file"
            )
        )
    def test_reset_authfile(self):
        self.assertEqual(
            [
                config_structure.ConfigItem("authfile", "/path/to/auth.file"),
                config_structure.ConfigItem("site", "1.1.1.1"),
            ],
            config_structure.set_authfile(
                [
                    config_structure.ConfigItem("site", "1.1.1.1"),
                    config_structure.ConfigItem("authfile", "/old/path/to/auth1.file"),
                    config_structure.ConfigItem("authfile", "/old/path/to/auth2.file"),
                ],
                "/path/to/auth.file"
            )
        )

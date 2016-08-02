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
            lambda: config_structure.validate_ticket_exists(["B"], "A"),
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
            lambda: config_structure.validate_ticket_unique(["A"], "A"),
            (
                severities.ERROR,
                report_codes.BOOTH_TICKET_DUPLICATE,
                {
                    "ticket_name": "A",
                },
            ),
        )


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


class ValidateParticipantsTest(TestCase):
    def test_do_no_raises_on_correct_args(self):
        config_structure.validate_participants(
            site_list=["1.1.1.1", "2.2.2.2"],
            arbitrator_list=["3.3.3.3"]
        )

    def test_refuse_less_than_2_sites(self):
        assert_raise_library_error(
            lambda: config_structure.validate_participants(
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

    def test_refuse_even_number_participants(self):
        assert_raise_library_error(
            lambda: config_structure.validate_participants(
                site_list=["1.1.1.1", "2.2.2.2"],
                arbitrator_list=[]
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_EVEN_PARTICIPANTS_NUM,
                {
                    "number": 2,
                }
            ),
        )

    def test_refuse_address_duplication(self):
        assert_raise_library_error(
            lambda: config_structure.validate_participants(
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
            lambda: config_structure.validate_participants(
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
                report_codes.BOOTH_EVEN_PARTICIPANTS_NUM,
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


class ParseTest(TestCase):
    def test_returns_parsed_config_when_correct_config(self):
        self.assertEqual(
            config_structure.parse("\n".join([
                "site = 1.1.1.1",
                " site  =  2.2.2.2 ",
                "arbitrator=3.3.3.3",
                'ticket = "TicketA"',
                'ticket = "TicketB"',
                "authfile = /path/to/authfile.key",
            ])),
            {
                "sites": ["1.1.1.1", "2.2.2.2"],
                "arbitrators": ["3.3.3.3"],
                "tickets": ["TicketA", "TicketB"],
                "authfile": "/path/to/authfile.key",
            }
        )

    def test_refuse_multiple_authfiles(self):
        assert_raise_library_error(
            lambda: config_structure.parse("\n".join([
                "authfile = /path/to/authfile.key",
                "authfile = /path/to/authfile2.key",
            ])),
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_INVALID_CONTENT,
                {
                    "reason": "multiple authfile",
                }
            ),
        )


    def test_refuse_unexpected_line(self):
        assert_raise_library_error(
            lambda: config_structure.parse("nonsense"),
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                {
                    "line_list": ["nonsense"],
                }
            ),
        )

    def test_refuse_unexpected_line_similar_to_pattern(self):
        assert_raise_library_error(
            lambda: config_structure.parse("nonsense = 1.1.1.1"),
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                {
                    "line_list": ["nonsense = 1.1.1.1"],
                }
            ),
        )


class BuildTest(TestCase):
    def test_succesfully_create_content_without_tickets(self):
        self.assertEqual(
            config_structure.build({
                "sites": ["1.1.1.1", "2.2.2.2"],
                "arbitrators": ["3.3.3.3"],
                "authfile": "/path/to/authfile.key",
            }),
            "\n".join([
                "site = 1.1.1.1",
                "site = 2.2.2.2",
                "arbitrator = 3.3.3.3",
                "authfile = /path/to/authfile.key",
            ])
        )

    def test_succesfully_create_content_with_tickets(self):
        self.assertEqual(
            config_structure.build({
                "sites": ["1.1.1.1", "2.2.2.2"],
                "arbitrators": ["3.3.3.3"],
                "authfile": "/path/to/authfile.key",
                "tickets": ["ticketB", "ticketA"],
            }),
            "\n".join([
                "site = 1.1.1.1",
                "site = 2.2.2.2",
                "arbitrator = 3.3.3.3",
                "authfile = /path/to/authfile.key",
                'ticket = "ticketA"',
                'ticket = "ticketB"',
            ])
        )

    def test_sort_sites_and_arbitrators(self):
        self.assertEqual(
            config_structure.build({
                "sites": ["2.2.2.2", "1.1.1.1"],
                "arbitrators": ["3.3.3.3"],
                "authfile": "/path/to/authfile.key",
            }),
            "\n".join([
                "site = 1.1.1.1",
                "site = 2.2.2.2",
                "arbitrator = 3.3.3.3",
                "authfile = /path/to/authfile.key",
            ])
        )


class RemoveTicketTest(TestCase):
    @mock.patch("pcs.lib.booth.config_structure.validate_ticket_exists")
    def test_successfully_remove_ticket(self, mock_validate_ticket_exists):
        self.assertEqual(
            config_structure.remove_ticket(
                {
                    "sites": ["1.1.1.1", "2.2.2.2"],
                    "arbitrators": ["3.3.3.3"],
                    "tickets": ["deprecated-ticket", "some-ticket"]
                },
                "deprecated-ticket"
            ),
            {
                "sites": ["1.1.1.1", "2.2.2.2"],
                "arbitrators": ["3.3.3.3"],
                "tickets": ["some-ticket"]
            },
        )
        mock_validate_ticket_exists.assert_called_once_with(
            ["deprecated-ticket", "some-ticket"],
            "deprecated-ticket"
        )


class AddTicketTest(TestCase):
    @mock.patch("pcs.lib.booth.config_structure.validate_ticket_unique")
    @mock.patch("pcs.lib.booth.config_structure.validate_ticket_name")
    def test_successfully_add_ticket(
        self, mock_validate_ticket_name, mock_validate_ticket_unique
    ):
        self.assertEqual(
            config_structure.add_ticket(
                {
                    "sites": ["1.1.1.1", "2.2.2.2"],
                    "arbitrators": ["3.3.3.3"],
                    "tickets": ["some-ticket"]
                },
                "new-ticket"
            ),
            {
                "sites": ["1.1.1.1", "2.2.2.2"],
                "arbitrators": ["3.3.3.3"],
                "tickets": ["new-ticket", "some-ticket"]
            },
        )

        mock_validate_ticket_name.assert_called_once_with("new-ticket")
        mock_validate_ticket_unique.assert_called_once_with(
            ["some-ticket"],
            "new-ticket"
        )

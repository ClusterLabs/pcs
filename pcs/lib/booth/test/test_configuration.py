from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.booth import configuration
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_raise_library_error


class BuildTest(TestCase):
    def test_succesfully_create_content(self):
        self.assertEqual(
            configuration.build({
                "sites": ["1.1.1.1", "2.2.2.2"],
                "arbitrators": ["3.3.3.3"]
            }),
            [
                "site = 1.1.1.1",
                "site = 2.2.2.2",
                "arbitrator = 3.3.3.3",
            ]
        )

    def test_sort_sites_and_arbitrators(self):
        self.assertEqual(
            configuration.build({
                "sites": ["2.2.2.2", "1.1.1.1"],
                "arbitrators": ["3.3.3.3"]
            }),
            [
                "site = 1.1.1.1",
                "site = 2.2.2.2",
                "arbitrator = 3.3.3.3",
            ]
        )

class ParseTest(TestCase):
    def test_returns_sites_and_arbitrators_when_correct_config(self):
        self.assertEqual(
            configuration.parse([
                "site = 1.1.1.1",
                " site  =  2.2.2.2 ",
                "arbitrator=3.3.3.3",
            ]),
            {
                "sites": ["1.1.1.1", "2.2.2.2"],
                "arbitrators": ["3.3.3.3"],
            }
        )

    def test_refuse_unexpected_line(self):
        assert_raise_library_error(
            lambda: configuration.parse(["nonsense"]),
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
            lambda: configuration.parse([
                "nonsense = 1.1.1.1",
            ]),
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                {
                    "line_list": ["nonsense = 1.1.1.1"],
                }
            ),
        )

class ValidateParticipantsTest(TestCase):
    def test_do_no_raises_on_correct_args(self):
        configuration.validate_participants(
            site_list=["1.1.1.1", "2.2.2.2"],
            arbitrator_list=["3.3.3.3"]
        )

    def test_refuse_less_than_2_sites(self):
        assert_raise_library_error(
            lambda: configuration.validate_participants(
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
            lambda: configuration.validate_participants(
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
            lambda: configuration.validate_participants(
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
            lambda: configuration.validate_participants(
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

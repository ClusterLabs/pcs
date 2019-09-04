from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal

from pcs.common import report_codes
from pcs.lib.booth import config_validators
from pcs.lib.booth.config_facade import ConfigFacade
from pcs.lib.booth.config_parser import ConfigItem


class CheckInstanceName(TestCase):
    # pylint: disable=no-self-use
    def test_success(self):
        assert_report_item_list_equal(
            config_validators.check_instance_name(
                "valid_instance"
            ),
            []
        )

    def test_report(self):
        instance = "/tmp/booth/invalid_instance"
        assert_report_item_list_equal(
            config_validators.check_instance_name(instance),
            [
                fixture.error(
                    report_codes.BOOTH_INVALID_NAME,
                    name=instance,
                    reason="contains illegal character '/'",
                ),
            ]
        )


class Create(TestCase):
    # pylint: disable=no-self-use
    def test_no_reports_on_correct_args(self):
        assert_report_item_list_equal(
            config_validators.create(
                ["1.1.1.1", "2.2.2.2"],
                ["3.3.3.3"]
            ),
            []
        )

    def test_refuse_less_than_2_sites(self):
        assert_report_item_list_equal(
            config_validators.create(
                ["1.1.1.1"],
                ["3.3.3.3", "4.4.4.4"]
            ),
            [
                fixture.error(
                    report_codes.BOOTH_LACK_OF_SITES,
                    sites=["1.1.1.1"],
                ),
            ]
        )

    def test_refuse_even_number_peers(self):
        assert_report_item_list_equal(
            config_validators.create(
                ["1.1.1.1", "2.2.2.2"],
                []
            ),
            [
                fixture.error(
                    report_codes.BOOTH_EVEN_PEERS_NUM,
                    number=2,
                ),
            ]
        )

    def test_refuse_address_duplication(self):
        assert_report_item_list_equal(
            config_validators.create(
                ["1.1.1.1", "1.1.1.1", "1.1.1.1"],
                ["3.3.3.3", "4.4.4.4"]
            ),
            [
                fixture.error(
                    report_codes.BOOTH_ADDRESS_DUPLICATION,
                    addresses=["1.1.1.1"],
                ),
            ]
        )

    def test_refuse_problem_combination(self):
        assert_report_item_list_equal(
            config_validators.create(
                ["1.1.1.1"],
                ["1.1.1.1"]
            ),
            [
                fixture.error(
                    report_codes.BOOTH_LACK_OF_SITES,
                    sites=["1.1.1.1"],
                ),
                fixture.error(
                    report_codes.BOOTH_EVEN_PEERS_NUM,
                    number=2,
                ),
                fixture.error(
                    report_codes.BOOTH_ADDRESS_DUPLICATION,
                    addresses=["1.1.1.1"],
                ),
            ]
        )

class AddTicket(TestCase):
    invalid_option_report_args = dict(
        option_type="booth ticket",
        allowed=[
            "acquire-after",
            "attr-prereq",
            "before-acquire-handler",
            "expire",
            "renewal-freq",
            "retries",
            "timeout",
            "weights",
        ],
        allowed_patterns=[],
    )

    def setUp(self):
        self.conf = ConfigFacade([
            ConfigItem("site", "site1", []),
            ConfigItem("site", "site2", []),
            ConfigItem("arbitrator", "arbitrator1", []),
            ConfigItem("ticket", "ticketA", []),
        ])

    def test_success_no_options(self):
        assert_report_item_list_equal(
            config_validators.add_ticket(self.conf, "ticketB", {}),
            []
        )

    def test_success(self):
        assert_report_item_list_equal(
            config_validators.add_ticket(
                self.conf, "ticketB", {"timeout": "10"}
            ),
            []
        )

    def test_bad_ticket_name(self):
        assert_report_item_list_equal(
            config_validators.add_ticket(self.conf, "@ticketB", {}),
            [
                fixture.error(
                    report_codes.BOOTH_TICKET_NAME_INVALID,
                    ticket_name="@ticketB",
                ),
            ]
        )

    def test_duplicate_ticket_name(self):
        assert_report_item_list_equal(
            config_validators.add_ticket(self.conf, "ticketA", {}),
            [
                fixture.error(
                    report_codes.BOOTH_TICKET_DUPLICATE,
                    ticket_name="ticketA",
                ),
            ]
        )

    def test_options(self):
        assert_report_item_list_equal(
            config_validators.add_ticket(
                self.conf,
                "ticketB",
                {
                    "site": "a",
                    "port": "b",
                    "timeout": " ",
                    "unknown": " ",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_names=["unknown"],
                    **self.invalid_option_report_args
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["port", "site"],
                    **self.invalid_option_report_args
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value=" ",
                    option_name="timeout",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value=" ",
                    option_name="unknown",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_unknown_options_forced(self):
        assert_report_item_list_equal(
            config_validators.add_ticket(
                self.conf,
                "ticketB",
                {
                    "site": "a",
                    "unknown": "c",
                },
                allow_unknown_options=True
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    **self.invalid_option_report_args
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["site"],
                    **self.invalid_option_report_args
                ),
            ]
        )

class RemoveTicket(TestCase):
    def setUp(self):
        self.conf = ConfigFacade([
            ConfigItem("site", "site1", []),
            ConfigItem("site", "site2", []),
            ConfigItem("arbitrator", "arbitrator1", []),
            ConfigItem("ticket", "ticketA", []),
            ConfigItem("ticket", "ticketB", []),
        ])

    def test_no_reports_on_existing_ticket(self):
        assert_report_item_list_equal(
            config_validators.remove_ticket(self.conf, "ticketA"),
            []
        )

    def test_report_missing_ticket(self):
        assert_report_item_list_equal(
            config_validators.remove_ticket(self.conf, "ticketX"),
            [
                fixture.error(
                    report_codes.BOOTH_TICKET_DOES_NOT_EXIST,
                    ticket_name="ticketX",
                )
            ]
        )

    def test_report_not_a_ticket(self):
        assert_report_item_list_equal(
            config_validators.remove_ticket(self.conf, "site1"),
            [
                fixture.error(
                    report_codes.BOOTH_TICKET_DOES_NOT_EXIST,
                    ticket_name="site1",
                )
            ]
        )

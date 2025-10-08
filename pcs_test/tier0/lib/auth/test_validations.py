from unittest import TestCase

from pcs import settings
from pcs.common import reports
from pcs.common.auth import HostAuthData, HostWithTokenAuthData
from pcs.common.host import Destination
from pcs.lib.auth import validations

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class ValidateHostsWithToken(TestCase):
    def test_valid_no_reports(self):
        report_list = validations.validate_hosts_with_token(
            {
                "node1": HostWithTokenAuthData(
                    "TOKEN", [Destination("node1", 2224)]
                ),
                "node2": HostWithTokenAuthData(
                    "TOKEN", [Destination("node2", 2224)]
                ),
            }
        )
        assert_report_item_list_equal(report_list, [])

    def test_invalid_name(self):
        report_list = validations.validate_hosts_with_token(
            {
                "node1": HostWithTokenAuthData(
                    "TOKEN", [Destination("node1", 2224)]
                ),
                "": HostWithTokenAuthData(
                    "TOKEN", [Destination("node2", 2224)]
                ),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="host name",
                    option_value="",
                    allowed_values="",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_empty_token(self):
        report_list = validations.validate_hosts_with_token(
            {
                "node1": HostWithTokenAuthData(
                    "TOKEN", [Destination("node1", 2224)]
                ),
                "node2": HostWithTokenAuthData(
                    "", [Destination("node2", 2224)]
                ),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="token",
                    option_value="",
                    allowed_values="a string (min length: 1) (max length: 512)",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_token_too_long(self):
        bad_token = "a" * (settings.pcsd_token_max_chars + 1)
        report_list = validations.validate_hosts_with_token(
            {
                "node1": HostWithTokenAuthData(
                    "TOKEN", [Destination("node1", 2224)]
                ),
                "node2": HostWithTokenAuthData(
                    bad_token, [Destination("node2", 2224)]
                ),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="token",
                    option_value=bad_token,
                    allowed_values="a string (min length: 1) (max length: 512)",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_empty_dest_list(self):
        report_list = validations.validate_hosts_with_token(
            {
                "node1": HostWithTokenAuthData(
                    "TOKEN", [Destination("node1", 2224)]
                ),
                "node2": HostWithTokenAuthData("TOKEN", []),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="dest_list",
                    option_value="[]",
                    allowed_values="non-empty list of destinations for node 'node2'",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_empty_node_addr(self):
        report_list = validations.validate_hosts_with_token(
            {
                "node1": HostWithTokenAuthData(
                    "TOKEN", [Destination("node1", 2224), Destination("", 2224)]
                ),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="addr",
                    option_value="",
                    allowed_values="address for node 'node1'",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_invalid_port_number(self):
        report_list = validations.validate_hosts_with_token(
            {
                "node1": HostWithTokenAuthData(
                    "TOKEN",
                    [
                        Destination("node1", 2224),
                        Destination("a", -1),
                        Destination("b", 0),
                        Destination("c", 1000000000),
                    ],
                ),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="port for node 'node1'",
                    option_value=-1,
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="port for node 'node1'",
                    option_value=0,
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="port for node 'node1'",
                    option_value=1000000000,
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )


class ValidateHosts(TestCase):
    def test_valid_no_reports(self):
        report_list = validations.validate_hosts(
            {
                "node1": HostAuthData(
                    "username", "password", [Destination("node1", 2224)]
                ),
                "node2": HostAuthData(
                    "username", "password", [Destination("node2", 2224)]
                ),
            }
        )
        assert_report_item_list_equal(report_list, [])

    def test_invalid_name(self):
        report_list = validations.validate_hosts(
            {
                "node1": HostAuthData(
                    "username", "password", [Destination("node1", 2224)]
                ),
                "": HostAuthData(
                    "username", "password", [Destination("node2", 2224)]
                ),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="host name",
                    option_value="",
                    allowed_values="",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_empty_dest_list(self):
        report_list = validations.validate_hosts(
            {
                "node1": HostAuthData(
                    "username", "password", [Destination("node1", 2224)]
                ),
                "node2": HostAuthData("username", "password", []),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="dest_list",
                    option_value="[]",
                    allowed_values="non-empty list of destinations for node 'node2'",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_empty_node_addr(self):
        report_list = validations.validate_hosts(
            {
                "node1": HostAuthData(
                    "username",
                    "password",
                    [Destination("node1", 2224), Destination("", 2224)],
                ),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="addr",
                    option_value="",
                    allowed_values="address for node 'node1'",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_invalid_port_number(self):
        report_list = validations.validate_hosts_with_token(
            {
                "node1": HostAuthData(
                    "username",
                    "password",
                    [
                        Destination("node1", 2224),
                        Destination("a", -1),
                        Destination("b", 0),
                        Destination("c", 1000000000),
                    ],
                ),
            }
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="port for node 'node1'",
                    option_value=-1,
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="port for node 'node1'",
                    option_value=0,
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="port for node 'node1'",
                    option_value=1000000000,
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

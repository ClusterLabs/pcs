from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
from os.path import join

from pcs.common import report_codes
from pcs.lib.booth import configuration
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.settings import booth_config_dir as BOOTH_CONFIG_DIR
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_mock import mock
from pcs.test.tools.assertions import assert_report_item_list_equal

class AddTicketTest(TestCase):
    @mock.patch("pcs.lib.booth.configuration.validate_ticket_unique")
    @mock.patch("pcs.lib.booth.configuration.validate_ticket_name")
    def test_successfully_add_ticket(
        self, mock_validate_ticket_name, mock_validate_ticket_unique
    ):
        self.assertEqual(
            configuration.add_ticket(
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

class RemoveTicketTest(TestCase):
    @mock.patch("pcs.lib.booth.configuration.validate_ticket_exists")
    def test_successfully_remove_ticket(self, mock_validate_ticket_exists):
        self.assertEqual(
            configuration.remove_ticket(
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


class BuildTest(TestCase):
    def test_succesfully_create_content_without_tickets(self):
        self.assertEqual(
            configuration.build({
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
            configuration.build({
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
            configuration.build({
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

class ParseTest(TestCase):
    def test_returns_parsed_config_when_correct_config(self):
        self.assertEqual(
            configuration.parse("\n".join([
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
            lambda: configuration.parse("\n".join([
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
            lambda: configuration.parse("nonsense"),
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
            lambda: configuration.parse("nonsense = 1.1.1.1"),
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

class ValidateTicketNameTest(TestCase):
    def test_accept_valid_ticket_name(self):
        configuration.validate_ticket_name("abc")

    def test_refuse_bad_ticket_name(self):
        assert_raise_library_error(
            lambda: configuration.validate_ticket_name("@ticket"),
            (
                severities.ERROR,
                report_codes.BOOTH_TICKET_NAME_INVALID,
                {
                    "ticket_name": "@ticket",
                },
            ),
        )

class ValidateTicketUniqueTest(TestCase):
    def test_raises_on_duplicate_ticket(self):
        assert_raise_library_error(
            lambda: configuration.validate_ticket_unique(["A"], "A"),
            (
                severities.ERROR,
                report_codes.BOOTH_TICKET_DUPLICATE,
                {
                    "ticket_name": "A",
                },
            ),
        )

class ValidateTicketExistsTest(TestCase):
    def test_raises_on_duplicate_ticket(self):
        assert_raise_library_error(
            lambda: configuration.validate_ticket_exists(["B"], "A"),
            (
                severities.ERROR,
                report_codes.BOOTH_TICKET_DOES_NOT_EXIST,
                {
                    "ticket_name": "A",
                },
            ),
        )


@mock.patch("os.listdir")
class GetAllConfigsTest(TestCase):
    def test_success(self, mock_listdir):
        mock_listdir.return_value = [
            "name1", "name2.conf", "name.conf.conf", ".conf", "name3.conf"
        ]
        self.assertEqual(
            ["name2.conf", "name.conf.conf", ".conf", "name3.conf"],
            configuration.get_all_configs()
        )
        mock_listdir.assert_called_once_with(BOOTH_CONFIG_DIR)


class ReadConfigTest(TestCase):
    def test_success(self):
        self.maxDiff = None
        mock_open = mock.mock_open(read_data="config content")
        with mock.patch(
            "pcs.lib.booth.configuration.open", mock_open, create=True
        ):
            self.assertEqual(
                "config content",
                configuration._read_config("my-file.conf")
            )

        self.assertEqual(
            [
                mock.call(join(BOOTH_CONFIG_DIR, "my-file.conf"), "r"),
                mock.call().__enter__(),
                mock.call().read(),
                mock.call().__exit__(None, None, None)
            ],
            mock_open.mock_calls
        )


@mock.patch("pcs.lib.booth.configuration._read_config")
@mock.patch("pcs.lib.booth.configuration.get_all_configs")
class ReadConfigsTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()

    def test_success(self, mock_get_configs, mock_read):
        def _mock_read_cfg(file):
            if file == "name1.conf":
                return "config1"
            elif file == "name2.conf":
                return "config2"
            elif file == "name3.conf":
                return "config3"
            else:
                raise AssertionError("unexpected input: {0}".format(file))
        mock_get_configs.return_value = [
            "name1.conf", "name2.conf", "name3.conf"
        ]
        mock_read.side_effect = _mock_read_cfg

        self.assertEqual(
            {
                "name1.conf": "config1",
                "name2.conf": "config2",
                "name3.conf": "config3"
            },
            configuration.read_configs(self.mock_reporter)
        )

        mock_get_configs.assert_called_once_with()
        self.assertEqual(3, mock_read.call_count)
        mock_read.assert_has_calls([
            mock.call("name1.conf"),
            mock.call("name2.conf"),
            mock.call("name3.conf")
        ])
        self.assertEqual(0, len(self.mock_reporter.report_item_list))

    def test_skip_failed(self, mock_get_configs, mock_read):
        def _mock_read_cfg(file):
            if file in ["name1.conf", "name3.conf"]:
                raise EnvironmentError()
            elif file == "name2.conf":
                return "config2"
            else:
                raise AssertionError("unexpected input: {0}".format(file))

        mock_get_configs.return_value = [
            "name1.conf", "name2.conf", "name3.conf"
        ]
        mock_read.side_effect = _mock_read_cfg

        self.assertEqual(
            {"name2.conf": "config2"},
            configuration.read_configs(self.mock_reporter, True)
        )
        mock_get_configs.assert_called_once_with()
        self.assertEqual(3, mock_read.call_count)
        mock_read.assert_has_calls([
            mock.call("name1.conf"),
            mock.call("name2.conf"),
            mock.call("name3.conf")
        ])
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severities.WARNING,
                    report_codes.BOOTH_CONFIG_READ_ERROR,
                    {"name": "name1.conf"}
                ),
                (
                    severities.WARNING,
                    report_codes.BOOTH_CONFIG_READ_ERROR,
                    {"name": "name3.conf"}
                )
            ]
        )

    def test_do_not_skip_failed(self, mock_get_configs, mock_read):
        def _mock_read_cfg(file):
            if file in ["name1.conf", "name3.conf"]:
                raise EnvironmentError()
            elif file == "name2.conf":
                return "config2"
            else:
                raise AssertionError("unexpected input: {0}".format(file))

        mock_get_configs.return_value = [
            "name1.conf", "name2.conf", "name3.conf"
        ]
        mock_read.side_effect = _mock_read_cfg

        assert_raise_library_error(
            lambda: configuration.read_configs(self.mock_reporter),
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_READ_ERROR,
                {"name": "name1.conf"},
                report_codes.SKIP_UNREADABLE_CONFIG
            ),
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_READ_ERROR,
                {"name": "name3.conf"},
                report_codes.SKIP_UNREADABLE_CONFIG
            )
        )
        mock_get_configs.assert_called_once_with()
        self.assertEqual(3, mock_read.call_count)
        mock_read.assert_has_calls([
            mock.call("name1.conf"),
            mock.call("name2.conf"),
            mock.call("name3.conf")
        ])
        self.assertEqual(2, len(self.mock_reporter.report_item_list))


@mock.patch("pcs.lib.booth.configuration.parse")
@mock.patch("pcs.lib.booth.configuration.read_authfile")
class ReadAuthFileFromConfigsTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()

    def test_success(self, mock_read, mock_parse):
        def _mock_read(_, path):
            if path == "/etc/booth/k1.key":
                return "key1"
            elif path == "/etc/booth/k2.key":
                return "key2"
            else:
                raise AssertionError("unexpected input: {0}".format(path))

        configs = {
            "config1.conf": "config1",
            "config2.conf": "config2",
            "config3.conf": "config3"
        }

        def _mock_parse(config):
            if config == "config1":
                return {"authfile": "/etc/booth/k1.key"}
            elif config == "config2":
                return {"authfile": "/etc/booth/k2.key"}
            elif config == "config3":
                return {}
            else:
                raise AssertionError("unexpected input: {0}".format(config))

        mock_read.side_effect = _mock_read
        mock_parse.side_effect = _mock_parse

        self.assertEqual(
            {
                "k1.key": "key1",
                "k2.key": "key2"
            },
            configuration.read_authfiles_from_configs(
                self.mock_reporter, configs.values()
            )
        )
        self.assertEqual(3, mock_parse.call_count)
        mock_parse.has_calls([
            mock.call(configs["config1.conf"]),
            mock.call(configs["config2.conf"]),
            mock.call(configs["config3.conf"]),
        ])
        self.assertEqual(2, mock_read.call_count)
        mock_read.has_calls([
            mock.call(self.mock_reporter, "/etc/booth/k1.key"),
            mock.call(self.mock_reporter, "/etc/booth/k2.key")
        ])


class ReadAuthfileTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()
        self.maxDiff = None

    def test_success(self):
        path = join(BOOTH_CONFIG_DIR, "file.key")
        mock_open = mock.mock_open(read_data="key")

        with mock.patch(
            "pcs.lib.booth.configuration.open", mock_open, create=True
        ):
            self.assertEqual(
                "key", configuration.read_authfile(self.mock_reporter, path)
            )

        self.assertEqual(
            [
                mock.call(path, "rb"),
                mock.call().__enter__(),
                mock.call().read(),
                mock.call().__exit__(None, None, None)
            ],
            mock_open.mock_calls
        )
        self.assertEqual(0, len(self.mock_reporter.report_item_list))

    def test_path_none(self):
        self.assertTrue(
            configuration.read_authfile(self.mock_reporter, None) is None
        )
        self.assertEqual(0, len(self.mock_reporter.report_item_list))

    def test_invalid_path(self):
        path = "/not/etc/booth/booth.key"
        self.assertTrue(
            configuration.read_authfile(self.mock_reporter, path) is None
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                severities.WARNING,
                report_codes.BOOTH_UNSUPORTED_FILE_LOCATION,
                {"file": path}
            )]
        )

    def test_not_abs_path(self):
        path = "/etc/booth/../booth.key"
        self.assertTrue(
            configuration.read_authfile(self.mock_reporter, path) is None
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                severities.WARNING,
                report_codes.BOOTH_UNSUPORTED_FILE_LOCATION,
                {"file": path}
            )]
        )

    def test_read_failure(self):
        path = join(BOOTH_CONFIG_DIR, "file.key")
        mock_open = mock.mock_open()
        mock_open().read.side_effect = EnvironmentError("reason")

        with mock.patch(
            "pcs.lib.booth.configuration.open", mock_open, create=True
        ):
            return_value = configuration.read_authfile(self.mock_reporter, path)

        self.assertTrue(return_value is None)

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                severities.WARNING,
                report_codes.FILE_IO_ERROR,
                {
                    "file_role": "authfile",
                    "file_path": path,
                    "reason": "reason",
                }
            )]
        )

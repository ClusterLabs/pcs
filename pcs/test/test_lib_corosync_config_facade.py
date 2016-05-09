from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
import re

from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.misc import (
    ac,
    get_test_resource as rc,
)

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severity

import pcs.lib.corosync.config_facade as lib


class FromStringTest(TestCase):
    def test_success(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(facade.__class__, lib.ConfigFacade)
        self.assertEqual(facade.config.export(), config)

    def test_parse_error_missing_brace(self):
        config = "section {"
        assert_raise_library_error(
            lambda: lib.ConfigFacade.from_string(config),
            (
                severity.ERROR,
                report_codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE,
                {}
            )
        )

    def test_parse_error_unexpected_brace(self):
        config = "}"
        assert_raise_library_error(
            lambda: lib.ConfigFacade.from_string(config),
            (
                severity.ERROR,
                report_codes.PARSE_ERROR_COROSYNC_CONF_UNEXPECTED_CLOSING_BRACE,
                {}
            )
        )


class GetNodesTest(TestCase):
    def assert_equal_nodelist(self, expected_nodes, real_nodelist):
        real_nodes = [
            {"ring0": n.ring0, "ring1": n.ring1, "label": n.label, "id": n.id}
            for n in real_nodelist
        ]
        self.assertEqual(expected_nodes, real_nodes)

    def test_no_nodelist(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        nodes = facade.get_nodes()
        self.assertEqual(0, len(nodes))

    def test_empty_nodelist(self):
        config = """\
nodelist {
}
"""
        facade = lib.ConfigFacade.from_string(config)
        nodes = facade.get_nodes()
        self.assertEqual(0, len(nodes))

    def test_one_nodelist(self):
        config = """\
nodelist {
    node {
        ring0_addr: n1a
        nodeid: 1
    }

    node {
        ring0_addr: n2a
        ring1_addr: n2b
        name: n2n
        nodeid: 2
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        nodes = facade.get_nodes()
        self.assertEqual(2, len(nodes))
        self.assert_equal_nodelist(
            [
                {"ring0": "n1a", "ring1": None, "label": "n1a", "id": "1"},
                {"ring0": "n2a", "ring1": "n2b", "label": "n2n", "id": "2"},
            ],
            nodes
        )

    def test_more_nodelists(self):
        config = """\
nodelist {
    node {
        ring0_addr: n1a
        nodeid: 1
    }
}

nodelist {
    node {
        ring0_addr: n2a
        ring1_addr: n2b
        name: n2n
        nodeid: 2
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        nodes = facade.get_nodes()
        self.assertEqual(2, len(nodes))
        self.assert_equal_nodelist(
            [
                {"ring0": "n1a", "ring1": None, "label": "n1a", "id": "1"},
                {"ring0": "n2a", "ring1": "n2b", "label": "n2n", "id": "2"},
            ],
            nodes
        )


class GetQuorumOptionsTest(TestCase):
    def test_no_quorum(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)

    def test_empty_quorum(self):
        config = """\
quorum {
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)

    def test_no_options(self):
        config = """\
quorum {
    provider: corosync_votequorum
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)

    def test_some_options(self):
        config = """\
quorum {
    provider: corosync_votequorum
    wait_for_all: 0
    nonsense: ignored
    auto_tie_breaker: 1
    last_man_standing: 0
    last_man_standing_window: 1000
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual(
            {
                "auto_tie_breaker": "1",
                "last_man_standing": "0",
                "last_man_standing_window": "1000",
                "wait_for_all": "0",
            },
            options
        )

    def test_option_repeated(self):
        config = """\
quorum {
    wait_for_all: 0
    wait_for_all: 1
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual(
            {
                "wait_for_all": "1",
            },
            options
        )

    def test_quorum_repeated(self):
        config = """\
quorum {
    wait_for_all: 0
    last_man_standing: 0
}
quorum {
    last_man_standing_window: 1000
    wait_for_all: 1
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual(
            {
                "last_man_standing": "0",
                "last_man_standing_window": "1000",
                "wait_for_all": "1",
            },
            options
        )


class SetQuorumOptionsTest(TestCase):
    def get_two_node(self, facade):
        two_node = None
        for quorum in facade.config.get_sections("quorum"):
            for dummy_name, value in quorum.get_attributes("two_node"):
                two_node = value
        return two_node

    def test_add_missing_section(self):
        config = ""
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.set_quorum_options(reporter, {"wait_for_all": "0"})
        self.assertEqual(
            """\
quorum {
    wait_for_all: 0
}
""",
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_del_missing_section(self):
        config = ""
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.set_quorum_options(reporter, {"wait_for_all": ""})
        self.assertEqual("", facade.config.export())
        self.assertEqual([], reporter.report_item_list)

    def test_add_all_options(self):
        config = open(rc("corosync.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        expected_options = {
            "auto_tie_breaker": "1",
            "last_man_standing": "0",
            "last_man_standing_window": "1000",
            "wait_for_all": "0",
        }
        facade.set_quorum_options(reporter, expected_options)

        test_facade = lib.ConfigFacade.from_string(facade.config.export())
        self.assertEqual(
            expected_options,
            test_facade.get_quorum_options()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_complex(self):
        config = """\
quorum {
    wait_for_all: 0
    last_man_standing_window: 1000
}
quorum {
    wait_for_all: 0
    last_man_standing: 1
}
"""
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.set_quorum_options(
            reporter,
            {
                "auto_tie_breaker": "1",
                "wait_for_all": "1",
                "last_man_standing_window": "",
            }
        )

        test_facade = lib.ConfigFacade.from_string(facade.config.export())
        self.assertEqual(
            {
                "auto_tie_breaker": "1",
                "last_man_standing": "1",
                "wait_for_all": "1",
            },
            test_facade.get_quorum_options()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_2nodes_atb_on(self):
        config = open(rc("corosync.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(2, len(facade.get_nodes()))

        facade.set_quorum_options(reporter, {"auto_tie_breaker": "1"})

        self.assertEqual(
            "1",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )
        self.assertEqual([], reporter.report_item_list)

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node is None or two_node == "0")

    def test_2nodes_atb_off(self):
        config = open(rc("corosync.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(2, len(facade.get_nodes()))

        facade.set_quorum_options(reporter, {"auto_tie_breaker": "0"})

        self.assertEqual(
            "0",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )
        self.assertEqual([], reporter.report_item_list)

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node == "1")

    def test_3nodes_atb_on(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(3, len(facade.get_nodes()))

        facade.set_quorum_options(reporter, {"auto_tie_breaker": "1"})

        self.assertEqual(
            "1",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )
        self.assertEqual([], reporter.report_item_list)

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node is None or two_node == "0")

    def test_3nodes_atb_off(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(3, len(facade.get_nodes()))

        facade.set_quorum_options(reporter, {"auto_tie_breaker": "0"})

        self.assertEqual(
            "0",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )
        self.assertEqual([], reporter.report_item_list)

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node is None or two_node == "0")

    def test_invalid_value_no_effect_on_config(self):
        config= """\
quorum {
    auto_tie_breaker: 1
    wait_for_all: 1
    last_man_standing: 1
}
"""
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        options = {
            "auto_tie_breaker": "",
            "wait_for_all": "nonsense",
            "last_man_standing": "0",
            "last_man_standing_window": "250",
        }
        assert_raise_library_error(
            lambda: facade.set_quorum_options(reporter, options),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "wait_for_all",
                    "option_value": "nonsense",
                    "allowed_values_raw": ("0", "1"),
                    "allowed_values": "0 or 1",
                }
            )
        )
        self.assertEqual(
            lib.ConfigFacade.from_string(config).get_quorum_options(),
            facade.get_quorum_options()
        )

    def test_invalid_all_values(self):
        config= ""
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        options = {
            "auto_tie_breaker": "atb",
            "last_man_standing": "lms",
            "last_man_standing_window": "lmsw",
            "wait_for_all": "wfa",
        }
        assert_raise_library_error(
            lambda: facade.set_quorum_options(reporter, options),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "auto_tie_breaker",
                    "option_value": "atb",
                    "allowed_values_raw": ("0", "1"),
                    "allowed_values": "0 or 1",
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "last_man_standing",
                    "option_value": "lms",
                    "allowed_values_raw": ("0", "1"),
                    "allowed_values": "0 or 1",
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "last_man_standing_window",
                    "option_value": "lmsw",
                    "allowed_values_raw": ("integer", ),
                    "allowed_values": "integer",
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "wait_for_all",
                    "option_value": "wfa",
                    "allowed_values_raw": ("0", "1"),
                    "allowed_values": "0 or 1",
                }
            )
        )
        self.assertEqual(
            lib.ConfigFacade.from_string(config).get_quorum_options(),
            facade.get_quorum_options()
        )

    def test_invalid_option(self):
        config= ""
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        options = {
            "auto_tie_breaker": "1",
            "nonsense1": "0",
            "nonsense2": "doesnt matter",
        }
        assert_raise_library_error(
            lambda: facade.set_quorum_options(reporter, options),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "type": "quorum",
                    "option": "nonsense1",
                    "allowed_raw": (
                        "auto_tie_breaker", "last_man_standing",
                        "last_man_standing_window", "wait_for_all"
                    ),
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "type": "quorum",
                    "option": "nonsense2",
                    "allowed_raw": (
                        "auto_tie_breaker", "last_man_standing",
                        "last_man_standing_window", "wait_for_all"
                    ),
                }
            )
        )
        self.assertEqual(
            lib.ConfigFacade.from_string(config).get_quorum_options(),
            facade.get_quorum_options()
        )


class HasQuorumDeviceTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())

    def test_no_device(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())

    def test_empty_device(self):
        config = """\
quorum {
    device {
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())

    def test_device_set(self):
        config = """\
quorum {
    device {
        model: net
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertTrue(facade.has_quorum_device())

    def test_no_model(self):
        config = """\
quorum {
    device {
        option: value
        net {
            host: 127.0.0.1
        }
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())


class GetQuorumDeviceSettingsTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {}),
            facade.get_quorum_device_settings()
        )

    def test_no_device(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {}),
            facade.get_quorum_device_settings()
        )

    def test_empty_device(self):
        config = """\
quorum {
    device {
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {}),
            facade.get_quorum_device_settings()
        )

    def test_no_model(self):
        config = """\
quorum {
    device {
        option: value
        net {
            host: 127.0.0.1
        }
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {"option": "value"}),
            facade.get_quorum_device_settings()
        )

    def test_configured_properly(self):
        config = """\
quorum {
    device {
        option: value
        model: net
        net {
            host: 127.0.0.1
        }
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            ("net", {"host": "127.0.0.1"}, {"option": "value"}),
            facade.get_quorum_device_settings()
        )

    def test_more_devices_one_quorum(self):
        config = """\
quorum {
    device {
        option0: valueX
        option1: value1
        model: disk
        net {
            host: 127.0.0.1
        }
    }
    device {
        option0: valueY
        option2: value2
        model: net
        disk {
            path: /dev/quorum_disk
        }
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (
                "net",
                {"host": "127.0.0.1"},
                {"option0": "valueY", "option1": "value1", "option2": "value2"}
            ),
            facade.get_quorum_device_settings()
        )

    def test_more_devices_more_quorum(self):
        config = """\
quorum {
    device {
        option0: valueX
        option1: value1
        model: disk
        net {
            host: 127.0.0.1
        }
    }
}
quorum {
    device {
        option0: valueY
        option2: value2
        model: net
        disk {
            path: /dev/quorum_disk
        }
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (
                "net",
                {"host": "127.0.0.1"},
                {"option0": "valueY", "option1": "value1", "option2": "value2"}
            ),
            facade.get_quorum_device_settings()
        )


class AddQuorumDeviceTest(TestCase):
    def test_already_exists(self):
        config = """\
totem {
    version: 2
}

quorum {
    provider: corosync_votequorum

    device {
        option: value
        model: net

        net {
            host: 127.0.0.1
        }
    }
}
"""
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(
                reporter,
                "net",
                {"host": "127.0.0.1"},
                {}
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_ALREADY_DEFINED,
                {}
            )
        )
        ac(config, facade.config.export())

    def test_success_net_minimal(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1"},
            {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: net

        net {
            host: 127.0.0.1
        }
    }"""
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_success_net_full(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {
                "host": "127.0.0.1",
                "port": "4433",
                "algorithm": "ffsplit",
                "connect_timeout": "12345",
                "force_ip_version": "4",
                "tie_breaker": "lowest",
            },
            {
                "timeout": "23456",
                "sync_timeout": "34567"
            }
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        sync_timeout: 34567
        timeout: 23456
        model: net

        net {
            algorithm: ffsplit
            connect_timeout: 12345
            force_ip_version: 4
            host: 127.0.0.1
            port: 4433
            tie_breaker: lowest
        }
    }"""
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_succes_net_lms_3node(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1", "algorithm": "lms"},
            {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: net

        net {
            algorithm: lms
            host: 127.0.0.1
        }
    }"""
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_succes_net_2nodelms_3node(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1", "algorithm": "2nodelms"},
            {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: net

        net {
            algorithm: lms
            host: 127.0.0.1
        }
    }"""
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_succes_net_lms_2node(self):
        config = open(rc("corosync.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1", "algorithm": "lms"},
            {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: net

        net {
            algorithm: 2nodelms
            host: 127.0.0.1
        }
    }"""
            ).replace("    two_node: 1\n", ""),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_succes_net_2nodelms_2node(self):
        config = open(rc("corosync.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1", "algorithm": "2nodelms"},
            {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: net

        net {
            algorithm: 2nodelms
            host: 127.0.0.1
        }
    }"""
            ).replace("    two_node: 1\n", ""),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_remove_conflicting_options(self):
        config = open(rc("corosync.conf")).read()
        config = config.replace(
            "    two_node: 1\n",
            "\n".join([
                "    two_node: 1",
                "    auto_tie_breaker: 1",
                "    last_man_standing: 1",
                "    last_man_standing_window: 987",
                "    allow_downscale: 1",
                ""
            ])
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1"},
            {}
        )
        ac(
            re.sub(
                re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
                """\
quorum {
    provider: corosync_votequorum

    device {
        model: net

        net {
            host: 127.0.0.1
        }
    }
}""",
                config
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_remove_old_configuration(self):
        config = """\
quorum {
    provider: corosync_votequorum
    device {
        option: value_old1
    }
}
quorum {
    provider: corosync_votequorum
    device {
        option: value_old2
    }
}
        """
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1"},
            {}
        )
        ac(
            """\
quorum {
    provider: corosync_votequorum
}

quorum {
    provider: corosync_votequorum

    device {
        model: net

        net {
            host: 127.0.0.1
        }
    }
}
"""
            ,
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_bad_model(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(reporter, "invalid", {}, {}),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "model",
                    "option_value": "invalid",
                    "allowed_values_raw": ("net", ),
                },
                True
            )
        )
        ac(config, facade.config.export())

    def test_missing_required_options_net(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(reporter, "net", {}, {}),
            (
                severity.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {"name": "host"},
                False
            )
        )
        ac(config, facade.config.export())

    def test_bad_options_net(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(
                reporter,
                "net",
                {
                    "host": "",
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                    "model": "some model",
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "algorithm",
                    "option_value": "bad algorithm",
                    "allowed_values_raw": ("2nodelms", "ffsplit", "lms"),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option": "bad_model_option",
                    "type": "quorum device model",
                    "allowed_raw": [
                        "algorithm",
                        "connect_timeout",
                        "force_ip_version",
                        "host",
                        "port",
                        "tie_breaker",
                    ],
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "connect_timeout",
                    "option_value": "-1",
                    "allowed_values_raw": ("1000-120000", ),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "force_ip_version",
                    "option_value": "3",
                    "allowed_values_raw": ("0", "4", "6"),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {"name": "host"},
                False
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "port",
                    "option_value": "65537",
                    "allowed_values_raw": ("1-65535", ),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "tie_breaker",
                    "option_value": "125",
                    "allowed_values_raw": ("lowest", "highest", "valid node id"),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option": "bad_generic_option",
                    "type": "quorum device",
                    "allowed_raw": ["sync_timeout", "timeout"],
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option": "model",
                    "type": "quorum device",
                    "allowed_raw": ["sync_timeout", "timeout"],
                },
                False
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "sync_timeout",
                    "option_value": "-3",
                    "allowed_values_raw": ("integer", ),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "timeout",
                    "option_value": "-2",
                    "allowed_values_raw": ("integer", ),
                },
                True
            )
        )
        ac(config, facade.config.export())

class UpdateQuorumDeviceTest(TestCase):
    def fixture_add_device(self, config):
        return re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            """\
quorum {
    provider: corosync_votequorum

    device {
        timeout: 12345
        model: net

        net {
            host: 127.0.0.1
            port: 4433
        }
    }
}""",
            config
        )

    def test_not_existing(self):
        config = open(rc("corosync.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                reporter,
                {"host": "127.0.0.1"},
                {}
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )
        ac(config, facade.config.export())

    def test_success_model_options_net(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {"host": "127.0.0.2", "port": "", "algorithm": "ffsplit"},
            {}
        )
        ac(
            config.replace(
                "host: 127.0.0.1\n            port: 4433",
                "host: 127.0.0.2\n            algorithm: ffsplit"
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_success_net_3node_2nodelms(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {"algorithm": "2nodelms"},
            {}
        )
        ac(
            config.replace(
                "port: 4433",
                "port: 4433\n            algorithm: lms"
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_success_net_doesnt_require_host(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(reporter, {"port": "4444"}, {})
        ac(
            config.replace(
                "host: 127.0.0.1\n            port: 4433",
                "host: 127.0.0.1\n            port: 4444"
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_net_host_cannot_be_removed(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(reporter, {"host": ""}, {}),
            (
                severity.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {"name": "host"},
                False
            )
        )
        ac(config, facade.config.export())

    def test_bad_net_options(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                reporter,
                {
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {}
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "algorithm",
                    "option_value": "bad algorithm",
                    "allowed_values_raw": ("2nodelms", "ffsplit", "lms"),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option": "bad_model_option",
                    "type": "quorum device model",
                    "allowed_raw": [
                        "algorithm",
                        "connect_timeout",
                        "force_ip_version",
                        "host",
                        "port",
                        "tie_breaker",
                    ],
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "connect_timeout",
                    "option_value": "-1",
                    "allowed_values_raw": ("1000-120000", ),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "force_ip_version",
                    "option_value": "3",
                    "allowed_values_raw": ("0", "4", "6"),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "port",
                    "option_value": "65537",
                    "allowed_values_raw": ("1-65535", ),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "tie_breaker",
                    "option_value": "125",
                    "allowed_values_raw": ("lowest", "highest", "valid node id"),
                },
                True
            ),
        )
        ac(config, facade.config.export())

    def test_success_generic_options(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {},
            {"timeout": "", "sync_timeout": "23456"}
        )
        ac(
            config.replace(
                "timeout: 12345\n        model: net",
                "model: net\n        sync_timeout: 23456",
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_success_both_options(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {"port": "4444"},
            {"timeout": "23456"}
        )
        ac(
            config
                .replace("port: 4433", "port: 4444")
                .replace("timeout: 12345", "timeout: 23456")
            ,
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_bad_generic_options(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                reporter,
                {},
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                    "model": "some model",
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option": "bad_generic_option",
                    "type": "quorum device",
                    "allowed_raw": ["sync_timeout", "timeout"],
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option": "model",
                    "type": "quorum device",
                    "allowed_raw": ["sync_timeout", "timeout"],
                },
                False
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "sync_timeout",
                    "option_value": "-3",
                    "allowed_values_raw": ("integer", ),
                },
                True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "timeout",
                    "option_value": "-2",
                    "allowed_values_raw": ("integer", ),
                },
                True
            )
        )
        ac(config, facade.config.export())


class RemoveQuorumDeviceTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            facade.remove_quorum_device,
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )

    def test_no_device(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            facade.remove_quorum_device,
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )

    def test_remove_all_devices(self):
        config_no_devices = open(rc("corosync-3nodes.conf")).read()
        config = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            """\
quorum {
    provider: corosync_votequorum

    device {
        option: value
        model: net

        net {
            host: 127.0.0.1
            port: 4433
        }
    }

    device {
        option: value
    }
}

quorum {
    device {
        option: value
        model: disk

        net {
            host: 127.0.0.1
            port: 4433
        }
    }
}""",
            config_no_devices
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.remove_quorum_device()
        ac(
            config_no_devices,
            facade.config.export()
        )

    def test_restore_two_node(self):
        config_no_devices = open(rc("corosync.conf")).read()
        config = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            """\
quorum {
    provider: corosync_votequorum

    device {
        option: value
        model: net

        net {
            host: 127.0.0.1
            port: 4433
        }
    }
}""",
            config_no_devices
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.remove_quorum_device()
        ac(
            config_no_devices,
            facade.config.export()
        )

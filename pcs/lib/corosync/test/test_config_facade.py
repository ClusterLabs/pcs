import re
from textwrap import dedent
from unittest import TestCase

from pcs.test.tools import fixture
from pcs.test.tools.assertions import (
    ac,
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.misc import get_test_resource as rc, outdent

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severity

import pcs.lib.corosync.config_facade as lib


class FromStringTest(TestCase):
    def test_success(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(facade.__class__, lib.ConfigFacade)
        self.assertEqual(facade.config.export(), config)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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


class GetClusterNametest(TestCase):
    def test_no_name(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_name(self):
        config = "totem {\n cluster_name:\n}\n"
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_one_name(self):
        config = "totem {\n cluster_name: test\n}\n"
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("test", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_names(self):
        config = "totem {\n cluster_name: test\n cluster_name: TEST\n}\n"
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("TEST", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_sections(self):
        config = "totem{\ncluster_name:test\n}\ntotem{\ncluster_name:TEST\n}\n"
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("TEST", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_nodelist(self):
        config = """\
nodelist {
}
"""
        facade = lib.ConfigFacade.from_string(config)
        nodes = facade.get_nodes()
        self.assertEqual(0, len(nodes))
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class GetQuorumOptionsTest(TestCase):
    def test_no_quorum(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_quorum(self):
        config = """\
quorum {
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_options(self):
        config = """\
quorum {
    provider: corosync_votequorum
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class IsEnabledAutoTieBreaker(TestCase):
    def test_enabled(self):
        config = """\
quorum {
    auto_tie_breaker: 1
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertTrue(facade.is_enabled_auto_tie_breaker())

    def test_disabled(self):
        config = """\
quorum {
    auto_tie_breaker: 0
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.is_enabled_auto_tie_breaker())

    def test_no_value(self):
        config = """\
quorum {
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.is_enabled_auto_tie_breaker())


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
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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
                    "allowed_values": ("0", "1"),
                }
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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
                    "allowed_values": ("0", "1"),
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "last_man_standing",
                    "option_value": "lms",
                    "allowed_values": ("0", "1"),
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "last_man_standing_window",
                    "option_value": "lmsw",
                    "allowed_values": "a positive integer",
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "wait_for_all",
                    "option_value": "wfa",
                    "allowed_values": ("0", "1"),
                }
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["nonsense1", "nonsense2"],
                    "option_type": "quorum",
                    "allowed": [
                        "auto_tie_breaker",
                        "last_man_standing",
                        "last_man_standing_window",
                        "wait_for_all"
                    ],
                    "allowed_patterns": [],
                }
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            lib.ConfigFacade.from_string(config).get_quorum_options(),
            facade.get_quorum_options()
        )

    def test_qdevice_incompatible_options(self):
        config = open(rc("corosync-3nodes-qdevice.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        options = {
            "auto_tie_breaker": "1",
            "last_man_standing": "1",
            "last_man_standing_window": "250",
        }
        assert_raise_library_error(
            lambda: facade.set_quorum_options(reporter, options),
            (
                severity.ERROR,
                report_codes.COROSYNC_OPTIONS_INCOMPATIBLE_WITH_QDEVICE,
                {
                    "options_names": [
                        "auto_tie_breaker",
                        "last_man_standing",
                        "last_man_standing_window",
                    ],
                }
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            lib.ConfigFacade.from_string(config).get_quorum_options(),
            facade.get_quorum_options()
        )

    def test_qdevice_compatible_options(self):
        config = open(rc("corosync-3nodes-qdevice.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        expected_options = {
            "wait_for_all": "1",
        }
        facade.set_quorum_options(reporter, expected_options)

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        test_facade = lib.ConfigFacade.from_string(facade.config.export())
        self.assertEqual(
            expected_options,
            test_facade.get_quorum_options()
        )
        self.assertEqual([], reporter.report_item_list)


class HasQuorumDeviceTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_device(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_device(self):
        config = """\
quorum {
    device {
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class GetQuorumDeviceSettingsTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_device(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_device(self):
        config = dedent("""\
            quorum {
                device {
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_model(self):
        config = dedent("""\
            quorum {
                device {
                    option: value
                    net {
                        host: 127.0.0.1
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {"option": "value"}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_configured_properly(self):
        config = dedent("""\
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
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            ("net", {"host": "127.0.0.1"}, {"option": "value"}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_configured_properly_heuristics(self):
        config = dedent("""\
            quorum {
                device {
                    option: value
                    model: net
                    net {
                        host: 127.0.0.1
                    }
                    heuristics {
                        mode: on
                        exec_ls: test -f /tmp/test
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (
                "net",
                {"host": "127.0.0.1"},
                {"option": "value"},
                {"exec_ls": "test -f /tmp/test", "mode": "on"}
            ),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_devices_one_quorum(self):
        config = dedent("""\
            quorum {
                device {
                    option0: valueX
                    option1: value1
                    model: disk
                    net {
                        host: 127.0.0.1
                    }
                    heuristics {
                        mode: sync
                        exec_ls: test -f /tmp/test
                    }
                }
                device {
                    option0: valueY
                    option2: value2
                    model: net
                    disk {
                        path: /dev/quorum_disk
                    }
                    heuristics {
                        mode: on
                    }
                    heuristics {
                        timeout: 5
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (
                "net",
                {"host": "127.0.0.1"},
                {"option0": "valueY", "option1": "value1", "option2": "value2"},
                {"exec_ls": "test -f /tmp/test", "mode": "on", "timeout": "5"}
            ),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_devices_more_quorum(self):
        config = dedent("""\
            quorum {
                device {
                    option0: valueX
                    option1: value1
                    model: disk
                    net {
                        host: 127.0.0.1
                    }
                    heuristics {
                        mode: sync
                        exec_ls: test -f /tmp/test
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
                    heuristics {
                        mode: on
                    }
                    heuristics {
                        timeout: 5
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (
                "net",
                {"host": "127.0.0.1"},
                {"option0": "valueY", "option1": "value1", "option2": "value2"},
                {"exec_ls": "test -f /tmp/test", "mode": "on", "timeout": "5"}
            ),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class AddQuorumDeviceTest(TestCase):
    def heuristic_no_exec_warning(self, mode, warn):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
            {},
            {"mode": mode}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum\n",
                outdent("""\
                    provider: corosync_votequorum

                    device {
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: 127.0.0.1
                        }

                        heuristics {
                            mode: *mode*
                        }
                    }
                """.replace("*mode*", mode))
            ),
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        expected_reports = []
        if warn:
            expected_reports.append(
                fixture.warn(
                    report_codes.COROSYNC_QUORUM_HEURISTICS_ENABLED_WITH_NO_EXEC
                )
            )
        assert_report_item_list_equal(
            reporter.report_item_list,
            expected_reports
        )

    def test_already_exists(self):
        config = dedent("""\
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
                        algorithm: ffsplit
                    }
                }
            }
            """)

        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(
                reporter,
                "net",
                {"host": "127.0.0.1", "algorithm": "ffsplit"},
                {},
                {}
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_ALREADY_DEFINED,
                {},
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_success_net_minimal_ffsplit(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
            {},
            {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: net
        votes: 1

        net {
            algorithm: ffsplit
            host: 127.0.0.1
        }
    }"""
            ),
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual([], reporter.report_item_list)

    def test_success_net_minimal_lms(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1", "algorithm": "lms"},
            {},
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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual([], reporter.report_item_list)

    def test_success_remove_nodes_votes(self):
        config = open(rc("corosync-3nodes.conf")).read()
        config_votes = config.replace("node {", "node {\nquorum_votes: 2")
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config_votes)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1", "algorithm": "lms"},
            {},
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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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
            },
            {
                "mode": "on",
                "timeout": "5",
                "sync_timeout": "15",
                "interval": "30",
                "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                "exec_ls": "test -f /tmp/test",
            }
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum\n",
                outdent("""\
                    provider: corosync_votequorum

                    device {
                        sync_timeout: 34567
                        timeout: 23456
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            connect_timeout: 12345
                            force_ip_version: 4
                            host: 127.0.0.1
                            port: 4433
                            tie_breaker: lowest
                        }

                        heuristics {
                            exec_ls: test -f /tmp/test
                            exec_ping: ping -q -c 1 "127.0.0.1"
                            interval: 30
                            mode: on
                            sync_timeout: 15
                            timeout: 5
                        }
                    }
                """)
            ),
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual([], reporter.report_item_list)

    def test_succes_heuristics_on_no_exec(self):
        self.heuristic_no_exec_warning("on", True)

    def test_succes_heuristics_sync_no_exec(self):
        self.heuristic_no_exec_warning("sync", True)

    def test_succes_heuristics_off_no_exec(self):
        self.heuristic_no_exec_warning("off", False)

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
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
            {},
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
        votes: 1

        net {
            algorithm: ffsplit
            host: 127.0.0.1
        }
    }
}""",
                config
            ),
            facade.config.export()
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual([], reporter.report_item_list)

    def test_remove_old_configuration(self):
        config = dedent("""\
            quorum {
                provider: corosync_votequorum
                device {
                    option: value_old1
                    heuristics {
                        h_option: hvalue_old1
                    }
                }
            }
            quorum {
                provider: corosync_votequorum
                device {
                    option: value_old2
                    heuristics {
                        h_option: hvalue_old2
                    }
                }
            }
            """
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
            {},
            {}
        )
        ac(
            dedent("""\
                quorum {
                    provider: corosync_votequorum
                }

                quorum {
                    provider: corosync_votequorum

                    device {
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: 127.0.0.1
                        }
                    }
                }
                """
            )
            ,
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual([], reporter.report_item_list)

    def test_bad_model(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(reporter, "invalid", {}, {}, {}),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "model",
                    "option_value": "invalid",
                    "allowed_values": ["net", ],
                },
                report_codes.FORCE_QDEVICE_MODEL
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_bad_model_forced(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter, "invalid", {}, {}, {}, force_model=True
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: invalid
    }"""
            ),
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        assert_report_item_list_equal(
            reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "model",
                        "option_value": "invalid",
                        "allowed_values": ["net", ],
                    },
                )
            ]
        )

    def test_missing_required_options_net(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(reporter, "net", {}, {}, {}),
            fixture.error(
                report_codes.REQUIRED_OPTION_IS_MISSING,
                option_names=["algorithm"],
            ),
            fixture.error(
                report_codes.REQUIRED_OPTION_IS_MISSING,
                option_names=["host"],
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_bad_options_net(self):
        config = open(rc("corosync-3nodes.conf")).read()
        node_ids = ["1", "2", "3"] # it's in the config
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
                },
                {
                    "mode": "bad mode",
                    "timeout": "-5",
                    "sync_timeout": "-15",
                    "interval": "-30",
                    "exec_ping": "",
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                }
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                option_name="host",
                option_value="",
                allowed_values="a qdevice host address"
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "algorithm",
                    "option_value": "bad algorithm",
                    "allowed_values": ("ffsplit", "lms"),
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["bad_model_option"],
                    "option_type": "quorum device model",
                    "allowed": [
                        "algorithm",
                        "connect_timeout",
                        "force_ip_version",
                        "host",
                        "port",
                        "tie_breaker",
                    ],
                    "allowed_patterns": [],
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "connect_timeout",
                    "option_value": "-1",
                    "allowed_values": "1000..120000",
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "force_ip_version",
                    "option_value": "3",
                    "allowed_values": ("0", "4", "6"),
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "port",
                    "option_value": "65537",
                    "allowed_values": "a port number (1-65535)",
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "tie_breaker",
                    "option_value": "125",
                    "allowed_values": ["lowest", "highest"] + node_ids,
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["bad_generic_option"],
                    "option_type": "quorum device",
                    "allowed": ["sync_timeout", "timeout"],
                    "allowed_patterns": [],
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["model"],
                    "option_type": "quorum device",
                    "allowed": ["sync_timeout", "timeout"],
                    "allowed_patterns": [],
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "sync_timeout",
                    "option_value": "-3",
                    "allowed_values": "a positive integer",
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "timeout",
                    "option_value": "-2",
                    "allowed_values": "a positive integer",
                },
                report_codes.FORCE_OPTIONS
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                force_code=report_codes.FORCE_OPTIONS,
                option_name="mode",
                option_value="bad mode",
                allowed_values=("off", "on", "sync")
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                force_code=report_codes.FORCE_OPTIONS,
                option_name="interval",
                option_value="-30",
                allowed_values="a positive integer"
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                force_code=report_codes.FORCE_OPTIONS,
                option_name="sync_timeout",
                option_value="-15",
                allowed_values="a positive integer"
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                force_code=report_codes.FORCE_OPTIONS,
                option_name="timeout",
                option_value="-5",
                allowed_values="a positive integer"
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                option_name="exec_ping",
                option_value="",
                allowed_values="a command to be run"
            ),
            fixture.error(
                report_codes.INVALID_USERDEFINED_OPTIONS,
                option_names=[
                    "exec_ls bad", "exec_ls#bad", "exec_ls.bad", "exec_ls:bad",
                    "exec_ls{bad", "exec_ls}bad",
                ],
                option_type="heuristics",
                allowed_description=(
                    "exec_NAME cannot contain '.:{}#' and whitespace characters"
                )
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_mandatory_options_missing_net_forced(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(
                reporter, "net", {}, {}, {},
                force_model=True, force_options=True
            ),
            fixture.error(
                report_codes.REQUIRED_OPTION_IS_MISSING,
                option_names=["algorithm"],
            ),
            fixture.error(
                report_codes.REQUIRED_OPTION_IS_MISSING,
                option_names=["host"],
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_mandatory_options_empty_net_forced(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(
                reporter, "net", {"host": "", "algorithm": ""}, {}, {},
                force_model=True, force_options=True
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                option_name="host",
                option_value="",
                allowed_values="a qdevice host address"
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                option_name="algorithm",
                option_value="",
                allowed_values=("ffsplit", "lms")
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_cannot_force_bad_heuristics_exec_name(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(
                reporter,
                "net",
                {
                    "host": "qnetd-host",
                    "algorithm": "ffsplit",
                },
                {},
                {
                    "mode": "on",
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                },
                force_options=True
            ),
            fixture.error(
                report_codes.INVALID_USERDEFINED_OPTIONS,
                option_names=[
                    "exec_ls bad", "exec_ls#bad", "exec_ls.bad", "exec_ls:bad",
                    "exec_ls{bad", "exec_ls}bad",
                ],
                option_type="heuristics",
                allowed_description=(
                    "exec_NAME cannot contain '.:{}#' and whitespace characters"
                )
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_bad_options_net_forced(self):
        config = open(rc("corosync-3nodes.conf")).read()
        node_ids = ["1", "2", "3"] # it's in the config
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            reporter,
            "net",
            {
                "host": "127.0.0.1",
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
            },
            {
                "mode": "bad mode",
                "timeout": "-5",
                "sync_timeout": "-15",
                "interval": "-30",
                "exec_ping": 'ping -q -c 1 "127.0.0.1"',
            },
            force_options=True
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(
            config.replace(
                "    provider: corosync_votequorum\n",
                outdent("""\
                    provider: corosync_votequorum

                    device {
                        bad_generic_option: bad generic value
                        sync_timeout: -3
                        timeout: -2
                        model: net

                        net {
                            algorithm: bad algorithm
                            bad_model_option: bad model value
                            connect_timeout: -1
                            force_ip_version: 3
                            host: 127.0.0.1
                            port: 65537
                            tie_breaker: 125
                        }

                        heuristics {
                            exec_ping: ping -q -c 1 "127.0.0.1"
                            interval: -30
                            mode: bad mode
                            sync_timeout: -15
                            timeout: -5
                        }
                    }
                """)
            ),
            facade.config.export()
        )
        assert_report_item_list_equal(
            reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + node_ids,
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    }
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
            ]
        )

    def test_bad_options_net_disallowed_algorithms(self):
        config = open(rc("corosync-3nodes.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.add_quorum_device(
                reporter,
                "net",
                {"host": "127.0.0.1", "algorithm": "test"},
                {},
                {}
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "algorithm",
                    "option_value": "test",
                    "allowed_values": ("ffsplit", "lms"),
                },
                report_codes.FORCE_OPTIONS
            )
        )

        reporter = MockLibraryReportProcessor()
        assert_raise_library_error(
            lambda: facade.add_quorum_device(
                reporter,
                "net",
                {"host": "127.0.0.1", "algorithm": "2nodelms"},
                {},
                {}
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "algorithm",
                    "option_value": "2nodelms",
                    "allowed_values": ("ffsplit", "lms"),
                },
                report_codes.FORCE_OPTIONS
            )
        )


class UpdateQuorumDeviceTest(TestCase):
    def fixture_add_device(self, config, votes=None):
        with_device = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent("""\
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
                }"""
            ),
            config
        )
        if votes:
            with_device = with_device.replace(
                "model: net",
                "model: net\n        votes: {0}".format(votes)
            )
        return with_device

    def fixture_add_device_with_heuristics(self, config, votes=None):
        with_device = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent("""\
                quorum {
                    provider: corosync_votequorum

                    device {
                        timeout: 12345
                        model: net

                        net {
                            host: 127.0.0.1
                            port: 4433
                        }

                        heuristics {
                            exec_ls: test -f /tmp/test
                            interval: 30
                            mode: on
                        }
                    }
                }"""
            ),
            config
        )
        if votes:
            with_device = with_device.replace(
                "model: net",
                "model: net\n        votes: {0}".format(votes)
            )
        return with_device

    def heuristic_no_exec_warning(
        self, config, heuristics_options, expected_heuristics, warn
    ):
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(reporter, {}, {}, heuristics_options)

        expected_config = re.sub(
            re.compile(r"\s*heuristics {[^}]*}", re.MULTILINE | re.DOTALL),
            "",
            config
        )
        expected_config = expected_config.replace(
            "            port: 4433\n        }\n",
            outdent("""\
                        port: 4433
                    }

            *heuristics*
            """)
            .replace("*heuristics*\n", expected_heuristics)
        )

        ac(expected_config, facade.config.export())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        expected_reports = []
        if warn:
            expected_reports.append(
                fixture.warn(
                    report_codes.COROSYNC_QUORUM_HEURISTICS_ENABLED_WITH_NO_EXEC
                )
            )
        assert_report_item_list_equal(
            reporter.report_item_list,
            expected_reports
        )

    def test_not_existing(self):
        config = open(rc("corosync.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                reporter,
                {"host": "127.0.0.1"},
                {},
                {}
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_not_existing_add_heuristics(self):
        config = open(rc("corosync.conf")).read()
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                reporter,
                {},
                {},
                {"mode": "on"}
            ),
            fixture.error(report_codes.QDEVICE_NOT_DEFINED)
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_success_model_options_net(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read(),
            votes="1"
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {"host": "127.0.0.2", "port": "", "algorithm": "ffsplit"},
            {},
            {}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "host: 127.0.0.1\n            port: 4433",
                "host: 127.0.0.2\n            algorithm: ffsplit"
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_success_net_doesnt_require_host_and_algorithm(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(reporter, {"port": "4444"}, {}, {})
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "host: 127.0.0.1\n            port: 4433",
                "host: 127.0.0.1\n            port: 4444"
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_net_required_options_cannot_be_removed(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                reporter,
                {"host": "", "algorithm": ""},
                {},
                {}
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                option_name="host",
                option_value="",
                allowed_values="a qdevice host address"
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                option_name="algorithm",
                option_value="",
                allowed_values=("ffsplit", "lms")
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_net_required_options_cannot_be_removed_forced(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                reporter,
                {"host": "", "algorithm": ""},
                {},
                {},
                force_options=True
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                option_name="host",
                option_value="",
                allowed_values="a qdevice host address"
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                option_name="algorithm",
                option_value="",
                allowed_values=("ffsplit", "lms")
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_bad_net_options(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        node_ids = ["1", "2", "3"] # it's in the config
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
                {},
                {}
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "algorithm",
                    "option_value": "bad algorithm",
                    "allowed_values": ("ffsplit", "lms"),
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["bad_model_option"],
                    "option_type": "quorum device model",
                    "allowed": [
                        "algorithm",
                        "connect_timeout",
                        "force_ip_version",
                        "host",
                        "port",
                        "tie_breaker",
                    ],
                    "allowed_patterns": [],
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "connect_timeout",
                    "option_value": "-1",
                    "allowed_values": "1000..120000",
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "force_ip_version",
                    "option_value": "3",
                    "allowed_values": ("0", "4", "6"),
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "port",
                    "option_value": "65537",
                    "allowed_values": "a port number (1-65535)",
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "tie_breaker",
                    "option_value": "125",
                    "allowed_values": ["lowest", "highest"] + node_ids,
                },
                report_codes.FORCE_OPTIONS
            ),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_bad_net_options_forced(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        node_ids = ["1", "2", "3"] # it's in the config
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {
                "port": "65537",
                "algorithm": "bad algorithm",
                "connect_timeout": "-1",
                "force_ip_version": "3",
                "tie_breaker": "125",
                "bad_model_option": "bad model value",
            },
            {},
            {},
            force_options=True
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "            host: 127.0.0.1\n            port: 4433",
                """\
            host: 127.0.0.1
            port: 65537
            algorithm: bad algorithm
            bad_model_option: bad model value
            connect_timeout: -1
            force_ip_version: 3
            tie_breaker: 125"""
            ),
            facade.config.export()
        )
        assert_report_item_list_equal(
            reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + node_ids,
                    },
                ),
            ]
        )

    def test_success_generic_options(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {},
            {"timeout": "", "sync_timeout": "23456"},
            {}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "timeout: 12345\n        model: net",
                "model: net\n        sync_timeout: 23456",
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_success_all_options(self):
        config = self.fixture_add_device_with_heuristics(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {"port": "4444"},
            {"timeout": "23456"},
            {"interval": "35"}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config
                .replace("port: 4433", "port: 4444")
                .replace("timeout: 12345", "timeout: 23456")
                .replace("interval: 30", "interval: 35")
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
                },
                {}
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["bad_generic_option"],
                    "option_type": "quorum device",
                    "allowed": ["sync_timeout", "timeout"],
                    "allowed_patterns": [],
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["model"],
                    "option_type": "quorum device",
                    "allowed": ["sync_timeout", "timeout"],
                    "allowed_patterns": [],
                }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "sync_timeout",
                    "option_value": "-3",
                    "allowed_values": "a positive integer",
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "timeout",
                    "option_value": "-2",
                    "allowed_values": "a positive integer",
                },
                report_codes.FORCE_OPTIONS
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_bad_generic_options_cannot_force_model(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                reporter,
                {},
                {"model": "some model", },
                {},
                force_options=True
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["model"],
                    "option_type": "quorum device",
                    "allowed": ["sync_timeout", "timeout"],
                    "allowed_patterns": [],
                }
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_bad_generic_options_forced(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {},
            {
                "timeout": "-2",
                "sync_timeout": "-3",
                "bad_generic_option": "bad generic value",
            },
            {},
            force_options=True
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "        timeout: 12345\n        model: net",
                """\
        timeout: -2
        model: net
        bad_generic_option: bad generic value
        sync_timeout: -3"""
            ),
            facade.config.export()
        )
        assert_report_item_list_equal(
            reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    },
                )
            ]
        )

    def test_success_add_heuristics(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {},
            {},
            {"mode": "on", "exec_ls": "test -f /tmp/test", "interval": "30"}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            self.fixture_add_device_with_heuristics(
                open(rc("corosync-3nodes.conf")).read()
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_success_heuristics_add_on_no_exec(self):
        self.heuristic_no_exec_warning(
            self.fixture_add_device(open(rc("corosync.conf")).read()),
            {"mode": "on"},
            outdent("""\
                    heuristics {
                        mode: on
                    }
            """),
            True
        )

    def test_success_heuristics_add_sync_no_exec(self):
        self.heuristic_no_exec_warning(
            self.fixture_add_device(open(rc("corosync.conf")).read()),
            {"mode": "sync"},
            outdent("""\
                    heuristics {
                        mode: sync
                    }
            """),
            True
        )

    def test_success_heuristics_add_off_no_exec(self):
        self.heuristic_no_exec_warning(
            self.fixture_add_device(open(rc("corosync.conf")).read()),
            {"mode": "off"},
            outdent("""\
                    heuristics {
                        mode: off
                    }
            """),
            False
        )

    def test_success_heuristics_update_on_no_exec(self):
        self.heuristic_no_exec_warning(
            self.fixture_add_device_with_heuristics(
                open(rc("corosync.conf")).read()
            ),
            {"mode": "on", "exec_ls": ""},
            outdent("""\
                    heuristics {
                        interval: 30
                        mode: on
                    }
            """),
            True
        )

    def test_success_heuristics_update_sync_no_exec(self):
        self.heuristic_no_exec_warning(
            self.fixture_add_device_with_heuristics(
                open(rc("corosync.conf")).read()
            ),
            {"mode": "sync", "exec_ls": ""},
            outdent("""\
                    heuristics {
                        interval: 30
                        mode: sync
                    }
            """),
            True
        )

    def test_success_heuristics_update_off_no_exec(self):
        self.heuristic_no_exec_warning(
            self.fixture_add_device_with_heuristics(
                open(rc("corosync.conf")).read()
            ),
            {"mode": "off", "exec_ls": ""},
            outdent("""\
                    heuristics {
                        interval: 30
                        mode: off
                    }
            """),
            False
        )

    def test_success_heuristics_update_exec_present(self):
        self.heuristic_no_exec_warning(
            self.fixture_add_device_with_heuristics(
                open(rc("corosync.conf")).read()
            ),
            {"exec_ls": "", "exec_ping": "ping example.com"},
            outdent("""\
                    heuristics {
                        interval: 30
                        mode: on
                        exec_ping: ping example.com
                    }
            """),
            False
        )

    def test_success_heuristics_update_exec_kept(self):
        self.heuristic_no_exec_warning(
            self.fixture_add_device_with_heuristics(
                open(rc("corosync.conf")).read()
            ),
            {"interval": "25"},
            outdent("""\
                    heuristics {
                        exec_ls: test -f /tmp/test
                        interval: 25
                        mode: on
                    }
            """),
            False
        )

    def test_success_remove_heuristics(self):
        config = self.fixture_add_device_with_heuristics(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {},
            {},
            {"mode": "", "exec_ls": "", "interval": ""}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            self.fixture_add_device(
                open(rc("corosync-3nodes.conf")).read()
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_success_change_heuristics(self):
        config = self.fixture_add_device_with_heuristics(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {},
            {},
            {"mode": "sync", "interval": "", "timeout": "20"}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "interval: 30\n            mode: on",
                "mode: sync\n            timeout: 20",
            ),
            facade.config.export()
        )
        self.assertEqual([], reporter.report_item_list)

    def test_heuristics_bad_options(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                reporter,
                {},
                {},
                {
                    "mode": "bad mode",
                    "timeout": "-5",
                    "sync_timeout": "-15",
                    "interval": "-30",
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                }
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                force_code=report_codes.FORCE_OPTIONS,
                option_name="mode",
                option_value="bad mode",
                allowed_values=("off", "on", "sync")
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                force_code=report_codes.FORCE_OPTIONS,
                option_name="interval",
                option_value="-30",
                allowed_values="a positive integer"
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                force_code=report_codes.FORCE_OPTIONS,
                option_name="sync_timeout",
                option_value="-15",
                allowed_values="a positive integer"
            ),
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                force_code=report_codes.FORCE_OPTIONS,
                option_name="timeout",
                option_value="-5",
                allowed_values="a positive integer"
            ),
            fixture.error(
                report_codes.INVALID_USERDEFINED_OPTIONS,
                option_names=[
                    "exec_ls bad", "exec_ls#bad", "exec_ls.bad", "exec_ls:bad",
                    "exec_ls{bad", "exec_ls}bad",
                ],
                option_type="heuristics",
                allowed_description=(
                    "exec_NAME cannot contain '.:{}#' and whitespace characters"
                )
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_heuristics_bad_options_forced(self):
        config = self.fixture_add_device_with_heuristics(
            open(rc("corosync-3nodes.conf")).read()
        )
        reporter = MockLibraryReportProcessor()
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            reporter,
            {},
            {},
            {
                "interval": "-30",
                "mode": "bad mode",
                "sync_timeout": "-15",
                "timeout": "-5",
            },
            force_options=True
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "interval: 30\n            mode: on",
                (
                    "interval: -30\n            mode: bad mode\n"
                    "            sync_timeout: -15\n"
                    "            timeout: -5"
                ),
            ),
            facade.config.export()
        )
        assert_report_item_list_equal(
            reporter.report_item_list,
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
            ]
        )


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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
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
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(
            config_no_devices,
            facade.config.export()
        )


class RemoveQuorumDeviceHeuristics(TestCase):
    def test_error_on_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            facade.remove_quorum_device_heuristics,
            fixture.error(report_codes.QDEVICE_NOT_DEFINED)
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_error_on_no_device(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            facade.remove_quorum_device_heuristics,
            fixture.error(report_codes.QDEVICE_NOT_DEFINED)
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_noop_on_no_heuristics(self):
        config = open(rc("corosync-3nodes-qdevice.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        facade.remove_quorum_device_heuristics()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_remove_all_heuristics(self):
        config_no_devices = open(rc("corosync-3nodes.conf")).read()
        config_no_heuristics = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent("""\
                quorum {
                    provider: corosync_votequorum

                    device {
                        model: net

                        net {
                            host: 127.0.0.1
                        }
                    }

                    device {
                        option: value
                    }
                }

                quorum {
                    device {
                        model: net

                        net {
                            host: 127.0.0.2
                        }
                    }
                }"""
            ),
            config_no_devices
        )
        config_heuristics = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent("""\
                quorum {
                    provider: corosync_votequorum

                    device {
                        model: net

                        net {
                            host: 127.0.0.1
                        }

                        heuristics {
                            mode: on
                        }
                    }

                    device {
                        option: value

                        heuristics {
                            interval: 3000
                        }
                    }
                }

                quorum {
                    device {
                        model: net

                        net {
                            host: 127.0.0.2
                        }

                        heuristics {
                            exec_ls: test -f /tmp/test
                        }
                    }
                }"""
            ),
            config_no_devices
        )

        facade = lib.ConfigFacade.from_string(config_heuristics)
        facade.remove_quorum_device_heuristics()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(config_no_heuristics, facade.config.export())

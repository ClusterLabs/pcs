import re
from textwrap import dedent
from unittest import TestCase

import pcs.lib.corosync.config_facade as lib
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes
from pcs.lib.corosync.config_parser import Parser

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    ac,
    assert_raise_library_error,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import outdent


def _read_file(name):
    with open(rc(name)) as a_file:
        return a_file.read()


def _get_facade(config_text):
    return lib.ConfigFacade(Parser.parse(config_text.encode("utf-8")))


class HasQuorumDeviceTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = _get_facade(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_device(self):
        config = _read_file("corosync.conf")
        facade = _get_facade(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_device(self):
        config = dedent(
            """\
            quorum {
                device {
                }
            }
        """
        )
        facade = _get_facade(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_device_set(self):
        config = dedent(
            """\
            quorum {
                device {
                    model: net
                }
            }
        """
        )
        facade = _get_facade(config)
        self.assertTrue(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_model(self):
        config = dedent(
            """\
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
        facade = _get_facade(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class GetQuorumDeviceModel(TestCase):
    def assert_model(self, config, expected_model):
        facade = _get_facade(config)
        if expected_model is None:
            self.assertFalse(facade.has_quorum_device())
            with self.assertRaises(AssertionError):
                facade.get_quorum_device_model()
        else:
            self.assertTrue(facade.has_quorum_device())
            self.assertEqual(expected_model, facade.get_quorum_device_model())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_config(self):
        config = ""
        self.assert_model(config, None)

    def test_no_device(self):
        config = _read_file("corosync.conf")
        self.assert_model(config, None)

    def test_empty_device(self):
        config = dedent(
            """\
            quorum {
                device {
                }
            }
        """
        )
        self.assert_model(config, None)

    def test_no_model(self):
        config = dedent(
            """\
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
        self.assert_model(config, None)

    def test_configured_properly(self):
        config = dedent(
            """\
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
        self.assert_model(config, "net")

    def test_more_devices_one_quorum(self):
        config = dedent(
            """\
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
        self.assert_model(config, "net")

    def test_more_devices_more_quorum(self):
        config = dedent(
            """\
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
        self.assert_model(config, "net")


class GetQuorumDeviceSettingsTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = _get_facade(config)
        self.assertFalse(facade.has_quorum_device())
        with self.assertRaises(AssertionError):
            facade.get_quorum_device_model()
        with self.assertRaises(AssertionError):
            facade.get_quorum_device_settings()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_device(self):
        config = _read_file("corosync.conf")
        facade = _get_facade(config)
        self.assertFalse(facade.has_quorum_device())
        with self.assertRaises(AssertionError):
            facade.get_quorum_device_model()
        with self.assertRaises(AssertionError):
            facade.get_quorum_device_settings()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_device(self):
        config = dedent(
            """\
            quorum {
                device {
                }
            }
        """
        )
        facade = _get_facade(config)
        self.assertFalse(facade.has_quorum_device())
        with self.assertRaises(AssertionError):
            facade.get_quorum_device_model()
        with self.assertRaises(AssertionError):
            facade.get_quorum_device_settings()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_model(self):
        config = dedent(
            """\
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
        facade = _get_facade(config)
        self.assertFalse(facade.has_quorum_device())
        with self.assertRaises(AssertionError):
            facade.get_quorum_device_model()
        with self.assertRaises(AssertionError):
            facade.get_quorum_device_settings()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_configured_properly(self):
        config = dedent(
            """\
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
        facade = _get_facade(config)
        self.assertTrue(facade.has_quorum_device())
        self.assertEqual("net", facade.get_quorum_device_model())
        self.assertEqual(
            ({"host": "127.0.0.1"}, {"option": "value"}, {}),
            facade.get_quorum_device_settings(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_configured_properly_heuristics(self):
        config = dedent(
            """\
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
        facade = _get_facade(config)
        self.assertTrue(facade.has_quorum_device())
        self.assertEqual("net", facade.get_quorum_device_model())
        self.assertEqual(
            (
                {"host": "127.0.0.1"},
                {"option": "value"},
                {"exec_ls": "test -f /tmp/test", "mode": "on"},
            ),
            facade.get_quorum_device_settings(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_devices_one_quorum(self):
        config = dedent(
            """\
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
        facade = _get_facade(config)
        self.assertTrue(facade.has_quorum_device())
        self.assertEqual("net", facade.get_quorum_device_model())
        self.assertEqual(
            (
                {"host": "127.0.0.1"},
                {"option0": "valueY", "option1": "value1", "option2": "value2"},
                {"exec_ls": "test -f /tmp/test", "mode": "on", "timeout": "5"},
            ),
            facade.get_quorum_device_settings(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_devices_more_quorum(self):
        config = dedent(
            """\
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
        facade = _get_facade(config)
        self.assertTrue(facade.has_quorum_device())
        self.assertEqual("net", facade.get_quorum_device_model())
        self.assertEqual(
            (
                {"host": "127.0.0.1"},
                {"option0": "valueY", "option1": "value1", "option2": "value2"},
                {"exec_ls": "test -f /tmp/test", "mode": "on", "timeout": "5"},
            ),
            facade.get_quorum_device_settings(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class IsQuorumDeviceHeuristicsEnabledWithNoExec(TestCase):
    def assert_result(self, config, expected_result):
        facade = _get_facade(config)
        self.assertEqual(
            expected_result,
            facade.is_quorum_device_heuristics_enabled_with_no_exec(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_config(self):
        config = ""
        self.assert_result(config, False)

    def test_no_device(self):
        config = _read_file("corosync.conf")
        self.assert_result(config, False)

    def test_empty_heuristics(self):
        config = dedent(
            """\
            quorum {
                device {
                    model: net
                    heuristics {
                    }
                }
            }
        """
        )
        self.assert_result(config, False)

    def test_heuristics_off(self):
        config = dedent(
            """\
            quorum {
                device {
                    model: net
                    heuristics {
                        mode: off
                    }
                }
            }
        """
        )
        self.assert_result(config, False)

    def test_heuristics_on_no_exec(self):
        config = dedent(
            """\
            quorum {
                device {
                    model: net
                    heuristics {
                        mode: on
                    }
                }
            }
        """
        )
        self.assert_result(config, True)

    def test_heuristics_sync_no_exec(self):
        config = dedent(
            """\
            quorum {
                device {
                    model: net
                    heuristics {
                        mode: on
                        exec_ls:
                    }
                }
            }
        """
        )
        self.assert_result(config, True)

    def test_heuristics_on_with_exec(self):
        config = dedent(
            """\
            quorum {
                device {
                    model: net
                    heuristics {
                        mode: on
                        exec_ls: test -f /tmp/test
                    }
                }
            }
        """
        )
        self.assert_result(config, False)

    def test_heuristics_sync_with_exec(self):
        config = dedent(
            """\
            quorum {
                device {
                    model: net
                    heuristics {
                        mode: sync
                        exec_ls: test -f /tmp/test
                    }
                }
            }
        """
        )
        self.assert_result(config, False)

    def test_heuristics_unknown_no_exec(self):
        config = dedent(
            """\
            quorum {
                device {
                    model: net
                    heuristics {
                        mode: unknown
                    }
                }
            }
        """
        )
        self.assert_result(config, False)

    def test_heuristics_unknown_with_exec(self):
        config = dedent(
            """\
            quorum {
                device {
                    model: net
                    heuristics {
                        mode: unknown
                        exec_ls: test -f /tmp/test
                    }
                }
            }
        """
        )
        self.assert_result(config, False)


class AddQuorumDeviceTest(TestCase):
    def test_success_net_minimal_ffsplit(self):
        config = _read_file("corosync-3nodes.conf")
        facade = _get_facade(config)
        facade.add_quorum_device(
            "net", {"host": "127.0.0.1", "algorithm": "ffsplit"}, {}, {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum\n",
                outdent(
                    """\
                    provider: corosync_votequorum

                    device {
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: 127.0.0.1
                        }
                    }
                """
                ),
            ),
            facade.config.export(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_success_net_minimal_lms(self):
        config = _read_file("corosync-3nodes.conf")
        facade = _get_facade(config)
        facade.add_quorum_device(
            "net", {"host": "127.0.0.1", "algorithm": "lms"}, {}, {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum\n",
                outdent(
                    """\
                    provider: corosync_votequorum

                    device {
                        model: net

                        net {
                            algorithm: lms
                            host: 127.0.0.1
                        }
                    }
                """
                ),
            ),
            facade.config.export(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_success_remove_nodes_votes(self):
        config = _read_file("corosync-3nodes.conf")
        config_votes = config.replace("node {", "node {\nquorum_votes: 2")
        facade = _get_facade(config_votes)
        facade.add_quorum_device(
            "net", {"host": "127.0.0.1", "algorithm": "lms"}, {}, {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum\n",
                outdent(
                    """\
                    provider: corosync_votequorum

                    device {
                        model: net

                        net {
                            algorithm: lms
                            host: 127.0.0.1
                        }
                    }
                """
                ),
            ),
            facade.config.export(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_success_net_full(self):
        config = _read_file("corosync-3nodes.conf")
        facade = _get_facade(config)
        facade.add_quorum_device(
            "net",
            {
                "host": "127.0.0.1",
                "port": "4433",
                "algorithm": "ffsplit",
                "connect_timeout": "12345",
                "force_ip_version": "4",
                "tie_breaker": "lowest",
            },
            {"timeout": "23456", "sync_timeout": "34567"},
            {
                "mode": "on",
                "timeout": "5",
                "sync_timeout": "15",
                "interval": "30",
                "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                "exec_ls": "test -f /tmp/test",
            },
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum\n",
                outdent(
                    """\
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
                """
                ),
            ),
            facade.config.export(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_remove_conflicting_options(self):
        config = _read_file("corosync.conf")
        config = config.replace(
            "    two_node: 1\n",
            "\n".join(
                [
                    "    two_node: 1",
                    "    auto_tie_breaker: 1",
                    "    last_man_standing: 1",
                    "    last_man_standing_window: 987",
                    "    allow_downscale: 1",
                    "",
                ]
            ),
        )
        facade = _get_facade(config)
        facade.add_quorum_device(
            "net", {"host": "127.0.0.1", "algorithm": "ffsplit"}, {}, {}
        )
        ac(
            re.sub(
                re.compile(r"quorum {[^}]*}\n", re.MULTILINE | re.DOTALL),
                dedent(
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
                    }
                """
                ),
                config,
            ),
            facade.config.export(),
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_remove_old_configuration(self):
        config = dedent(
            """\
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
        facade = _get_facade(config)
        facade.add_quorum_device(
            "net", {"host": "127.0.0.1", "algorithm": "ffsplit"}, {}, {}
        )
        ac(
            dedent(
                """\
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
            ),
            facade.config.export(),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class UpdateQuorumDeviceTest(TestCase):
    @staticmethod
    def fixture_add_device(config, votes=None):
        with_device = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent(
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
                }"""
            ),
            config,
        )
        if votes:
            with_device = with_device.replace(
                "model: net", "model: net\n        votes: {0}".format(votes)
            )
        return with_device

    @staticmethod
    def fixture_add_device_with_heuristics(config, votes=None):
        with_device = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent(
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

                        heuristics {
                            exec_ls: test -f /tmp/test
                            interval: 30
                            mode: on
                        }
                    }
                }"""
            ),
            config,
        )
        if votes:
            with_device = with_device.replace(
                "model: net", "model: net\n        votes: {0}".format(votes)
            )
        return with_device

    def test_not_existing(self):
        config = _read_file("corosync.conf")
        facade = _get_facade(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device({"host": "127.0.0.1"}, {}, {}),
            (severity.ERROR, report_codes.QDEVICE_NOT_DEFINED, {}),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_not_existing_add_heuristics(self):
        config = _read_file("corosync.conf")
        facade = _get_facade(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device({}, {}, {"mode": "on"}),
            fixture.error(report_codes.QDEVICE_NOT_DEFINED),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_success_model_options_net(self):
        config = self.fixture_add_device(
            _read_file("corosync-3nodes.conf"), votes="1"
        )
        facade = _get_facade(config)
        facade.update_quorum_device(
            {"host": "127.0.0.2", "port": "", "algorithm": "ffsplit"}, {}, {}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "host: 127.0.0.1\n            port: 4433",
                "host: 127.0.0.2\n            algorithm: ffsplit",
            ),
            facade.config.export(),
        )

    def test_success_generic_options(self):
        config = self.fixture_add_device(_read_file("corosync-3nodes.conf"))
        facade = _get_facade(config)
        facade.update_quorum_device(
            {}, {"timeout": "", "sync_timeout": "23456"}, {}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "timeout: 12345\n        model: net",
                "model: net\n        sync_timeout: 23456",
            ),
            facade.config.export(),
        )

    def test_success_all_options(self):
        config = self.fixture_add_device_with_heuristics(
            _read_file("corosync-3nodes.conf")
        )
        facade = _get_facade(config)
        facade.update_quorum_device(
            {"port": "4444"}, {"timeout": "23456"}, {"interval": "35"}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace("port: 4433", "port: 4444")
            .replace("timeout: 12345", "timeout: 23456")
            .replace("interval: 30", "interval: 35"),
            facade.config.export(),
        )

    def test_success_add_heuristics(self):
        config = self.fixture_add_device(_read_file("corosync-3nodes.conf"))
        facade = _get_facade(config)
        facade.update_quorum_device(
            {},
            {},
            {"mode": "on", "exec_ls": "test -f /tmp/test", "interval": "30"},
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            self.fixture_add_device_with_heuristics(
                _read_file("corosync-3nodes.conf")
            ),
            facade.config.export(),
        )

    def test_success_remove_heuristics(self):
        config = self.fixture_add_device_with_heuristics(
            _read_file("corosync-3nodes.conf")
        )
        facade = _get_facade(config)
        facade.update_quorum_device(
            {}, {}, {"mode": "", "exec_ls": "", "interval": ""}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            self.fixture_add_device(_read_file("corosync-3nodes.conf")),
            facade.config.export(),
        )

    def test_success_change_heuristics(self):
        config = self.fixture_add_device_with_heuristics(
            _read_file("corosync-3nodes.conf")
        )
        facade = _get_facade(config)
        facade.update_quorum_device(
            {}, {}, {"mode": "sync", "interval": "", "timeout": "20"}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "interval: 30\n            mode: on",
                "mode: sync\n            timeout: 20",
            ),
            facade.config.export(),
        )


class RemoveQuorumDeviceTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = _get_facade(config)
        assert_raise_library_error(
            facade.remove_quorum_device,
            (severity.ERROR, report_codes.QDEVICE_NOT_DEFINED, {}),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_device(self):
        config = _read_file("corosync-3nodes.conf")
        facade = _get_facade(config)
        assert_raise_library_error(
            facade.remove_quorum_device,
            (severity.ERROR, report_codes.QDEVICE_NOT_DEFINED, {}),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_remove_all_devices(self):
        config_no_devices = _read_file("corosync-3nodes.conf")
        config = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent(
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
                }
            """
            ),
            config_no_devices,
        )
        facade = _get_facade(config)
        facade.remove_quorum_device()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config_no_devices, facade.config.export())

    def test_restore_two_node(self):
        config_no_devices = _read_file("corosync.conf")
        config = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent(
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
                }
            """
            ),
            config_no_devices,
        )
        facade = _get_facade(config)
        facade.remove_quorum_device()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config_no_devices, facade.config.export())


class RemoveQuorumDeviceHeuristics(TestCase):
    def test_error_on_empty_config(self):
        config = ""
        facade = _get_facade(config)
        assert_raise_library_error(
            facade.remove_quorum_device_heuristics,
            fixture.error(report_codes.QDEVICE_NOT_DEFINED),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_error_on_no_device(self):
        config = _read_file("corosync-3nodes.conf")
        facade = _get_facade(config)
        assert_raise_library_error(
            facade.remove_quorum_device_heuristics,
            fixture.error(report_codes.QDEVICE_NOT_DEFINED),
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_noop_on_no_heuristics(self):
        config = _read_file("corosync-3nodes-qdevice.conf")
        facade = _get_facade(config)
        facade.remove_quorum_device_heuristics()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_remove_all_heuristics(self):
        config_no_devices = _read_file("corosync-3nodes.conf")
        config_no_heuristics = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent(
                """\
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
            config_no_devices,
        )
        config_heuristics = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent(
                """\
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
            config_no_devices,
        )

        facade = _get_facade(config_heuristics)
        facade.remove_quorum_device_heuristics()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(config_no_heuristics, facade.config.export())

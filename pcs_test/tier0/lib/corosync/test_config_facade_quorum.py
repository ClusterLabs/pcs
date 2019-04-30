from textwrap import dedent
from unittest import TestCase

from pcs_test.tools.misc import get_test_resource as rc

import pcs.lib.corosync.config_facade as lib

class GetQuorumOptionsTest(TestCase):
    def test_no_quorum(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_quorum(self):
        config = dedent("""\
            quorum {
            }
        """)
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_options(self):
        config = dedent("""\
            quorum {
                provider: corosync_votequorum
            }
        """)
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_some_options(self):
        config = dedent("""\
            quorum {
                provider: corosync_votequorum
                wait_for_all: 0
                nonsense: ignored
                auto_tie_breaker: 1
                last_man_standing: 0
                last_man_standing_window: 1000
            }
        """)
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
        config = dedent("""\
            quorum {
                wait_for_all: 0
                wait_for_all: 1
            }
        """)
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
        config = dedent("""\
            quorum {
                wait_for_all: 0
                last_man_standing: 0
            }
            quorum {
                last_man_standing_window: 1000
                wait_for_all: 1
            }
        """)
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
        config = dedent("""\
            quorum {
                auto_tie_breaker: 1
            }
        """)
        facade = lib.ConfigFacade.from_string(config)
        self.assertTrue(facade.is_enabled_auto_tie_breaker())

    def test_disabled(self):
        config = dedent("""\
            quorum {
                auto_tie_breaker: 0
            }
        """)
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.is_enabled_auto_tie_breaker())

    def test_no_value(self):
        config = dedent("""\
            quorum {
            }
        """)
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.is_enabled_auto_tie_breaker())


class SetQuorumOptionsTest(TestCase):
    @staticmethod
    def get_two_node(facade):
        two_node = None
        for quorum in facade.config.get_sections("quorum"):
            for dummy_name, value in quorum.get_attributes("two_node"):
                two_node = value
        return two_node

    def test_add_missing_section(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        facade.set_quorum_options({"wait_for_all": "0"})
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent("""\
                quorum {
                    wait_for_all: 0
                }
            """),
            facade.config.export()
        )

    def test_del_missing_section(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        facade.set_quorum_options({"wait_for_all": ""})
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual("", facade.config.export())

    def test_add_all_options(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        expected_options = {
            "auto_tie_breaker": "1",
            "last_man_standing": "0",
            "last_man_standing_window": "1000",
            "wait_for_all": "0",
        }
        facade.set_quorum_options(expected_options)

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        test_facade = lib.ConfigFacade.from_string(facade.config.export())
        self.assertEqual(
            expected_options,
            test_facade.get_quorum_options()
        )

    def test_complex(self):
        config = dedent("""\
            quorum {
                wait_for_all: 0
                last_man_standing_window: 1000
            }
            quorum {
                wait_for_all: 0
                last_man_standing: 1
            }
        """)
        facade = lib.ConfigFacade.from_string(config)
        facade.set_quorum_options(
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

    def test_2nodes_atb_on(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(2, len(facade.get_nodes()))

        facade.set_quorum_options({"auto_tie_breaker": "1"})

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            "1",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node is None or two_node == "0")

    def test_2nodes_atb_off(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(2, len(facade.get_nodes()))

        facade.set_quorum_options({"auto_tie_breaker": "0"})

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            "0",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node == "1")

    def test_3nodes_atb_on(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(3, len(facade.get_nodes()))

        facade.set_quorum_options({"auto_tie_breaker": "1"})

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            "1",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node is None or two_node == "0")

    def test_3nodes_atb_off(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(3, len(facade.get_nodes()))

        facade.set_quorum_options({"auto_tie_breaker": "0"})

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            "0",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node is None or two_node == "0")

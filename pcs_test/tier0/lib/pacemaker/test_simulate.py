from unittest import TestCase

from lxml import etree

from pcs.lib.pacemaker import simulate

from pcs_test.tools.misc import get_test_resource as rc


class GetOperationsFromTransitions(TestCase):
    def test_transitions1(self):
        transitions = etree.parse(rc("transitions01.xml"))
        self.assertEqual(
            [
                {
                    "primitive_id": "dummy",
                    "primitive_long_id": "dummy",
                    "operation": "stop",
                    "on_node": "rh7-3",
                },
                {
                    "primitive_id": "dummy",
                    "primitive_long_id": "dummy",
                    "operation": "start",
                    "on_node": "rh7-2",
                },
                {
                    "primitive_id": "d0",
                    "primitive_long_id": "d0:1",
                    "operation": "stop",
                    "on_node": "rh7-1",
                },
                {
                    "primitive_id": "d0",
                    "primitive_long_id": "d0:1",
                    "operation": "start",
                    "on_node": "rh7-2",
                },
                {
                    "primitive_id": "state",
                    "primitive_long_id": "state:0",
                    "operation": "stop",
                    "on_node": "rh7-3",
                },
                {
                    "primitive_id": "state",
                    "primitive_long_id": "state:0",
                    "operation": "start",
                    "on_node": "rh7-2",
                },
            ],
            simulate.get_operations_from_transitions(transitions),
        )

    def test_transitions2(self):
        transitions = etree.parse(rc("transitions02.xml"))
        self.assertEqual(
            [
                {
                    "primitive_id": "RemoteNode",
                    "primitive_long_id": "RemoteNode",
                    "operation": "stop",
                    "on_node": "virt-143",
                },
                {
                    "primitive_id": "RemoteNode",
                    "primitive_long_id": "RemoteNode",
                    "operation": "migrate_to",
                    "on_node": "virt-143",
                },
                {
                    "primitive_id": "RemoteNode",
                    "primitive_long_id": "RemoteNode",
                    "operation": "migrate_from",
                    "on_node": "virt-142",
                },
                {
                    "primitive_id": "dummy8",
                    "primitive_long_id": "dummy8",
                    "operation": "stop",
                    "on_node": "virt-143",
                },
                {
                    "primitive_id": "dummy8",
                    "primitive_long_id": "dummy8",
                    "operation": "start",
                    "on_node": "virt-142",
                },
            ],
            simulate.get_operations_from_transitions(transitions),
        )


class GetResourcesFromOperations(TestCase):
    operations = [
        {
            "primitive_id": "dummy2",
            "primitive_long_id": "dummy2:1",
            "operation": "stop",
            "on_node": "node1",
        },
        {
            "primitive_id": "dummy1",
            "primitive_long_id": "dummy1",
            "operation": "stop",
            "on_node": "node3",
        },
        {
            "primitive_id": "dummy1",
            "primitive_long_id": "dummy1",
            "operation": "start",
            "on_node": "node2",
        },
    ]

    def test_no_operations(self):
        self.assertEqual([], simulate.get_resources_from_operations([]))

    def test_no_operations_exclude(self):
        self.assertEqual(
            [], simulate.get_resources_from_operations([], exclude={"dummy1"})
        )

    def test_some_operations(self):
        self.assertEqual(
            ["dummy1", "dummy2"],
            simulate.get_resources_from_operations(self.operations),
        )

    def test_some_operations_exclude(self):
        self.assertEqual(
            ["dummy2"],
            simulate.get_resources_from_operations(
                self.operations, exclude={"dummy1", "dummy2:1", "dummyX"}
            ),
        )


class GetResourcesLeftStoppedDemotedMixin:
    def test_no_operations(self):
        self.assertEqual([], self.call([]))

    def test_down(self):
        self.assertEqual(
            ["dummy"],
            self.call(
                [
                    {
                        "primitive_id": "dummy",
                        "primitive_long_id": "dummy",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                ]
            ),
        )

    def test_up(self):
        self.assertEqual(
            [],
            self.call(
                [
                    {
                        "primitive_id": "dummy",
                        "primitive_long_id": "dummy",
                        "operation": self.action_up,
                        "on_node": "node3",
                    },
                ]
            ),
        )

    def test_down_up(self):
        self.assertEqual(
            [],
            self.call(
                [
                    {
                        "primitive_id": "dummy",
                        "primitive_long_id": "dummy",
                        "operation": self.action_down,
                        "on_node": "node2",
                    },
                    {
                        "primitive_id": "dummy",
                        "primitive_long_id": "dummy",
                        "operation": self.action_up,
                        "on_node": "node3",
                    },
                ]
            ),
        )

    def test_up_down(self):
        self.assertEqual(
            [],
            self.call(
                [
                    {
                        "primitive_id": "dummy",
                        "primitive_long_id": "dummy",
                        "operation": self.action_up,
                        "on_node": "node2",
                    },
                    {
                        "primitive_id": "dummy",
                        "primitive_long_id": "dummy",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                ]
            ),
        )

    def test_mixed(self):
        self.assertEqual(
            ["dummy1", "dummy2"],
            self.call(
                [
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                    {
                        "primitive_id": "dummy2",
                        "primitive_long_id": "dummy2",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                    {
                        "primitive_id": "dummy3",
                        "primitive_long_id": "dummy3",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                    {
                        "primitive_id": "dummy3",
                        "primitive_long_id": "dummy3",
                        "operation": self.action_up,
                        "on_node": "node2",
                    },
                ]
            ),
        )

    def test_exclude(self):
        self.assertEqual(
            ["dummy2"],
            self.call(
                [
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                    {
                        "primitive_id": "dummy2",
                        "primitive_long_id": "dummy2",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                ],
                exclude={"dummy1", "dummyX"},
            ),
        )


class GetResourcesLeftStopped(GetResourcesLeftStoppedDemotedMixin, TestCase):
    action_up = "start"
    action_down = "stop"
    call = staticmethod(simulate.get_resources_left_stopped)

    def test_clone_move(self):
        self.assertEqual(
            [],
            self.call(
                [
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:0",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:1",
                        "operation": self.action_down,
                        "on_node": "node1",
                    },
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:0",
                        "operation": self.action_up,
                        "on_node": "node2",
                    },
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:1",
                        "operation": self.action_up,
                        "on_node": "node4",
                    },
                ]
            ),
        )

    def test_clone_stop(self):
        self.assertEqual(
            ["dummy1"],
            self.call(
                [
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:0",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:1",
                        "operation": self.action_down,
                        "on_node": "node1",
                    },
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:1",
                        "operation": self.action_up,
                        "on_node": "node4",
                    },
                ]
            ),
        )


class GetResourcesLeftDemoted(GetResourcesLeftStoppedDemotedMixin, TestCase):
    action_up = "promote"
    action_down = "demote"
    call = staticmethod(simulate.get_resources_left_demoted)

    def test_main_move(self):
        self.assertEqual(
            [],
            self.call(
                [
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:0",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:1",
                        "operation": self.action_up,
                        "on_node": "node4",
                    },
                ]
            ),
        )

    def test_main_stop(self):
        self.assertEqual(
            ["dummy1"],
            self.call(
                [
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:0",
                        "operation": self.action_down,
                        "on_node": "node3",
                    },
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:1",
                        "operation": self.action_up,
                        "on_node": "node4",
                    },
                    {
                        "primitive_id": "dummy1",
                        "primitive_long_id": "dummy1:2",
                        "operation": self.action_down,
                        "on_node": "node1",
                    },
                ]
            ),
        )

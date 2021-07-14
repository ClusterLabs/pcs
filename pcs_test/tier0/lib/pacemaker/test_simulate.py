from unittest import TestCase

from lxml import etree

from pcs.lib.pacemaker import simulate

from pcs_test.tools.misc import get_test_resource as rc


class GetOperationsFromTransitions(TestCase):
    def test_transitions1(self):
        transitions = etree.parse(rc("transitions01.xml"))
        self.assertEqual(
            [
                simulate.SimulationOperation(
                    operation_id=17,
                    primitive_id="dummy",
                    primitive_long_id="dummy",
                    operation_type=simulate.OPERATION_STOP,
                    on_node="rh7-3",
                ),
                simulate.SimulationOperation(
                    operation_id=18,
                    primitive_id="dummy",
                    primitive_long_id="dummy",
                    operation_type=simulate.OPERATION_START,
                    on_node="rh7-2",
                ),
                simulate.SimulationOperation(
                    operation_id=22,
                    primitive_id="d0",
                    primitive_long_id="d0:1",
                    operation_type=simulate.OPERATION_STOP,
                    on_node="rh7-1",
                ),
                simulate.SimulationOperation(
                    operation_id=23,
                    primitive_id="d0",
                    primitive_long_id="d0:1",
                    operation_type=simulate.OPERATION_START,
                    on_node="rh7-2",
                ),
                simulate.SimulationOperation(
                    operation_id=29,
                    primitive_id="state",
                    primitive_long_id="state:0",
                    operation_type=simulate.OPERATION_STOP,
                    on_node="rh7-3",
                ),
                simulate.SimulationOperation(
                    operation_id=30,
                    primitive_id="state",
                    primitive_long_id="state:0",
                    operation_type=simulate.OPERATION_START,
                    on_node="rh7-2",
                ),
            ],
            simulate.get_operations_from_transitions(transitions),
        )

    def test_transitions2(self):
        transitions = etree.parse(rc("transitions02.xml"))
        self.assertEqual(
            [
                simulate.SimulationOperation(
                    operation_id=26,
                    primitive_id="RemoteNode",
                    primitive_long_id="RemoteNode",
                    operation_type=simulate.OPERATION_STOP,
                    on_node="virt-143",
                ),
                simulate.SimulationOperation(
                    operation_id=29,
                    primitive_id="RemoteNode",
                    primitive_long_id="RemoteNode",
                    operation_type=simulate.OPERATION_MIGRATE_TO,
                    on_node="virt-143",
                ),
                simulate.SimulationOperation(
                    operation_id=30,
                    primitive_id="RemoteNode",
                    primitive_long_id="RemoteNode",
                    operation_type=simulate.OPERATION_MIGRATE_FROM,
                    on_node="virt-142",
                ),
                simulate.SimulationOperation(
                    operation_id=45,
                    primitive_id="dummy8",
                    primitive_long_id="dummy8",
                    operation_type=simulate.OPERATION_STOP,
                    on_node="virt-143",
                ),
                simulate.SimulationOperation(
                    operation_id=46,
                    primitive_id="dummy8",
                    primitive_long_id="dummy8",
                    operation_type=simulate.OPERATION_START,
                    on_node="virt-142",
                ),
            ],
            simulate.get_operations_from_transitions(transitions),
        )


class GetResourcesFromOperations(TestCase):
    operations = [
        simulate.SimulationOperation(
            operation_id=0,
            primitive_id="dummy2",
            primitive_long_id="dummy2:1",
            operation_type=simulate.OPERATION_STOP,
            on_node="node1",
        ),
        simulate.SimulationOperation(
            operation_id=1,
            primitive_id="dummy1",
            primitive_long_id="dummy1",
            operation_type=simulate.OPERATION_STOP,
            on_node="node3",
        ),
        simulate.SimulationOperation(
            operation_id=2,
            primitive_id="dummy1",
            primitive_long_id="dummy1",
            operation_type=simulate.OPERATION_START,
            on_node="node2",
        ),
    ]

    def test_no_operations(self):
        self.assertEqual([], simulate.get_resources_from_operations([]))

    def test_no_operations_exclude(self):
        self.assertEqual(
            [],
            simulate.get_resources_from_operations(
                [], exclude_resources={"dummy1"}
            ),
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
                self.operations,
                exclude_resources={"dummy1", "dummy2:1", "dummyX"},
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
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy",
                        primitive_long_id="dummy",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                ]
            ),
        )

    def test_up(self):
        self.assertEqual(
            [],
            self.call(
                [
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy",
                        primitive_long_id="dummy",
                        operation_type=self.action_up,
                        on_node="node3",
                    ),
                ]
            ),
        )

    def test_down_up(self):
        self.assertEqual(
            [],
            self.call(
                [
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy",
                        primitive_long_id="dummy",
                        operation_type=self.action_down,
                        on_node="node2",
                    ),
                    simulate.SimulationOperation(
                        operation_id=1,
                        primitive_id="dummy",
                        primitive_long_id="dummy",
                        operation_type=self.action_up,
                        on_node="node3",
                    ),
                ]
            ),
        )

    def test_up_down(self):
        self.assertEqual(
            [],
            self.call(
                [
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy",
                        primitive_long_id="dummy",
                        operation_type=self.action_up,
                        on_node="node2",
                    ),
                    simulate.SimulationOperation(
                        operation_id=1,
                        primitive_id="dummy",
                        primitive_long_id="dummy",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                ]
            ),
        )

    def test_mixed(self):
        self.assertEqual(
            ["dummy1", "dummy2"],
            self.call(
                [
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                    simulate.SimulationOperation(
                        operation_id=1,
                        primitive_id="dummy2",
                        primitive_long_id="dummy2",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                    simulate.SimulationOperation(
                        operation_id=2,
                        primitive_id="dummy3",
                        primitive_long_id="dummy3",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                    simulate.SimulationOperation(
                        operation_id=3,
                        primitive_id="dummy3",
                        primitive_long_id="dummy3",
                        operation_type=self.action_up,
                        on_node="node2",
                    ),
                ]
            ),
        )

    def test_exclude(self):
        self.assertEqual(
            ["dummy2"],
            self.call(
                [
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                    simulate.SimulationOperation(
                        operation_id=1,
                        primitive_id="dummy2",
                        primitive_long_id="dummy2",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                ],
                exclude_resources={"dummy1", "dummyX"},
            ),
        )


class GetResourcesLeftStopped(GetResourcesLeftStoppedDemotedMixin, TestCase):
    action_up = simulate.OPERATION_START
    action_down = simulate.OPERATION_STOP
    call = staticmethod(simulate.get_resources_left_stopped)

    def test_clone_move(self):
        self.assertEqual(
            [],
            self.call(
                [
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:0",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                    simulate.SimulationOperation(
                        operation_id=1,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:1",
                        operation_type=self.action_down,
                        on_node="node1",
                    ),
                    simulate.SimulationOperation(
                        operation_id=2,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:0",
                        operation_type=self.action_up,
                        on_node="node2",
                    ),
                    simulate.SimulationOperation(
                        operation_id=3,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:1",
                        operation_type=self.action_up,
                        on_node="node4",
                    ),
                ]
            ),
        )

    def test_clone_stop(self):
        self.assertEqual(
            ["dummy1"],
            self.call(
                [
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:0",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                    simulate.SimulationOperation(
                        operation_id=1,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:1",
                        operation_type=self.action_down,
                        on_node="node1",
                    ),
                    simulate.SimulationOperation(
                        operation_id=3,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:1",
                        operation_type=self.action_up,
                        on_node="node4",
                    ),
                ]
            ),
        )


class GetResourcesLeftDemoted(GetResourcesLeftStoppedDemotedMixin, TestCase):
    action_up = simulate.OPERATION_PROMOTE
    action_down = simulate.OPERATION_DEMOTE
    call = staticmethod(simulate.get_resources_left_demoted)

    def test_master_move(self):
        self.assertEqual(
            [],
            self.call(
                [
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:0",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                    simulate.SimulationOperation(
                        operation_id=3,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:1",
                        operation_type=self.action_up,
                        on_node="node4",
                    ),
                ]
            ),
        )

    def test_master_stop(self):
        self.assertEqual(
            ["dummy1"],
            self.call(
                [
                    simulate.SimulationOperation(
                        operation_id=0,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:0",
                        operation_type=self.action_down,
                        on_node="node3",
                    ),
                    simulate.SimulationOperation(
                        operation_id=3,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:1",
                        operation_type=self.action_up,
                        on_node="node4",
                    ),
                    simulate.SimulationOperation(
                        operation_id=1,
                        primitive_id="dummy1",
                        primitive_long_id="dummy1:2",
                        operation_type=self.action_down,
                        on_node="node1",
                    ),
                ]
            ),
        )

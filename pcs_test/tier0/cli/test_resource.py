from random import shuffle
from textwrap import dedent
from unittest import TestCase, mock

from pcs import resource
from pcs.cli.common.errors import CmdLineInputError

from pcs_test.tools.assertions import AssertPcsMixin, ac
from pcs_test.tools.misc import dict_to_modifiers


class FailcountShow(TestCase):
    def setUp(self):
        print_patcher = mock.patch("pcs.resource.print")
        self.print_mock = print_patcher.start()
        self.addCleanup(print_patcher.stop)
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["get_failcounts"])
        self.get_failcounts = mock.Mock()
        self.lib.resource = self.resource
        self.lib.resource.get_failcounts = self.get_failcounts

    def assert_failcount_output(
        self,
        lib_failures,
        expected_output,
        resource_id=None,
        node=None,
        operation=None,
        interval=None,
        full=False,
    ):
        self.get_failcounts.return_value = lib_failures
        argv = []
        if resource_id:
            argv.append(resource_id)
        if node:
            argv.append(f"node={node}")
        if operation:
            argv.append(f"operation={operation}")
        if interval:
            argv.append(f"interval={interval}")

        resource.resource_failcount_show(
            self.lib, argv, dict_to_modifiers(dict(full=full))
        )
        self.print_mock.assert_called_once()
        ac(
            self.print_mock.call_args[0][0],
            expected_output,
        )

    @staticmethod
    def fixture_failures_monitor():
        failures = [
            {
                "node": "node2",
                "resource": "resource",
                "clone_id": None,
                "operation": "monitor",
                "interval": "500",
                "fail_count": 10,
                "last_failure": 1528871946,
            },
            {
                "node": "node2",
                "resource": "resource",
                "clone_id": None,
                "operation": "monitor",
                "interval": "1500",
                "fail_count": 150,
                "last_failure": 1528871956,
            },
            {
                "node": "node1",
                "resource": "resource",
                "clone_id": None,
                "operation": "monitor",
                "interval": "1500",
                "fail_count": 25,
                "last_failure": 1528871966,
            },
        ]
        shuffle(failures)
        return failures

    def fixture_failures(self):
        failures = self.fixture_failures_monitor() + [
            {
                "node": "node1",
                "resource": "clone",
                "clone_id": "0",
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node1",
                "resource": "clone",
                "clone_id": "1",
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node2",
                "resource": "clone",
                "clone_id": "0",
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node2",
                "resource": "clone",
                "clone_id": "1",
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node1",
                "resource": "resource",
                "clone_id": None,
                "operation": "start",
                "interval": "0",
                "fail_count": 100,
                "last_failure": 1528871966,
            },
            {
                "node": "node1",
                "resource": "resource",
                "clone_id": None,
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871966,
            },
        ]
        shuffle(failures)
        return failures

    def test_no_failcounts(self):
        self.assert_failcount_output([], "No failcounts")

    def test_no_failcounts_resource(self):
        self.assert_failcount_output(
            [], "No failcounts for resource 'res'", resource_id="res"
        )

    def test_no_failcounts_node(self):
        self.assert_failcount_output(
            [], "No failcounts on node 'nod'", node="nod"
        )

    def test_no_failcounts_operation(self):
        self.assert_failcount_output(
            [], "No failcounts for operation 'ope'", operation="ope"
        )

    def test_no_failcounts_operation_interval(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' with interval '10'",
            operation="ope",
            interval="10",
        )

    def test_no_failcounts_resource_node(self):
        self.assert_failcount_output(
            [],
            "No failcounts for resource 'res' on node 'nod'",
            resource_id="res",
            node="nod",
        )

    def test_no_failcounts_resource_operation(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' of resource 'res'",
            resource_id="res",
            operation="ope",
        )

    def test_no_failcounts_resource_operation_interval(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' with interval '10' of resource "
            "'res'",
            resource_id="res",
            operation="ope",
            interval="10",
        )

    def test_no_failcounts_resource_node_operation_interval(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' with interval '10' of resource "
            "'res' on node 'nod'",
            resource_id="res",
            node="nod",
            operation="ope",
            interval="10",
        )

    def test_no_failcounts_node_operation(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' on node 'nod'",
            node="nod",
            operation="ope",
        )

    def test_no_failcounts_node_operation_interval(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' with interval '10' on node 'nod'",
            node="nod",
            operation="ope",
            interval="10",
        )

    def test_failcounts_short(self):
        self.assert_failcount_output(
            self.fixture_failures(),
            dedent(
                """\
                Failcounts for resource 'clone'
                  node1: INFINITY
                  node2: INFINITY
                Failcounts for resource 'resource'
                  node1: INFINITY
                  node2: 160"""
            ),
            full=False,
        )

    def test_failcounts_full(self):
        self.assert_failcount_output(
            self.fixture_failures(),
            dedent(
                """\
                Failcounts for resource 'clone'
                  node1:
                    start 0ms: INFINITY
                  node2:
                    start 0ms: INFINITY
                Failcounts for resource 'resource'
                  node1:
                    monitor 1500ms: 25
                    start 0ms: INFINITY
                  node2:
                    monitor 1500ms: 150
                    monitor 500ms: 10"""
            ),
            full=True,
        )

    def test_failcounts_short_filter(self):
        self.assert_failcount_output(
            self.fixture_failures_monitor(),
            dedent(
                """\
                Failcounts for operation 'monitor' of resource 'resource'
                  node1: 25
                  node2: 160"""
            ),
            operation="monitor",
            full=False,
        )

    def test_failcounts_full_filter(self):
        self.assert_failcount_output(
            self.fixture_failures_monitor(),
            dedent(
                """\
                Failcounts for operation 'monitor' of resource 'resource'
                  node1:
                    monitor 1500ms: 25
                  node2:
                    monitor 1500ms: 150
                    monitor 500ms: 10"""
            ),
            operation="monitor",
            full=True,
        )


class GroupAdd(TestCase, AssertPcsMixin):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["group_add", "is_any_stonith"])
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_group_add_cmd(self.lib, [], dict_to_modifiers({}))
        self.assertIsNone(cm.exception.message)
        self.resource.group_add.assert_not_called()

    def test_no_resources(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_group_add_cmd(
                self.lib, ["G"], dict_to_modifiers({})
            )
        self.assertIsNone(cm.exception.message)
        self.resource.group_add.assert_not_called()

    def test_both_after_and_before(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_group_add_cmd(
                self.lib,
                ["G", "R1", "R2"],
                dict_to_modifiers(dict(after="A", before="B")),
            )
        self.assertEqual(
            cm.exception.message, "you cannot specify both --before and --after"
        )
        self.resource.group_add.assert_not_called()

    def test_success(self):
        resource.resource_group_add_cmd(
            self.lib, ["G", "R1", "R2"], dict_to_modifiers({})
        )
        self.resource.group_add.assert_called_once_with(
            "G",
            ["R1", "R2"],
            adjacent_resource_id=None,
            put_after_adjacent=True,
            wait=False,
        )

    def test_success_before(self):
        resource.resource_group_add_cmd(
            self.lib, ["G", "R1", "R2"], dict_to_modifiers(dict(before="X"))
        )
        self.resource.group_add.assert_called_once_with(
            "G",
            ["R1", "R2"],
            adjacent_resource_id="X",
            put_after_adjacent=False,
            wait=False,
        )

    def test_success_after(self):
        resource.resource_group_add_cmd(
            self.lib, ["G", "R1", "R2"], dict_to_modifiers(dict(after="X"))
        )
        self.resource.group_add.assert_called_once_with(
            "G",
            ["R1", "R2"],
            adjacent_resource_id="X",
            put_after_adjacent=True,
            wait=False,
        )

    def test_success_wait(self):
        resource.resource_group_add_cmd(
            self.lib, ["G", "R1", "R2"], dict_to_modifiers(dict(wait="10"))
        )
        self.resource.group_add.assert_called_once_with(
            "G",
            ["R1", "R2"],
            adjacent_resource_id=None,
            put_after_adjacent=True,
            wait="10",
        )


class ResourceMove(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["move_autoclean", "is_any_stonith"])
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_move(self.lib, [], dict_to_modifiers({}))
        self.assertEqual(
            cm.exception.message, "must specify a resource to move"
        )
        self.resource.move_autoclean.assert_not_called()

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_move(
                self.lib,
                ["resource", "arg1", "arg2"],
                dict_to_modifiers({}),
            )
        self.assertIsNone(cm.exception.message)
        self.resource.move_autoclean.assert_not_called()

    def test_success(self):
        resource.resource_move(self.lib, ["resource"], dict_to_modifiers({}))
        self.resource.move_autoclean.assert_called_once_with(
            "resource", node=None, master=False, wait_timeout=-1, strict=False
        )

    def test_success_node(self):
        resource.resource_move(
            self.lib, ["resource", "node"], dict_to_modifiers({})
        )
        self.resource.move_autoclean.assert_called_once_with(
            "resource", node="node", master=False, wait_timeout=-1, strict=False
        )

    def test_success_wait(self):
        resource.resource_move(
            self.lib, ["resource", "node"], dict_to_modifiers(dict(wait=None))
        )
        self.resource.move_autoclean.assert_called_once_with(
            "resource", node="node", master=False, wait_timeout=0, strict=False
        )

    def test_success_all_options(self):
        resource.resource_move(
            self.lib,
            ["resource", "node"],
            dict_to_modifiers(dict(promoted=True, strict=True, wait="10")),
        )
        self.resource.move_autoclean.assert_called_once_with(
            "resource", node="node", master=True, wait_timeout=10, strict=True
        )


class ResourceManage(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["manage", "is_any_stonith"])
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_manage_cmd(self.lib, [], dict_to_modifiers({}))
        self.assertEqual(
            cm.exception.message, "You must specify resource(s) to manage"
        )
        self.resource.manage.assert_not_called()

    def test_one_resource(self):
        resource.resource_manage_cmd(self.lib, ["R1"], dict_to_modifiers({}))
        self.resource.manage.assert_called_once_with(["R1"], with_monitor=False)

    def test_more_resources(self):
        resource.resource_manage_cmd(
            self.lib, ["R1", "R2"], dict_to_modifiers({})
        )
        self.resource.manage.assert_called_once_with(
            ["R1", "R2"], with_monitor=False
        )

    def test_monitor(self):
        resource.resource_manage_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(dict(monitor=True)),
        )
        self.resource.manage.assert_called_once_with(
            ["R1", "R2"], with_monitor=True
        )


class ResourceUnmanage(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["unmanage", "is_any_stonith"])
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_unmanage_cmd(self.lib, [], dict_to_modifiers({}))
        self.assertEqual(
            cm.exception.message, "You must specify resource(s) to unmanage"
        )
        self.resource.unmanage.assert_not_called()

    def test_one_resource(self):
        resource.resource_unmanage_cmd(self.lib, ["R1"], dict_to_modifiers({}))
        self.resource.unmanage.assert_called_once_with(
            ["R1"], with_monitor=False
        )

    def test_more_resources(self):
        resource.resource_unmanage_cmd(
            self.lib, ["R1", "R2"], dict_to_modifiers({})
        )
        self.resource.unmanage.assert_called_once_with(
            ["R1", "R2"], with_monitor=False
        )

    def test_monitor(self):
        resource.resource_unmanage_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(dict(monitor=True)),
        )
        self.resource.unmanage.assert_called_once_with(
            ["R1", "R2"], with_monitor=True
        )


@mock.patch("pcs.resource.print_to_stderr")
class ResourceRestart(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["restart"])
        self.lib.resource = self.resource

    def test_no_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_restart_cmd(self.lib, [], dict_to_modifiers({}))
        self.assertEqual(
            cm.exception.message, "You must specify a resource to restart"
        )
        self.resource.restart.assert_not_called()
        mock_print.assert_not_called()

    def test_one_arg(self, mock_print):
        resource.resource_restart_cmd(
            self.lib, ["resource"], dict_to_modifiers({})
        )
        self.resource.restart.assert_called_once_with("resource", None, None)
        mock_print.assert_called_once_with("resource successfully restarted")

    def test_two_args(self, mock_print):
        resource.resource_restart_cmd(
            self.lib, ["resource", "node"], dict_to_modifiers({})
        )
        self.resource.restart.assert_called_once_with("resource", "node", None)
        mock_print.assert_called_once_with("resource successfully restarted")

    def test_more_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_restart_cmd(
                self.lib, ["one", "two", "three"], dict_to_modifiers({})
            )
        self.assertEqual(cm.exception.message, None)
        self.resource.restart.assert_not_called()
        mock_print.assert_not_called()

    def test_wait(self, mock_print):
        resource.resource_restart_cmd(
            self.lib, ["resource"], dict_to_modifiers({"wait": "10s"})
        )
        self.resource.restart.assert_called_once_with("resource", None, "10s")
        mock_print.assert_called_once_with("resource successfully restarted")

    def test_all_options(self, mock_print):
        resource.resource_restart_cmd(
            self.lib, ["resource", "node"], dict_to_modifiers({"wait": "10s"})
        )
        self.resource.restart.assert_called_once_with("resource", "node", "10s")
        mock_print.assert_called_once_with("resource successfully restarted")

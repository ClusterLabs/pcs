from random import shuffle
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs import resource
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.reports.processor import ReportItemSeverity
from pcs.common.reports.codes import FORCE

from pcs_test.tools.assertions import (
    AssertPcsMixin,
    ac,
)
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


class ResourceMoveBanMixin:
    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.cli_command(self.lib, [], dict_to_modifiers({}))
        self.assertEqual(cm.exception.message, self.no_args_error)
        self.lib_command.assert_not_called()

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.cli_command(
                self.lib,
                ["resource", "arg1", "arg2", "arg3"],
                dict_to_modifiers({}),
            )
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()

    def test_node_twice(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.cli_command(
                self.lib,
                ["resource", "node1", "node2"],
                dict_to_modifiers({}),
            )
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()

    def test_lifetime_twice(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.cli_command(
                self.lib,
                ["resource", "lifetime=1h", "lifetime=2h"],
                dict_to_modifiers({}),
            )
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()

    def test_success(self):
        self.cli_command(self.lib, ["resource"], dict_to_modifiers({}))
        self.lib_command.assert_called_once_with(
            "resource", lifetime=None, master=False, node=None, wait=False
        )

    def test_success_node(self):
        self.cli_command(self.lib, ["resource", "node"], dict_to_modifiers({}))
        self.lib_command.assert_called_once_with(
            "resource", lifetime=None, master=False, node="node", wait=False
        )

    def test_success_lifetime(self):
        self.cli_command(
            self.lib, ["resource", "lifetime=1h"], dict_to_modifiers({})
        )
        self.lib_command.assert_called_once_with(
            "resource", lifetime="P1h", master=False, node=None, wait=False
        )

    def test_success_lifetime_unchanged(self):
        self.cli_command(
            self.lib, ["resource", "lifetime=T1h"], dict_to_modifiers({})
        )
        self.lib_command.assert_called_once_with(
            "resource", lifetime="T1h", master=False, node=None, wait=False
        )

    def test_success_node_lifetime(self):
        self.cli_command(
            self.lib,
            ["resource", "node", "lifetime=1h"],
            dict_to_modifiers({}),
        )
        self.lib_command.assert_called_once_with(
            "resource", lifetime="P1h", master=False, node="node", wait=False
        )

    def test_success_lifetime_node(self):
        self.cli_command(
            self.lib,
            ["resource", "lifetime=1h", "node"],
            dict_to_modifiers({}),
        )
        self.lib_command.assert_called_once_with(
            "resource", lifetime="P1h", master=False, node="node", wait=False
        )

    def test_success_all_options(self):
        self.cli_command(
            self.lib,
            ["resource", "lifetime=1h", "node"],
            dict_to_modifiers(dict(promoted=True, wait="10")),
        )
        self.lib_command.assert_called_once_with(
            "resource", lifetime="P1h", master=True, node="node", wait="10"
        )


class ResourceMoveLegacy(ResourceMoveBanMixin, TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["move", "is_any_stonith"])
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource
        self.lib_command = self.resource.move
        self.cli_command = resource.resource_move_with_constraint
        self.no_args_error = "must specify a resource to move"


class ResourceBan(ResourceMoveBanMixin, TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["ban", "is_any_stonith"])
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource
        self.lib_command = self.resource.ban
        self.cli_command = resource.resource_ban
        self.no_args_error = "must specify a resource to ban"


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


class ResourceClear(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["unmove_unban", "is_any_stonith"])
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_unmove_unban(self.lib, [], dict_to_modifiers({}))
        self.assertEqual(
            cm.exception.message, "must specify a resource to clear"
        )
        self.resource.unmove_unban.assert_not_called()

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_unmove_unban(
                self.lib,
                ["resource", "arg1", "arg2"],
                dict_to_modifiers({}),
            )
        self.assertIsNone(cm.exception.message)
        self.resource.unmove_unban.assert_not_called()

    def test_success(self):
        resource.resource_unmove_unban(
            self.lib, ["resource"], dict_to_modifiers({})
        )
        self.resource.unmove_unban.assert_called_once_with(
            "resource", node=None, master=False, expired=False, wait=False
        )

    def test_success_node(self):
        resource.resource_unmove_unban(
            self.lib, ["resource", "node"], dict_to_modifiers({})
        )
        self.resource.unmove_unban.assert_called_once_with(
            "resource", node="node", master=False, expired=False, wait=False
        )

    def test_success_all_options(self):
        resource.resource_unmove_unban(
            self.lib,
            ["resource", "node"],
            dict_to_modifiers(dict(promoted=True, expired=True, wait="10")),
        )
        self.resource.unmove_unban.assert_called_once_with(
            "resource", node="node", master=True, expired=True, wait="10"
        )


class ResourceDisable(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource", "env"])
        self.resource = mock.Mock(
            spec_set=[
                "disable",
                "disable_safe",
                "disable_simulate",
                "is_any_stonith",
            ]
        )
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource

        self.report_processor = mock.Mock(
            spec_set=["suppress_reports_of_severity"]
        )
        self.env = mock.Mock(spec_set=["report_processor"])
        self.lib.env = self.env
        self.env.report_processor = self.report_processor

    @staticmethod
    def _fixture_output(plaintext=None, resources=None):
        plaintext = plaintext if plaintext is not None else "simulate output"
        resources = resources if resources is not None else ["Rx", "Ry"]
        return dict(
            plaintext_simulated_status=plaintext,
            other_affected_resource_list=resources,
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_disable_common(
                self.lib, [], dict_to_modifiers({})
            )
        self.assertEqual(
            cm.exception.message, "You must specify resource(s) to disable"
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_one_resource(self):
        resource.resource_disable_common(
            self.lib, ["R1"], dict_to_modifiers({})
        )
        self.resource.disable.assert_called_once_with(["R1"], False, set())
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_more_resources(self):
        resource.resource_disable_common(
            self.lib, ["R1", "R2"], dict_to_modifiers({})
        )
        self.resource.disable.assert_called_once_with(
            ["R1", "R2"], False, set()
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_force(self):
        resource.resource_disable_common(
            self.lib, ["R1"], dict_to_modifiers(dict(force=True))
        )
        self.resource.disable.assert_called_once_with(["R1"], False, {FORCE})
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_brief(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_disable_common(
                self.lib, ["R1", "R2"], dict_to_modifiers(dict(brief=True))
            )
        self.assertEqual(
            cm.exception.message,
            "'--brief' cannot be used without '--simulate' or '--safe'",
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_safe(self):
        resource.resource_disable_common(
            self.lib, ["R1", "R2"], dict_to_modifiers(dict(safe=True))
        )
        self.resource.disable_safe.assert_called_once_with(
            ["R1", "R2"], True, False
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_safe_brief(self):
        resource.resource_disable_common(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(dict(safe=True, brief=True)),
        )
        self.resource.disable_safe.assert_called_once_with(
            ["R1", "R2"], True, False
        )
        self.report_processor.suppress_reports_of_severity.assert_called_once_with(
            [ReportItemSeverity.INFO]
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_safe_wait(self):
        resource.resource_disable_common(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(dict(safe=True, wait="10")),
        )
        self.resource.disable_safe.assert_called_once_with(
            ["R1", "R2"], True, "10"
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_safe_no_strict(self):
        resource.resource_disable_common(
            self.lib, ["R1", "R2"], dict_to_modifiers({"no-strict": True})
        )
        self.resource.disable_safe.assert_called_once_with(
            ["R1", "R2"], False, False
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_safe_no_strict_wait(self):
        resource.resource_disable_common(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers({"no-strict": True, "wait": "10"}),
        )
        self.resource.disable_safe.assert_called_once_with(
            ["R1", "R2"], False, "10"
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    @mock.patch("pcs.resource.print")
    def test_simulate(self, mock_print):
        self.resource.disable_simulate.return_value = self._fixture_output()
        resource.resource_disable_common(
            self.lib, ["R1", "R2"], dict_to_modifiers(dict(simulate=True))
        )
        self.resource.disable_simulate.assert_called_once_with(
            ["R1", "R2"], True
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        mock_print.assert_called_once_with("simulate output")

    @mock.patch("pcs.resource.print")
    def test_simulate_brief(self, mock_print):
        self.resource.disable_simulate.return_value = self._fixture_output()
        resource.resource_safe_disable_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(dict(simulate=True, brief=True)),
        )
        self.resource.disable_simulate.assert_called_once_with(
            ["R1", "R2"], True
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        mock_print.assert_called_once_with("Rx\nRy")

    @mock.patch("pcs.resource.print")
    def test_simulate_brief_nostrict(self, mock_print):
        self.resource.disable_simulate.return_value = self._fixture_output()
        resource.resource_safe_disable_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(
                {"simulate": True, "brief": True, "no-strict": True}
            ),
        )
        self.resource.disable_simulate.assert_called_once_with(
            ["R1", "R2"], False
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        mock_print.assert_called_once_with("Rx\nRy")

    @mock.patch("pcs.resource.print")
    def test_simulate_brief_nothing_affected(self, mock_print):
        self.resource.disable_simulate.return_value = self._fixture_output(
            resources=[]
        )
        resource.resource_safe_disable_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(dict(simulate=True, brief=True)),
        )
        self.resource.disable_simulate.assert_called_once_with(
            ["R1", "R2"], True
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        mock_print.assert_not_called()

    def test_simulate_wait(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_disable_common(
                self.lib,
                ["R1"],
                dict_to_modifiers(dict(simulate=True, wait=True)),
            )
        self.assertEqual(
            cm.exception.message,
            "Only one of '--simulate', '--wait' can be used",
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_simulate_safe(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_disable_common(
                self.lib,
                ["R1"],
                dict_to_modifiers(
                    {"no-strict": True, "simulate": True, "safe": True}
                ),
            )
        self.assertEqual(
            cm.exception.message, "'--simulate' cannot be used with '--safe'"
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_wait(self):
        resource.resource_disable_common(
            self.lib, ["R1", "R2"], dict_to_modifiers(dict(wait="10"))
        )
        self.report_processor.suppress_reports_of_severity.assert_not_called()
        self.resource.disable.assert_called_once_with(["R1", "R2"], "10", set())
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()


class ResourceSafeDisable(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(
            spec_set=[
                "disable",
                "disable_safe",
                "disable_simulate",
                "is_any_stonith",
            ]
        )
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource
        self.force_warning = (
            "option '--force' is specified therefore checks for disabling "
            "resource safely will be skipped"
        )

    @staticmethod
    def _fixture_output(plaintext=None, resources=None):
        plaintext = plaintext if plaintext is not None else "simulate output"
        resources = resources if resources is not None else ["Rx", "Ry"]
        return dict(
            plaintext_simulated_status=plaintext,
            other_affected_resource_list=resources,
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_safe_disable_cmd(
                self.lib, [], dict_to_modifiers({})
            )
        self.assertEqual(
            cm.exception.message, "You must specify resource(s) to disable"
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_one_resource(self):
        resource.resource_safe_disable_cmd(
            self.lib, ["R1"], dict_to_modifiers({})
        )
        self.resource.disable_safe.assert_called_once_with(["R1"], True, False)
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_more_resources(self):
        resource.resource_safe_disable_cmd(
            self.lib, ["R1", "R2"], dict_to_modifiers({})
        )
        self.resource.disable_safe.assert_called_once_with(
            ["R1", "R2"], True, False
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_wait(self):
        resource.resource_safe_disable_cmd(
            self.lib, ["R1", "R2"], dict_to_modifiers(dict(wait="10"))
        )
        self.resource.disable_safe.assert_called_once_with(
            ["R1", "R2"], True, "10"
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_no_strict(self):
        resource.resource_safe_disable_cmd(
            self.lib, ["R1", "R2"], dict_to_modifiers({"no-strict": True})
        )
        self.resource.disable_safe.assert_called_once_with(
            ["R1", "R2"], False, False
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_no_strict_wait(self):
        resource.resource_safe_disable_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers({"no-strict": True, "wait": "10"}),
        )
        self.resource.disable_safe.assert_called_once_with(
            ["R1", "R2"], False, "10"
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    @mock.patch("pcs.resource.warn")
    def test_force(self, mock_warn):
        resource.resource_safe_disable_cmd(
            self.lib, ["R1", "R2"], dict_to_modifiers({"force": True})
        )
        self.resource.disable.assert_called_once_with(
            ["R1", "R2"], False, set()
        )
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()
        mock_warn.assert_called_once_with(self.force_warning)

    @mock.patch("pcs.resource.warn")
    def test_force_wait(self, mock_warn):
        resource.resource_safe_disable_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers({"force": True, "wait": "10"}),
        )
        self.resource.disable.assert_called_once_with(["R1", "R2"], "10", set())
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()
        mock_warn.assert_called_once_with(self.force_warning)

    @mock.patch("pcs.resource.print")
    def test_simulate(self, mock_print):
        self.resource.disable_simulate.return_value = self._fixture_output()
        resource.resource_safe_disable_cmd(
            self.lib, ["R1", "R2"], dict_to_modifiers(dict(simulate=True))
        )
        self.resource.disable_simulate.assert_called_once_with(
            ["R1", "R2"], True
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        mock_print.assert_called_once_with("simulate output")

    @mock.patch("pcs.resource.print")
    def test_simulate_brief(self, mock_print):
        self.resource.disable_simulate.return_value = self._fixture_output()
        resource.resource_safe_disable_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(dict(simulate=True, brief=True)),
        )
        self.resource.disable_simulate.assert_called_once_with(
            ["R1", "R2"], True
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        mock_print.assert_called_once_with("Rx\nRy")

    @mock.patch("pcs.resource.print")
    def test_simulate_brief_nostrict(self, mock_print):
        self.resource.disable_simulate.return_value = self._fixture_output()
        resource.resource_safe_disable_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(
                {"simulate": True, "brief": True, "no-strict": True}
            ),
        )
        self.resource.disable_simulate.assert_called_once_with(
            ["R1", "R2"], False
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        mock_print.assert_called_once_with("Rx\nRy")

    @mock.patch("pcs.resource.print")
    def test_simulate_brief_nothing_affected(self, mock_print):
        self.resource.disable_simulate.return_value = self._fixture_output(
            resources=[]
        )
        resource.resource_safe_disable_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(
                {"simulate": True, "brief": True, "no-strict": True}
            ),
        )
        self.resource.disable_simulate.assert_called_once_with(
            ["R1", "R2"], False
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        mock_print.assert_not_called()

    def test_simulate_wait(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_safe_disable_cmd(
                self.lib,
                ["R1"],
                dict_to_modifiers(dict(simulate=True, wait=True)),
            )
        self.assertEqual(
            cm.exception.message,
            "Only one of '--simulate', '--wait' can be used",
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_simulate_force(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_safe_disable_cmd(
                self.lib,
                ["R1"],
                dict_to_modifiers(dict(simulate=True, force=True)),
            )
        self.assertEqual(
            cm.exception.message, "'--force' cannot be used with '--simulate'"
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    @mock.patch("pcs.resource.print")
    def test_simulate_no_strict(self, mock_print):
        self.resource.disable_simulate.return_value = self._fixture_output()
        resource.resource_safe_disable_cmd(
            self.lib,
            ["R1"],
            dict_to_modifiers({"simulate": True, "no-strict": True}),
        )
        self.resource.disable_simulate.assert_called_once_with(["R1"], False)
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        mock_print.assert_called_once_with("simulate output")

    def test_simulate_no_strict_force(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_safe_disable_cmd(
                self.lib,
                ["R1"],
                dict_to_modifiers(
                    {"simulate": True, "no-strict": True, "force": True}
                ),
            )
        self.assertEqual(
            cm.exception.message,
            "'--force' cannot be used with '--no-strict', '--simulate'",
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()

    def test_force_no_strict(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_safe_disable_cmd(
                self.lib,
                ["R1"],
                dict_to_modifiers({"force": True, "no-strict": True}),
            )
        self.assertEqual(
            cm.exception.message, "'--force' cannot be used with '--no-strict'"
        )
        self.resource.disable.assert_not_called()
        self.resource.disable_safe.assert_not_called()
        self.resource.disable_simulate.assert_not_called()


class ResourceEnable(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["enable", "is_any_stonith"])
        self.resource.is_any_stonith.return_value = False
        self.lib.resource = self.resource

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            resource.resource_enable_cmd(self.lib, [], dict_to_modifiers({}))
        self.assertEqual(
            cm.exception.message, "You must specify resource(s) to enable"
        )
        self.resource.enable.assert_not_called()

    def test_one_resource(self):
        resource.resource_enable_cmd(self.lib, ["R1"], dict_to_modifiers({}))
        self.resource.enable.assert_called_once_with(["R1"], False)

    def test_more_resources(self):
        resource.resource_enable_cmd(
            self.lib, ["R1", "R2"], dict_to_modifiers({})
        )
        self.resource.enable.assert_called_once_with(["R1", "R2"], False)

    def test_wait(self):
        resource.resource_enable_cmd(
            self.lib,
            ["R1", "R2"],
            dict_to_modifiers(dict(wait="10")),
        )
        self.resource.enable.assert_called_once_with(["R1", "R2"], "10")


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

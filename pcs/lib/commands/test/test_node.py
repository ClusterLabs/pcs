from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree
import logging

from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock, TestCase

from pcs.common import report_codes
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import ReportItemSeverity as severity

from pcs.lib.commands import node as lib


mocked_cib = etree.fromstring("<cib />")

class StandbyMaintenancePassParameters(TestCase):
    def setUp(self):
        self.lib_env = "lib_env"
        self.nodes = "nodes"
        self.wait = "wait"
        self.standby_on = {"standby": "on"}
        self.standby_off = {"standby": ""}
        self.maintenance_on = {"maintenance": "on"}
        self.maintenance_off = {"maintenance": ""}

@mock.patch("pcs.lib.commands.node._set_instance_attrs_local_node")
class StandbyMaintenancePassParametersLocal(StandbyMaintenancePassParameters):
    def test_standby(self, mock_doer):
        lib.standby_unstandby_local(self.lib_env, True, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.standby_on,
            self.wait
        )

    def test_unstandby(self, mock_doer):
        lib.standby_unstandby_local(self.lib_env, False, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.standby_off,
            self.wait
        )

    def test_maintenance(self, mock_doer):
        lib.maintenance_unmaintenance_local(self.lib_env, True, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.maintenance_on,
            self.wait
        )

    def test_unmaintenance(self, mock_doer):
        lib.maintenance_unmaintenance_local(self.lib_env, False, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.maintenance_off,
            self.wait
        )

@mock.patch("pcs.lib.commands.node._set_instance_attrs_node_list")
class StandbyMaintenancePassParametersList(StandbyMaintenancePassParameters):
    def test_standby(self, mock_doer):
        lib.standby_unstandby_list(self.lib_env, True, self.nodes, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.standby_on,
            self.nodes,
            self.wait
        )

    def test_unstandby(self, mock_doer):
        lib.standby_unstandby_list(self.lib_env, False, self.nodes, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.standby_off,
            self.nodes,
            self.wait
        )

    def test_maintenance(self, mock_doer):
        lib.maintenance_unmaintenance_list(
            self.lib_env, True, self.nodes, self.wait
        )
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.maintenance_on,
            self.nodes,
            self.wait
        )

    def test_unmaintenance(self, mock_doer):
        lib.maintenance_unmaintenance_list(
            self.lib_env, False, self.nodes, self.wait
        )
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.maintenance_off,
            self.nodes,
            self.wait
        )

@mock.patch("pcs.lib.commands.node._set_instance_attrs_all_nodes")
class StandbyMaintenancePassParametersAll(StandbyMaintenancePassParameters):
    def test_standby(self, mock_doer):
        lib.standby_unstandby_all(self.lib_env, True, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.standby_on,
            self.wait
        )

    def test_unstandby(self, mock_doer):
        lib.standby_unstandby_all(self.lib_env, False, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.standby_off,
            self.wait
        )

    def test_maintenance(self, mock_doer):
        lib.maintenance_unmaintenance_all(self.lib_env, True, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.maintenance_on,
            self.wait
        )

    def test_unmaintenance(self, mock_doer):
        lib.maintenance_unmaintenance_all(self.lib_env, False, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env,
            self.maintenance_off,
            self.wait
        )

class SetInstaceAttrsBase(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def fixture_state(self, node_count):
        node_list = []
        for i in range(node_count):
            node = mock.MagicMock()
            node.attrs = mock.MagicMock()
            node.attrs.name = "node-{0}".format(i)
            node_list.append(node)
        state = mock.MagicMock()
        state.node_section = mock.MagicMock()
        state.node_section.nodes = node_list
        return state

@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
@mock.patch.object(
    LibraryEnvironment,
    "get_cib",
    lambda self: mocked_cib
)
@mock.patch.object(
    LibraryEnvironment,
    "_push_cib_xml",
    lambda self, cib: None
)
@mock.patch("pcs.lib.env.get_cib_xml", lambda runner: "<cib />")
@mock.patch("pcs.lib.commands.node.get_cluster_status_xml", lambda runner: None)
@mock.patch("pcs.lib.commands.node.update_node_instance_attrs")
@mock.patch("pcs.lib.commands.node.get_local_node_name")
@mock.patch("pcs.lib.commands.node.ClusterState")
@mock.patch("pcs.lib.commands.node.wait_for_idle")
@mock.patch("pcs.lib.commands.node.ensure_wait_for_idle_support")
class SetInstaceAttrsLocal(SetInstaceAttrsBase):
    def test_not_possible_with_cib_file(
        self, mock_has_wait, mock_wait, mock_status, mock_name, mock_attrs
    ):
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            cib_data="<cib />"
        )

        assert_raise_library_error(
            lambda: lib._set_instance_attrs_local_node(
                lib_env, "attrs", "wait"
            ),
            (
                severity.ERROR,
                report_codes.LIVE_ENVIRONMENT_REQUIRED_FOR_LOCAL_NODE,
                {},
                None
            )
        )

        mock_has_wait.assert_not_called()
        mock_wait.assert_not_called()
        mock_status.assert_not_called()
        mock_name.assert_not_called()
        mock_attrs.assert_not_called()

    def test_success(
        self, mock_has_wait, mock_wait, mock_status, mock_name, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        cluster_state = self.fixture_state(2)
        mock_status.return_value = cluster_state
        mock_name.return_value = "node-1"

        lib._set_instance_attrs_local_node(lib_env, "attrs", False)

        mock_has_wait.assert_not_called()
        mock_wait.assert_not_called()
        mock_status.assert_called_once_with(None)
        mock_name.assert_called_once_with("mock_runner")
        mock_attrs.assert_called_once_with(
            mocked_cib, "node-1", "attrs", cluster_state.node_section.nodes
        )

    def test_wait_not_supported(
        self, mock_has_wait, mock_wait, mock_status, mock_name, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        mock_has_wait.side_effect = ValueError

        self.assertRaises(
            ValueError,
            lambda: lib._set_instance_attrs_local_node(
                lib_env, "attrs", "wait"
            )
        )

        mock_has_wait.assert_called_once_with("mock_runner")
        mock_wait.assert_not_called()
        mock_status.assert_not_called()
        mock_name.assert_not_called()
        mock_attrs.assert_not_called()

    def test_wait_bad_timeout(
        self, mock_has_wait, mock_wait, mock_status, mock_name, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib._set_instance_attrs_local_node(
                lib_env, "attrs", "wait"
            ),
            (
                severity.ERROR,
                report_codes.INVALID_TIMEOUT_VALUE,
                {
                    "timeout": "wait",
                },
                None
            )
        )

        mock_has_wait.assert_called_once_with("mock_runner")
        mock_wait.assert_not_called()
        mock_status.assert_not_called()
        mock_name.assert_not_called()
        mock_attrs.assert_not_called()

    def test_wait_success(
        self, mock_has_wait, mock_wait, mock_status, mock_name, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        cluster_state = self.fixture_state(2)
        mock_status.return_value = cluster_state
        mock_name.return_value = "node-1"

        lib._set_instance_attrs_local_node(lib_env, "attrs", 10)

        mock_has_wait.assert_called_once_with("mock_runner")
        mock_wait.assert_called_once_with("mock_runner", 10)
        mock_status.assert_called_once_with(None)
        mock_name.assert_called_once_with("mock_runner")
        mock_attrs.assert_called_once_with(
            mocked_cib, "node-1", "attrs", cluster_state.node_section.nodes
        )

@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
@mock.patch.object(
    LibraryEnvironment,
    "get_cib",
    lambda self: mocked_cib
)
@mock.patch.object(
    LibraryEnvironment,
    "_push_cib_xml",
    lambda self, cib: None
)
@mock.patch("pcs.lib.env.get_cib_xml", lambda runner: "<cib />")
@mock.patch("pcs.lib.commands.node.get_cluster_status_xml", lambda runner: None)
@mock.patch("pcs.lib.commands.node.update_node_instance_attrs")
@mock.patch("pcs.lib.commands.node.ClusterState")
@mock.patch("pcs.lib.commands.node.wait_for_idle")
@mock.patch("pcs.lib.commands.node.ensure_wait_for_idle_support")
class SetInstaceAttrsAll(SetInstaceAttrsBase):
    def test_success(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        cluster_state = self.fixture_state(2)
        mock_status.return_value = cluster_state

        lib._set_instance_attrs_all_nodes(lib_env, "attrs", False)

        mock_has_wait.assert_not_called()
        mock_wait.assert_not_called()
        mock_status.assert_called_once_with(None)
        self.assertEqual(2, len(mock_attrs.mock_calls))
        mock_attrs.assert_has_calls([
            mock.call(
                mocked_cib, "node-0", "attrs", cluster_state.node_section.nodes
            ),
            mock.call(
                mocked_cib, "node-1", "attrs", cluster_state.node_section.nodes
            ),
        ])

    def test_wait_with_cib_file(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            cib_data="<cib />"
        )

        assert_raise_library_error(
            lambda: lib._set_instance_attrs_all_nodes(
                lib_env, "attrs", "wait"
            ),
            (
                severity.ERROR,
                report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER,
                { },
                None
            )
        )

        mock_has_wait.assert_not_called()
        mock_wait.assert_not_called()
        mock_status.assert_not_called()
        mock_attrs.assert_not_called()

    def test_wait_not_supported(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        mock_has_wait.side_effect = ValueError

        self.assertRaises(
            ValueError,
            lambda: lib._set_instance_attrs_all_nodes(
                lib_env, "attrs", "wait"
            )
        )

        mock_has_wait.assert_called_once_with("mock_runner")
        mock_wait.assert_not_called()
        mock_status.assert_not_called()
        mock_attrs.assert_not_called()

    def test_wait_bad_timeout(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib._set_instance_attrs_all_nodes(
                lib_env, "attrs", "wait"
            ),
            (
                severity.ERROR,
                report_codes.INVALID_TIMEOUT_VALUE,
                {
                    "timeout": "wait",
                },
                None
            )
        )

        mock_has_wait.assert_called_once_with("mock_runner")
        mock_wait.assert_not_called()
        mock_status.assert_not_called()
        mock_attrs.assert_not_called()

    def test_wait_success(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        cluster_state = self.fixture_state(2)
        mock_status.return_value = cluster_state

        lib._set_instance_attrs_all_nodes(lib_env, "attrs", 10)

        mock_has_wait.assert_called_once_with("mock_runner")
        mock_wait.assert_called_once_with("mock_runner", 10)
        mock_status.assert_called_once_with(None)
        mock_attrs.assert_has_calls([
            mock.call(
                mocked_cib, "node-0", "attrs", cluster_state.node_section.nodes
            ),
            mock.call(
                mocked_cib, "node-1", "attrs", cluster_state.node_section.nodes
            ),
        ])

@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
@mock.patch.object(
    LibraryEnvironment,
    "get_cib",
    lambda self: mocked_cib
)
@mock.patch.object(
    LibraryEnvironment,
    "_push_cib_xml",
    lambda self, cib: None
)
@mock.patch("pcs.lib.env.get_cib_xml", lambda runner: "<cib />")
@mock.patch("pcs.lib.commands.node.get_cluster_status_xml", lambda runner: None)
@mock.patch("pcs.lib.commands.node.update_node_instance_attrs")
@mock.patch("pcs.lib.commands.node.ClusterState")
@mock.patch("pcs.lib.commands.node.wait_for_idle")
@mock.patch("pcs.lib.commands.node.ensure_wait_for_idle_support")
class SetInstaceAttrsList(SetInstaceAttrsBase):
    def test_success(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        cluster_state = self.fixture_state(4)
        mock_status.return_value = cluster_state

        lib._set_instance_attrs_node_list(
            lib_env, "attrs", ["node-1", "node-2"], False
        )

        mock_has_wait.assert_not_called()
        mock_wait.assert_not_called()
        mock_status.assert_called_once_with(None)
        self.assertEqual(2, len(mock_attrs.mock_calls))
        mock_attrs.assert_has_calls([
            mock.call(
                mocked_cib, "node-1", "attrs", cluster_state.node_section.nodes
            ),
            mock.call(
                mocked_cib, "node-2", "attrs", cluster_state.node_section.nodes
            ),
        ])

    def test_bad_node(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        cluster_state = self.fixture_state(4)
        mock_status.return_value = cluster_state

        assert_raise_library_error(
            lambda: lib._set_instance_attrs_node_list(
                lib_env, "attrs", ["node-1", "node-9"], False
            ),
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "node-9",
                },
                None
            )
        )

        mock_has_wait.assert_not_called()
        mock_wait.assert_not_called()
        mock_status.assert_called_once_with(None)
        mock_attrs.assert_not_called()

    def test_wait_with_cib_file(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            cib_data="<cib />"
        )

        assert_raise_library_error(
            lambda: lib._set_instance_attrs_node_list(
                lib_env, "attrs", ["node-1"], "wait"
            ),
            (
                severity.ERROR,
                report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER,
                { },
                None
            )
        )

        mock_has_wait.assert_not_called()
        mock_wait.assert_not_called()
        mock_status.assert_not_called()
        mock_attrs.assert_not_called()

    def test_wait_not_supported(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        mock_has_wait.side_effect = ValueError

        self.assertRaises(
            ValueError,
            lambda: lib._set_instance_attrs_node_list(
                lib_env, "attrs", ["node-1"], "wait"
            )
        )

        mock_has_wait.assert_called_once_with("mock_runner")
        mock_wait.assert_not_called()
        mock_status.assert_not_called()
        mock_attrs.assert_not_called()

    def test_wait_bad_timeout(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib._set_instance_attrs_node_list(
                lib_env, "attrs", ["node-1"], "wait"
            ),
            (
                severity.ERROR,
                report_codes.INVALID_TIMEOUT_VALUE,
                {
                    "timeout": "wait",
                },
                None
            )
        )

        mock_has_wait.assert_called_once_with("mock_runner")
        mock_wait.assert_not_called()
        mock_status.assert_not_called()
        mock_attrs.assert_not_called()

    def test_wait_success(
        self, mock_has_wait, mock_wait, mock_status, mock_attrs
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        cluster_state = self.fixture_state(4)
        mock_status.return_value = cluster_state

        lib._set_instance_attrs_node_list(
            lib_env, "attrs", ["node-1", "node-2"], 10
        )

        mock_has_wait.assert_called_once_with("mock_runner")
        mock_wait.assert_called_once_with("mock_runner", 10)
        mock_status.assert_called_once_with(None)
        mock_attrs.assert_has_calls([
            mock.call(
                mocked_cib, "node-1", "attrs", cluster_state.node_section.nodes
            ),
            mock.call(
                mocked_cib, "node-2", "attrs", cluster_state.node_section.nodes
            ),
        ])


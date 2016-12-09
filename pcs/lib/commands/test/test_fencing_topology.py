from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial
import logging

from pcs.common.fencing_topology import (
    TARGET_TYPE_REGEXP,
    TARGET_TYPE_ATTRIBUTE,
)
from pcs.lib.env import LibraryEnvironment
from pcs.test.tools.misc import create_patcher
from pcs.test.tools.pcs_unittest import mock, TestCase
from pcs.test.tools.custom_mock import MockLibraryReportProcessor

from pcs.lib.commands import fencing_topology as lib


create_lib_env = partial(
    LibraryEnvironment,
    mock.MagicMock(logging.Logger),
    MockLibraryReportProcessor()
)
patch_env = partial(mock.patch.object, LibraryEnvironment)
patch_command = create_patcher("pcs.lib.commands.fencing_topology")


@patch_command("cib_fencing_topology.add_level")
@patch_command("get_resources")
@patch_command("get_fencing_topology")
@patch_env("push_cib")
@patch_command("ClusterState")
@patch_command("get_cluster_status_xml")
@patch_env("get_cib")
@patch_env("cmd_runner", lambda self: "mocked cmd_runner")
class AddLevel(TestCase):
    def prepare_mocks(
        self, mock_get_cib, mock_status_xml, mock_status, mock_get_topology,
        mock_get_resources
    ):
        mock_get_cib.return_value = "mocked cib"
        mock_status_xml.return_value = "mock get_cluster_status_xml"
        mock_status.return_value = mock.MagicMock(
            node_section=mock.MagicMock(nodes="nodes")
        )
        mock_get_topology.return_value = "topology el"
        mock_get_resources.return_value = "resources_el"

    def assert_mocks(
        self, mock_status_xml, mock_status, mock_get_topology,
        mock_get_resources, mock_push_cib
    ):
        mock_status_xml.assert_called_once_with("mocked cmd_runner")
        mock_status.assert_called_once_with("mock get_cluster_status_xml")
        mock_get_topology.assert_called_once_with("mocked cib")
        mock_get_resources.assert_called_once_with("mocked cib")
        mock_push_cib.assert_called_once_with("mocked cib")

    def test_success(
        self, mock_get_cib, mock_status_xml, mock_status, mock_push_cib,
        mock_get_topology, mock_get_resources, mock_add_level
    ):
        self.prepare_mocks(
            mock_get_cib, mock_status_xml, mock_status, mock_get_topology,
            mock_get_resources
        )
        lib_env = create_lib_env()

        lib.add_level(
            lib_env, "level", "target type", "target value", "devices",
            "force device", "force node"
        )

        mock_add_level.assert_called_once_with(
            lib_env.report_processor,
            "topology el",
            "resources_el",
            "level",
            "target type",
            "target value",
            "devices",
            "nodes",
            "force device",
            "force node"
        )
        mock_get_cib.assert_called_once_with(None)
        self.assert_mocks(
            mock_status_xml, mock_status, mock_get_topology, mock_get_resources,
            mock_push_cib
        )

    def test_target_attribute_updates_cib(
        self, mock_get_cib, mock_status_xml, mock_status, mock_push_cib,
        mock_get_topology, mock_get_resources, mock_add_level
    ):
        self.prepare_mocks(
            mock_get_cib, mock_status_xml, mock_status, mock_get_topology,
            mock_get_resources
        )
        lib_env = create_lib_env()

        lib.add_level(
            lib_env, "level", TARGET_TYPE_ATTRIBUTE, "target value", "devices",
            "force device", "force node"
        )

        mock_add_level.assert_called_once_with(
            lib_env.report_processor,
            "topology el",
            "resources_el",
            "level",
            TARGET_TYPE_ATTRIBUTE,
            "target value",
            "devices",
            "nodes",
            "force device",
            "force node"
        )
        mock_get_cib.assert_called_once_with((2, 4, 0))
        self.assert_mocks(
            mock_status_xml, mock_status, mock_get_topology, mock_get_resources,
            mock_push_cib
        )

    def test_target_regexp_updates_cib(
        self, mock_get_cib, mock_status_xml, mock_status, mock_push_cib,
        mock_get_topology, mock_get_resources, mock_add_level
    ):
        self.prepare_mocks(
            mock_get_cib, mock_status_xml, mock_status, mock_get_topology,
            mock_get_resources
        )
        lib_env = create_lib_env()

        lib.add_level(
            lib_env, "level", TARGET_TYPE_REGEXP, "target value", "devices",
            "force device", "force node"
        )

        mock_add_level.assert_called_once_with(
            lib_env.report_processor,
            "topology el",
            "resources_el",
            "level",
            TARGET_TYPE_REGEXP,
            "target value",
            "devices",
            "nodes",
            "force device",
            "force node"
        )
        mock_get_cib.assert_called_once_with((2, 3, 0))
        self.assert_mocks(
            mock_status_xml, mock_status, mock_get_topology, mock_get_resources,
            mock_push_cib
        )

@patch_command("cib_fencing_topology.export")
@patch_command("get_fencing_topology")
@patch_env("push_cib")
@patch_env("get_cib", lambda self: "mocked cib")
class GetConfig(TestCase):
    def test_success(self, mock_push_cib, mock_get_topology, mock_export):
        mock_get_topology.return_value = "topology el"
        mock_export.return_value = "exported config"
        lib_env = create_lib_env()

        self.assertEqual(
            "exported config",
            lib.get_config(lib_env)
        )

        mock_export.assert_called_once_with("topology el")
        mock_get_topology.assert_called_once_with("mocked cib")
        mock_push_cib.assert_not_called()


@patch_command("cib_fencing_topology.remove_all_levels")
@patch_command("get_fencing_topology")
@patch_env("push_cib")
@patch_env("get_cib", lambda self: "mocked cib")
class RemoveAllLevels(TestCase):
    def test_success(self, mock_push_cib, mock_get_topology, mock_remove):
        mock_get_topology.return_value = "topology el"
        lib_env = create_lib_env()

        lib.remove_all_levels(lib_env)

        mock_remove.assert_called_once_with("topology el")
        mock_get_topology.assert_called_once_with("mocked cib")
        mock_push_cib.assert_called_once_with("mocked cib")


@patch_command("cib_fencing_topology.remove_levels_by_params")
@patch_command("get_fencing_topology")
@patch_env("push_cib")
@patch_env("get_cib", lambda self: "mocked cib")
class RemoveLevelsByParams(TestCase):
    def test_success(self, mock_push_cib, mock_get_topology, mock_remove):
        mock_get_topology.return_value = "topology el"
        lib_env = create_lib_env()

        lib.remove_levels_by_params(
            lib_env, "level", "target type", "target value", "devices", "ignore"
        )

        mock_remove.assert_called_once_with(
            lib_env.report_processor,
            "topology el",
            "level",
            "target type",
            "target value",
            "devices",
            "ignore"
        )
        mock_get_topology.assert_called_once_with("mocked cib")
        mock_push_cib.assert_called_once_with("mocked cib")


@patch_command("cib_fencing_topology.verify")
@patch_command("get_resources")
@patch_command("get_fencing_topology")
@patch_env("push_cib")
@patch_command("ClusterState")
@patch_command("get_cluster_status_xml")
@patch_env("get_cib", lambda self: "mocked cib")
@patch_env("cmd_runner", lambda self: "mocked cmd_runner")
class Verify(TestCase):
    def test_success(
        self, mock_status_xml, mock_status, mock_push_cib, mock_get_topology,
        mock_get_resources, mock_verify
    ):
        mock_status_xml.return_value = "mock get_cluster_status_xml"
        mock_status.return_value = mock.MagicMock(
            node_section=mock.MagicMock(nodes="nodes")
        )
        mock_get_topology.return_value = "topology el"
        mock_get_resources.return_value = "resources_el"
        lib_env = create_lib_env()

        lib.verify(lib_env)

        mock_verify.assert_called_once_with(
            lib_env.report_processor,
            "topology el",
            "resources_el",
            "nodes"
        )
        mock_status_xml.assert_called_once_with("mocked cmd_runner")
        mock_status.assert_called_once_with("mock get_cluster_status_xml")
        mock_get_topology.assert_called_once_with("mocked cib")
        mock_get_resources.assert_called_once_with("mocked cib")
        mock_push_cib.assert_not_called()

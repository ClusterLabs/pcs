import logging
from functools import partial
from unittest import (
    TestCase,
    mock,
)

from pcs.common.fencing_topology import (
    TARGET_TYPE_ATTRIBUTE,
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
)
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import fencing_topology as lib
from pcs.lib.env import LibraryEnvironment

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import MockLibraryReportProcessor
from pcs_test.tools.misc import create_patcher

create_lib_env = partial(
    LibraryEnvironment,
    mock.MagicMock(logging.Logger),
    MockLibraryReportProcessor(),
)
patch_env = partial(mock.patch.object, LibraryEnvironment)
patch_command = create_patcher("pcs.lib.commands.fencing_topology")


@patch_command("cib_fencing_topology.add_level")
@patch_command("get_resources")
@patch_command("get_fencing_topology")
@patch_env("push_cib")
@patch_command("ClusterState")
@patch_env("get_cluster_state")
@patch_env("get_cib")
class AddLevel(TestCase):
    def prepare_mocks(
        self,
        mock_get_cib,
        mock_status_dom,
        mock_status,
        mock_get_topology,
        mock_get_resources,
    ):
        # pylint: disable=no-self-use
        mock_get_cib.return_value = "mocked cib"
        mock_status_dom.return_value = "mock get_cluster_status_dom"
        mock_status.return_value = mock.MagicMock(
            node_section=mock.MagicMock(nodes="nodes")
        )
        mock_get_topology.return_value = "topology el"
        mock_get_resources.return_value = "resources_el"

    def assert_mocks(
        self,
        mock_status_dom,
        mock_status,
        mock_get_topology,
        mock_get_resources,
        mock_push_cib,
    ):
        # pylint: disable=no-self-use
        mock_status_dom.assert_called_once_with()
        mock_status.assert_called_once_with("mock get_cluster_status_dom")
        mock_get_topology.assert_called_once_with("mocked cib")
        mock_get_resources.assert_called_once_with("mocked cib")
        mock_push_cib.assert_called_once_with()

    def test_success(
        self,
        mock_get_cib,
        mock_status_dom,
        mock_status,
        mock_push_cib,
        mock_get_topology,
        mock_get_resources,
        mock_add_level,
    ):
        self.prepare_mocks(
            mock_get_cib,
            mock_status_dom,
            mock_status,
            mock_get_topology,
            mock_get_resources,
        )
        lib_env = create_lib_env()

        lib.add_level(
            lib_env,
            "level",
            "target type",
            "target value",
            "devices",
            "force device",
            "force node",
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
            "force node",
        )
        mock_get_cib.assert_called_once_with()
        self.assert_mocks(
            mock_status_dom,
            mock_status,
            mock_get_topology,
            mock_get_resources,
            mock_push_cib,
        )

    def test_target_attribute_updates_cib(
        self,
        mock_get_cib,
        mock_status_dom,
        mock_status,
        mock_push_cib,
        mock_get_topology,
        mock_get_resources,
        mock_add_level,
    ):
        self.prepare_mocks(
            mock_get_cib,
            mock_status_dom,
            mock_status,
            mock_get_topology,
            mock_get_resources,
        )
        lib_env = create_lib_env()

        lib.add_level(
            lib_env,
            "level",
            TARGET_TYPE_ATTRIBUTE,
            "target value",
            "devices",
            "force device",
            "force node",
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
            "force node",
        )
        mock_get_cib.assert_called_once_with()
        self.assert_mocks(
            mock_status_dom,
            mock_status,
            mock_get_topology,
            mock_get_resources,
            mock_push_cib,
        )

    def test_target_regexp_updates_cib(
        self,
        mock_get_cib,
        mock_status_dom,
        mock_status,
        mock_push_cib,
        mock_get_topology,
        mock_get_resources,
        mock_add_level,
    ):
        self.prepare_mocks(
            mock_get_cib,
            mock_status_dom,
            mock_status,
            mock_get_topology,
            mock_get_resources,
        )
        lib_env = create_lib_env()

        lib.add_level(
            lib_env,
            "level",
            TARGET_TYPE_REGEXP,
            "target value",
            "devices",
            "force device",
            "force node",
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
            "force node",
        )
        mock_get_cib.assert_called_once_with()
        self.assert_mocks(
            mock_status_dom,
            mock_status,
            mock_get_topology,
            mock_get_resources,
            mock_push_cib,
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

        self.assertEqual("exported config", lib.get_config(lib_env))

        mock_export.assert_called_once_with("topology el")
        mock_get_topology.assert_called_once_with("mocked cib")
        mock_push_cib.assert_not_called()


@patch_command("cib_fencing_topology.remove_all_levels")
@patch_command("get_fencing_topology")
@patch_env("push_cib")
@patch_env("get_cib", lambda self: "mocked cib")
class RemoveAllLevels(TestCase):
    def test_success(self, mock_push_cib, mock_get_topology, mock_remove):
        # pylint: disable=no-self-use
        mock_get_topology.return_value = "topology el"
        lib_env = create_lib_env()

        lib.remove_all_levels(lib_env)

        mock_remove.assert_called_once_with("topology el")
        mock_get_topology.assert_called_once_with("mocked cib")
        mock_push_cib.assert_called_once_with()


class RemoveLevelsByParams(TestCase):
    fixture_cib_node = """
        <fencing-topology>
            <fencing-level
                id="fl1" index="1" devices="dev1,dev2" target="node1"
            />
            <fencing-level
                id="flX" index="2" devices="devX,devY" target="node1"
            />
        </fencing-topology>
    """

    fixture_cib_attr = """
        <fencing-topology>
            <fencing-level
                id="fl1" index="1" devices="dev1,dev2"
                target-attribute="fencing" target-value="improved"
            />
            <fencing-level
                id="flX" index="2" devices="devX,devY" target="node1"
            />
        </fencing-topology>
    """

    fixture_cib_regexp = """
        <fencing-topology>
            <fencing-level
                id="fl1" index="1" devices="dev1,dev2" target-pattern="node\\d+"
            />
            <fencing-level
                id="flX" index="2" devices="devX,devY" target="node1"
            />
        </fencing-topology>
    """

    fixture_cib_other_level = """
        <fencing-topology>
            <fencing-level
                id="flX" index="2" devices="devX,devY" target="node1"
            />
        </fencing-topology>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_devices_target_attr_present(self):
        self.config.runner.cib.load(fencing_topology=self.fixture_cib_attr)
        self.config.env.push_cib(fencing_topology=self.fixture_cib_other_level)

        lib.remove_levels_by_params(
            self.env_assist.get_env(),
            level="1",
            target_type=TARGET_TYPE_ATTRIBUTE,
            target_value=("fencing", "improved"),
            devices=["dev1", "dev2"],
        )

    def test_devices_target_attr_missing(self):
        self.config.runner.cib.load(fencing_topology=self.fixture_cib_attr)

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_levels_by_params(
                self.env_assist.get_env(),
                level="2",
                target_type=TARGET_TYPE_ATTRIBUTE,
                target_value=("fencing", "improved"),
                devices=["dev1", "dev2"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST,
                    level="2",
                    target_type=TARGET_TYPE_ATTRIBUTE,
                    target_value=("fencing", "improved"),
                    devices=["dev1", "dev2"],
                ),
            ]
        )

    def test_devices_target_regexp_present(self):
        self.config.runner.cib.load(fencing_topology=self.fixture_cib_regexp)
        self.config.env.push_cib(fencing_topology=self.fixture_cib_other_level)

        lib.remove_levels_by_params(
            self.env_assist.get_env(),
            level="1",
            target_type=TARGET_TYPE_REGEXP,
            target_value="node\\d+",
            devices=["dev1", "dev2"],
        )

    def test_devices_target_regexp_missing(self):
        self.config.runner.cib.load(fencing_topology=self.fixture_cib_regexp)

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_levels_by_params(
                self.env_assist.get_env(),
                level="2",
                target_type=TARGET_TYPE_REGEXP,
                target_value="node\\d+",
                devices=["dev1", "dev2"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST,
                    level="2",
                    target_type=TARGET_TYPE_REGEXP,
                    target_value="node\\d+",
                    devices=["dev1", "dev2"],
                ),
            ]
        )

    def test_devices_target_node_present(self):
        self.config.runner.cib.load(fencing_topology=self.fixture_cib_node)
        self.config.env.push_cib(fencing_topology=self.fixture_cib_other_level)

        lib.remove_levels_by_params(
            self.env_assist.get_env(),
            level="1",
            target_type=TARGET_TYPE_NODE,
            target_value="node1",
            devices=["dev1", "dev2"],
        )

    def test_devices_target_node_missing_success(self):
        self.config.runner.cib.load(fencing_topology=self.fixture_cib_node)
        self.config.env.push_cib(fencing_topology=self.fixture_cib_other_level)

        lib.remove_levels_by_params(
            self.env_assist.get_env(),
            level="1",
            target_type=TARGET_TYPE_NODE,
            target_value="dev1",
            devices=["dev2"],
            target_may_be_a_device=True,
        )

    def test_devices_target_node_missing_not_found(self):
        self.config.runner.cib.load(fencing_topology=self.fixture_cib_node)

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_levels_by_params(
                self.env_assist.get_env(),
                level="2",
                target_type=TARGET_TYPE_NODE,
                target_value="dev1",
                devices=["dev2"],
                target_may_be_a_device=True,
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST,
                    level="2",
                    target_type=TARGET_TYPE_NODE,
                    target_value="dev1",
                    devices=["dev2"],
                ),
                fixture.error(
                    report_codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST,
                    level="2",
                    target_type=None,
                    target_value=None,
                    devices=["dev1", "dev2"],
                ),
            ]
        )

    def test_devices_target_node_missing_guessing_disabled(self):
        self.config.runner.cib.load(fencing_topology=self.fixture_cib_node)

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_levels_by_params(
                self.env_assist.get_env(),
                level="1",
                target_type=TARGET_TYPE_NODE,
                target_value="dev1",
                devices=["dev2"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST,
                    level="1",
                    target_type=TARGET_TYPE_NODE,
                    target_value="dev1",
                    devices=["dev2"],
                ),
            ]
        )


@patch_command("cib_fencing_topology.verify")
@patch_command("get_resources")
@patch_command("get_fencing_topology")
@patch_env("push_cib")
@patch_command("ClusterState")
@patch_env("get_cluster_state")
@patch_env("get_cib", lambda self: "mocked cib")
class Verify(TestCase):
    def test_success(
        self,
        mock_status_dom,
        mock_status,
        mock_push_cib,
        mock_get_topology,
        mock_get_resources,
        mock_verify,
    ):
        # pylint: disable=no-self-use
        mock_status_dom.return_value = "mock get_cluster_status_dom"
        mock_status.return_value = mock.MagicMock(
            node_section=mock.MagicMock(nodes="nodes")
        )
        mock_get_topology.return_value = "topology el"
        mock_get_resources.return_value = "resources_el"
        lib_env = create_lib_env()

        lib.verify(lib_env)

        mock_verify.assert_called_once_with(
            "topology el", "resources_el", "nodes"
        )
        mock_status_dom.assert_called_once_with()
        mock_status.assert_called_once_with("mock get_cluster_status_dom")
        mock_get_topology.assert_called_once_with("mocked cib")
        mock_get_resources.assert_called_once_with("mocked cib")
        mock_push_cib.assert_not_called()

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging

from pcs.common import report_codes
from pcs.lib.commands import resource
import pcs.lib.commands.test.resource.fixture as fixture
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.integration_lib import Runner
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.pcs_unittest import TestCase, mock


runner = Runner()

fixture_primitive_cib_managed = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
        </primitive>
    </resources>
"""
fixture_primitive_cib_unmanaged = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        </primitive>
    </resources>
"""

fixture_primitive_cib_managed_op_enabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Stateful">
            <operations>
                <op id="A-start" name="start" />
                <op id="A-stop" name="stop" />
                <op id="A-monitor-m" name="monitor" role="Master" />
                <op id="A-monitor-s" name="monitor" role="Slave" />
            </operations>
        </primitive>
    </resources>
"""
fixture_primitive_cib_managed_op_disabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Stateful">
            <operations>
                <op id="A-start" name="start" />
                <op id="A-stop" name="stop" />
                <op id="A-monitor-m" name="monitor" role="Master"
                    enabled="false" />
                <op id="A-monitor-s" name="monitor" role="Slave"
                    enabled="false" />
            </operations>
        </primitive>
    </resources>
"""
fixture_primitive_cib_unmanaged_op_enabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Stateful">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <operations>
                <op id="A-start" name="start" />
                <op id="A-stop" name="stop" />
                <op id="A-monitor-m" name="monitor" role="Master" />
                <op id="A-monitor-s" name="monitor" role="Slave" />
            </operations>
        </primitive>
    </resources>
"""
fixture_primitive_cib_unmanaged_op_disabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Stateful">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <operations>
                <op id="A-start" name="start" />
                <op id="A-stop" name="stop" />
                <op id="A-monitor-m" name="monitor" role="Master"
                    enabled="false" />
                <op id="A-monitor-s" name="monitor" role="Slave"
                    enabled="false" />
            </operations>
        </primitive>
    </resources>
"""

fixture_group_cib_managed = """
    <resources>
        <group id="A">
            <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </group>
    </resources>
"""
fixture_group_cib_unmanaged_resource = """
    <resources>
        <group id="A">
            <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A1-meta_attributes">
                    <nvpair id="A1-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
            <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </group>
    </resources>
"""
fixture_group_cib_unmanaged_resource_and_group = """
    <resources>
        <group id="A">
            <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A1-meta_attributes">
                    <nvpair id="A1-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
            <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        </group>
    </resources>
"""
fixture_group_cib_unmanaged_all_resources = """
    <resources>
        <group id="A">
            <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A1-meta_attributes">
                    <nvpair id="A1-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
            <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A2-meta_attributes">
                    <nvpair id="A2-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </group>
    </resources>
"""

fixture_clone_cib_managed = """
    <resources>
        <clone id="A-clone">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </clone>
    </resources>
"""
fixture_clone_cib_unmanaged_clone = """
    <resources>
        <clone id="A-clone">
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </clone>
    </resources>
"""
fixture_clone_cib_unmanaged_primitive = """
    <resources>
        <clone id="A-clone">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </clone>
    </resources>
"""
fixture_clone_cib_unmanaged_both = """
    <resources>
        <clone id="A-clone">
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </clone>
    </resources>
"""

fixture_master_cib_managed = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_unmanaged_master = """
    <resources>
        <master id="A-master">
            <meta_attributes id="A-master-meta_attributes">
                <nvpair id="A-master-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_unmanaged_both = """
    <resources>
        <master id="A-master">
            <meta_attributes id="A-master-meta_attributes">
                <nvpair id="A-master-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </master>
    </resources>
"""

fixture_clone_group_cib_managed = """
    <resources>
        <clone id="A-clone">
            <group id="A">
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                </primitive>
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_cib_unmanaged_primitive = """
    <resources>
        <clone id="A-clone">
            <group id="A">
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A1-meta_attributes">
                        <nvpair id="A1-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                </primitive>
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_cib_unmanaged_all_primitives = """
    <resources>
        <clone id="A-clone">
            <group id="A">
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A1-meta_attributes">
                        <nvpair id="A1-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A2-meta_attributes">
                        <nvpair id="A2-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_cib_unmanaged_clone = """
    <resources>
        <clone id="A-clone">
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <group id="A">
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                </primitive>
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_cib_unmanaged_everything = """
    <resources>
        <clone id="A-clone">
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <group id="A">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A1-meta_attributes">
                        <nvpair id="A1-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A2-meta_attributes">
                        <nvpair id="A2-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
            </group>
        </clone>
    </resources>
"""

def fixture_calls_cib(cib_pre, cib_post):
    return (
        fixture.call_cib_load(fixture.cib_resources(cib_pre))
        +
        fixture.call_cib_push(fixture.cib_resources(cib_post))
    )

def fixture_report_no_monitors(resource):
    return (
        severities.WARNING,
        report_codes.RESOURCE_MANAGED_NO_MONITOR_ENABLED,
        {
            "resource_id": resource,
        },
        None
    )


class CommonResourceTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patcher = mock.patch.object(
            LibraryEnvironment,
            "cmd_runner",
            lambda self: runner
        )
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    def setUp(self):
        self.env = LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor()
        )

    def assert_command_effect(self, cib_pre, cmd, cib_post, reports=None):
        runner.set_runs(
            fixture_calls_cib(cib_pre, cib_post)
        )
        cmd()
        self.env.report_processor.assert_reports(reports if reports else [])
        runner.assert_everything_launched()


class UnmanagePrimitive(CommonResourceTest):
    def test_nonexistent_resource(self):
        runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(fixture_primitive_cib_managed)
            )
        )

        assert_raise_library_error(
            lambda: resource.unmanage(self.env, ["B"]),
            fixture.report_not_found("B", "resources")
        )
        runner.assert_everything_launched()

    def test_primitive(self):
        self.assert_command_effect(
            fixture_primitive_cib_managed,
            lambda: resource.unmanage(self.env, ["A"]),
            fixture_primitive_cib_unmanaged
        )

    def test_primitive_unmanaged(self):
        self.assert_command_effect(
            fixture_primitive_cib_unmanaged,
            lambda: resource.unmanage(self.env, ["A"]),
            fixture_primitive_cib_unmanaged
        )


class ManagePrimitive(CommonResourceTest):
    def test_nonexistent_resource(self):
        runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(fixture_primitive_cib_unmanaged)
            )
        )

        assert_raise_library_error(
            lambda: resource.manage(self.env, ["B"]),
            fixture.report_not_found("B", "resources")
        )
        runner.assert_everything_launched()

    def test_primitive(self):
        self.assert_command_effect(
            fixture_primitive_cib_unmanaged,
            lambda: resource.manage(self.env, ["A"]),
            fixture_primitive_cib_managed
        )

    def test_primitive_managed(self):
        self.assert_command_effect(
            fixture_primitive_cib_managed,
            lambda: resource.manage(self.env, ["A"]),
            fixture_primitive_cib_managed
        )


class UnmanageGroup(CommonResourceTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_group_cib_managed,
            lambda: resource.unmanage(self.env, ["A1"]),
            fixture_group_cib_unmanaged_resource
        )

    def test_group(self):
        self.assert_command_effect(
            fixture_group_cib_managed,
            lambda: resource.unmanage(self.env, ["A"]),
            fixture_group_cib_unmanaged_all_resources
        )


class ManageGroup(CommonResourceTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_group_cib_unmanaged_all_resources,
            lambda: resource.manage(self.env, ["A2"]),
            fixture_group_cib_unmanaged_resource
        )

    def test_primitive_unmanaged_group(self):
        self.assert_command_effect(
            fixture_group_cib_unmanaged_resource_and_group,
            lambda: resource.manage(self.env, ["A1"]),
            fixture_group_cib_managed
        )

    def test_group(self):
        self.assert_command_effect(
            fixture_group_cib_unmanaged_all_resources,
            lambda: resource.manage(self.env, ["A"]),
            fixture_group_cib_managed
        )

    def test_group_unmanaged_group(self):
        self.assert_command_effect(
            fixture_group_cib_unmanaged_resource_and_group,
            lambda: resource.manage(self.env, ["A"]),
            fixture_group_cib_managed
        )


class UnmanageClone(CommonResourceTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_clone_cib_managed,
            lambda: resource.unmanage(self.env, ["A"]),
            fixture_clone_cib_unmanaged_clone
        )

    def test_clone(self):
        self.assert_command_effect(
            fixture_clone_cib_managed,
            lambda: resource.unmanage(self.env, ["A-clone"]),
            fixture_clone_cib_unmanaged_clone
        )


class ManageClone(CommonResourceTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_clone_cib_unmanaged_clone,
            lambda: resource.manage(self.env, ["A"]),
            fixture_clone_cib_managed
        )

    def test_primitive_unmanaged_primitive(self):
        self.assert_command_effect(
            fixture_clone_cib_unmanaged_primitive,
            lambda: resource.manage(self.env, ["A"]),
            fixture_clone_cib_managed
        )

    def test_primitive_unmanaged_both(self):
        self.assert_command_effect(
            fixture_clone_cib_unmanaged_both,
            lambda: resource.manage(self.env, ["A"]),
            fixture_clone_cib_managed
        )

    def test_clone(self):
        self.assert_command_effect(
            fixture_clone_cib_unmanaged_clone,
            lambda: resource.manage(self.env, ["A-clone"]),
            fixture_clone_cib_managed
        )

    def test_clone_unmanaged_primitive(self):
        self.assert_command_effect(
            fixture_clone_cib_unmanaged_primitive,
            lambda: resource.manage(self.env, ["A-clone"]),
            fixture_clone_cib_managed
        )

    def test_clone_unmanaged_both(self):
        self.assert_command_effect(
            fixture_clone_cib_unmanaged_both,
            lambda: resource.manage(self.env, ["A-clone"]),
            fixture_clone_cib_managed
        )


class UnmanageMaster(CommonResourceTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_master_cib_managed,
            lambda: resource.unmanage(self.env, ["A"]),
            fixture_master_cib_unmanaged_master
        )

    def test_master(self):
        self.assert_command_effect(
            fixture_master_cib_managed,
            lambda: resource.unmanage(self.env, ["A-master"]),
            fixture_master_cib_unmanaged_master
        )


class ManageMaster(CommonResourceTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_master_cib_unmanaged_master,
            lambda: resource.manage(self.env, ["A"]),
            fixture_master_cib_managed
        )

    def test_primitive_unmanaged_both(self):
        self.assert_command_effect(
            fixture_master_cib_unmanaged_both,
            lambda: resource.manage(self.env, ["A"]),
            fixture_master_cib_managed
        )

    def test_master(self):
        self.assert_command_effect(
            fixture_master_cib_unmanaged_master,
            lambda: resource.manage(self.env, ["A-master"]),
            fixture_master_cib_managed
        )

    def test_master_unmanaged_both(self):
        self.assert_command_effect(
            fixture_master_cib_unmanaged_both,
            lambda: resource.manage(self.env, ["A-master"]),
            fixture_master_cib_managed
        )


class UnmanageClonedGroup(CommonResourceTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_clone_group_cib_managed,
            lambda: resource.unmanage(self.env, ["A1"]),
            fixture_clone_group_cib_unmanaged_primitive
        )

    def test_group(self):
        self.assert_command_effect(
            fixture_clone_group_cib_managed,
            lambda: resource.unmanage(self.env, ["A"]),
            fixture_clone_group_cib_unmanaged_all_primitives
        )

    def test_clone(self):
        self.assert_command_effect(
            fixture_clone_group_cib_managed,
            lambda: resource.unmanage(self.env, ["A-clone"]),
            fixture_clone_group_cib_unmanaged_clone
        )


class ManageClonedGroup(CommonResourceTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_clone_group_cib_unmanaged_primitive,
            lambda: resource.manage(self.env, ["A1"]),
            fixture_clone_group_cib_managed
        )

    def test_primitive_unmanaged_all(self):
        self.assert_command_effect(
            fixture_clone_group_cib_unmanaged_everything,
            lambda: resource.manage(self.env, ["A2"]),
            fixture_clone_group_cib_unmanaged_primitive
        )

    def test_group(self):
        self.assert_command_effect(
            fixture_clone_group_cib_unmanaged_all_primitives,
            lambda: resource.manage(self.env, ["A"]),
            fixture_clone_group_cib_managed
        )

    def test_group_unmanaged_all(self):
        self.assert_command_effect(
            fixture_clone_group_cib_unmanaged_everything,
            lambda: resource.manage(self.env, ["A"]),
            fixture_clone_group_cib_managed
        )

    def test_clone(self):
        self.assert_command_effect(
            fixture_clone_group_cib_unmanaged_clone,
            lambda: resource.manage(self.env, ["A-clone"]),
            fixture_clone_group_cib_managed
        )

    def test_clone_unmanaged_all(self):
        self.assert_command_effect(
            fixture_clone_group_cib_unmanaged_everything,
            lambda: resource.manage(self.env, ["A-clone"]),
            fixture_clone_group_cib_managed
        )


class MoreResources(CommonResourceTest):
    fixture_cib_managed = """
        <resources>
            <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
            </primitive>
        </resources>
    """
    fixture_cib_unmanaged = """
        <resources>
            <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                <meta_attributes id="B-meta_attributes">
                    <nvpair id="B-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                <meta_attributes id="C-meta_attributes">
                    <nvpair id="C-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </resources>
    """

    def test_success_unmanage(self):
        fixture_cib_unmanaged = """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                </primitive>
                <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                    <meta_attributes id="C-meta_attributes">
                        <nvpair id="C-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
            </resources>
        """
        self.assert_command_effect(
            self.fixture_cib_managed,
            lambda: resource.unmanage(self.env, ["A", "C"]),
            fixture_cib_unmanaged
        )

    def test_success_manage(self):
        fixture_cib_managed = """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                </primitive>
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                    <meta_attributes id="B-meta_attributes">
                        <nvpair id="B-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                </primitive>
            </resources>
        """
        self.assert_command_effect(
            self.fixture_cib_unmanaged,
            lambda: resource.manage(self.env, ["A", "C"]),
            fixture_cib_managed
        )

    def test_bad_resource_unmanage(self):
        runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(self.fixture_cib_managed)
            )
        )

        assert_raise_library_error(
            lambda: resource.unmanage(self.env, ["B", "X", "Y", "A"]),
            fixture.report_not_found("X", "resources"),
            fixture.report_not_found("Y", "resources"),
        )
        runner.assert_everything_launched()

    def test_bad_resource_enable(self):
        runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(self.fixture_cib_unmanaged)
            )
        )

        assert_raise_library_error(
            lambda: resource.manage(self.env, ["B", "X", "Y", "A"]),
            fixture.report_not_found("X", "resources"),
            fixture.report_not_found("Y", "resources"),
        )
        runner.assert_everything_launched()


class WithMonitor(CommonResourceTest):
    def test_unmanage_noop(self):
        self.assert_command_effect(
            fixture_primitive_cib_managed,
            lambda: resource.unmanage(self.env, ["A"], True),
            fixture_primitive_cib_unmanaged
        )

    def test_manage_noop(self):
        self.assert_command_effect(
            fixture_primitive_cib_unmanaged,
            lambda: resource.manage(self.env, ["A"], True),
            fixture_primitive_cib_managed
        )

    def test_unmanage(self):
        self.assert_command_effect(
            fixture_primitive_cib_managed_op_enabled,
            lambda: resource.unmanage(self.env, ["A"], True),
            fixture_primitive_cib_unmanaged_op_disabled
        )

    def test_manage(self):
        self.assert_command_effect(
            fixture_primitive_cib_unmanaged_op_disabled,
            lambda: resource.manage(self.env, ["A"], True),
            fixture_primitive_cib_managed_op_enabled
        )

    def test_unmanage_enabled_monitors(self):
        self.assert_command_effect(
            fixture_primitive_cib_managed_op_enabled,
            lambda: resource.unmanage(self.env, ["A"], False),
            fixture_primitive_cib_unmanaged_op_enabled
        )

    def test_manage_disabled_monitors(self):
        self.assert_command_effect(
            fixture_primitive_cib_unmanaged_op_disabled,
            lambda: resource.manage(self.env, ["A"], False),
            fixture_primitive_cib_managed_op_disabled,
            [
                fixture_report_no_monitors("A"),
            ]
        )

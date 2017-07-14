from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.common import report_codes
from pcs.lib.commands import resource
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.pcs_unittest import TestCase


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

fixture_clone_cib_managed_op_enabled = """
    <resources>
        <clone id="A-clone">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor"/>
                </operations>
            </primitive>
        </clone>
    </resources>
"""
fixture_clone_cib_unmanaged_primitive_op_disabled = """
    <resources>
        <clone id="A-clone">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor" enabled="false"/>
                </operations>
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
fixture_master_cib_unmanaged_primitive = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
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

fixture_master_cib_managed_op_enabled = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor"/>
                </operations>
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_unmanaged_primitive_op_disabled = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor" enabled="false"/>
                </operations>
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

fixture_clone_group_cib_managed_op_enabled = """
    <resources>
        <clone id="A-clone">
            <group id="A">
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <operations>
                        <op id="A1-start" name="start" />
                        <op id="A1-stop" name="stop" />
                        <op id="A1-monitor" name="monitor" />
                    </operations>
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <operations>
                        <op id="A2-start" name="start" />
                        <op id="A2-stop" name="stop" />
                        <op id="A2-monitor" name="monitor" />
                    </operations>
                </primitive>
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_cib_unmanaged_primitive_op_disabled = """
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
                    <operations>
                        <op id="A1-start" name="start" />
                        <op id="A1-stop" name="stop" />
                        <op id="A1-monitor" name="monitor" enabled="false" />
                    </operations>
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <operations>
                        <op id="A2-start" name="start" />
                        <op id="A2-stop" name="stop" />
                        <op id="A2-monitor" name="monitor" />
                    </operations>
                </primitive>
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_cib_unmanaged_all_primitives_op_disabled = """
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
                    <operations>
                        <op id="A1-start" name="start" />
                        <op id="A1-stop" name="stop" />
                        <op id="A1-monitor" name="monitor" enabled="false" />
                    </operations>
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A2-meta_attributes">
                        <nvpair id="A2-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                    <operations>
                        <op id="A2-start" name="start" />
                        <op id="A2-stop" name="stop" />
                        <op id="A2-monitor" name="monitor" enabled="false" />
                    </operations>
                </primitive>
            </group>
        </clone>
    </resources>
"""


fixture_bundle_empty_cib_managed = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
        </bundle>
    </resources>
"""
fixture_bundle_empty_cib_unmanaged_bundle = """
    <resources>
        <bundle id="A-bundle">
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <docker image="pcs:test" />
        </bundle>
    </resources>
"""

fixture_bundle_cib_managed = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_cib_unmanaged_bundle = """
    <resources>
        <bundle id="A-bundle">
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_cib_unmanaged_primitive = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_cib_unmanaged_both = """
    <resources>
        <bundle id="A-bundle">
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </bundle>
    </resources>
"""

fixture_bundle_cib_managed_op_enabled = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor"/>
                </operations>
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_cib_unmanaged_primitive_op_disabled = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor" enabled="false"/>
                </operations>
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_cib_unmanaged_both_op_disabled = """
    <resources>
        <bundle id="A-bundle">
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor" enabled="false"/>
                </operations>
            </primitive>
        </bundle>
    </resources>
"""

def fixture_report_no_monitors(resource):
    return (
        severities.WARNING,
        report_codes.RESOURCE_MANAGED_NO_MONITOR_ENABLED,
        {
            "resource_id": resource,
        },
        None
    )

class UnmanagePrimitiveNew(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_nonexistent_resource(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_managed)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.unmanage(self.env_assist.get_env(), ["B"]),
            [
                fixture.report_not_found("B", "resources")
            ],
            expected_in_processor=False
        )

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_managed)
            .cib.push(resources=fixture_primitive_cib_unmanaged)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_unmanaged)
            .cib.push(resources=fixture_primitive_cib_unmanaged)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])


class ManagePrimitive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_nonexistent_resource(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_unmanaged)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.manage(self.env_assist.get_env(), ["B"]),
            [
                fixture.report_not_found("B", "resources")
            ],
            expected_in_processor=False
        )

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_unmanaged)
            .cib.push(resources=fixture_primitive_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_managed(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_managed)
            .cib.push(resources=fixture_primitive_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])


class UnmanageGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_managed)
            .cib.push(resources=fixture_group_cib_unmanaged_resource)
        )
        resource.unmanage(self.env_assist.get_env(), ["A1"])

    def test_group(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_managed)
            .cib.push(resources=fixture_group_cib_unmanaged_all_resources)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])


class ManageGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_unmanaged_all_resources)
            .cib.push(resources=fixture_group_cib_unmanaged_resource)
        )
        resource.manage(self.env_assist.get_env(), ["A2"])

    def test_primitive_unmanaged_group(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_unmanaged_resource_and_group)
            .cib.push(resources=fixture_group_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A1"])

    def test_group(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_unmanaged_all_resources)
            .cib.push(resources=fixture_group_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_group_unmanaged_group(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_unmanaged_resource_and_group)
            .cib.push(resources=fixture_group_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])


class UnmanageClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_managed)
            .cib.push(resources=fixture_clone_cib_unmanaged_primitive)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_managed)
            .cib.push(resources=fixture_clone_cib_unmanaged_primitive)
        )
        resource.unmanage(self.env_assist.get_env(), ["A-clone"])


class ManageClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_unmanaged_clone)
            .cib.push(resources=fixture_clone_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_unmanaged_primitive)
            .cib.push(resources=fixture_clone_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_both(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_unmanaged_both)
            .cib.push(resources=fixture_clone_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_unmanaged_clone)
            .cib.push(resources=fixture_clone_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])

    def test_clone_unmanaged_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_unmanaged_primitive)
            .cib.push(resources=fixture_clone_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])

    def test_clone_unmanaged_both(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_unmanaged_both)
            .cib.push(resources=fixture_clone_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])


class UnmanageMaster(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_managed)
            .cib.push(resources=fixture_master_cib_unmanaged_primitive)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_master(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_managed)
            .cib.push(resources=fixture_master_cib_unmanaged_primitive)
        )
        resource.unmanage(self.env_assist.get_env(), ["A-master"])


class ManageMaster(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_unmanaged_primitive)
            .cib.push(resources=fixture_master_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_master(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_unmanaged_master)
            .cib.push(resources=fixture_master_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_both(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_unmanaged_both)
            .cib.push(resources=fixture_master_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_master(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_unmanaged_master)
            .cib.push(resources=fixture_master_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-master"])

    def test_master_unmanaged_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_unmanaged_primitive)
            .cib.push(resources=fixture_master_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-master"])

    def test_master_unmanaged_both(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_unmanaged_both)
            .cib.push(resources=fixture_master_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-master"])


class UnmanageClonedGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_managed)
            .cib.push(resources=fixture_clone_group_cib_unmanaged_primitive)
        )
        resource.unmanage(self.env_assist.get_env(), ["A1"])

    def test_group(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_managed)
            .cib.push(resources=fixture_clone_group_cib_unmanaged_all_primitives)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_managed)
            .cib.push(resources=fixture_clone_group_cib_unmanaged_all_primitives)
        )
        resource.unmanage(self.env_assist.get_env(), ["A-clone"])


class ManageClonedGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_unmanaged_primitive)
            .cib.push(resources=fixture_clone_group_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A1"])

    def test_primitive_unmanaged_all(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_unmanaged_everything)
            .cib.push(resources=fixture_clone_group_cib_unmanaged_primitive)
        )
        resource.manage(self.env_assist.get_env(), ["A2"])

    def test_group(self):
        (self.config.runner
            .cib.load(
                resources=fixture_clone_group_cib_unmanaged_all_primitives
            )
            .cib.push(resources=fixture_clone_group_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_group_unmanaged_all(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_unmanaged_everything)
            .cib.push(resources=fixture_clone_group_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_unmanaged_clone)
            .cib.push(resources=fixture_clone_group_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])

    def test_clone_unmanaged_all(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_unmanaged_everything)
            .cib.push(resources=fixture_clone_group_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])


class UnmanageBundle(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_managed)
            .cib.push(resources=fixture_bundle_cib_unmanaged_primitive)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_bundle(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_managed)
            .cib.push(resources=fixture_bundle_cib_unmanaged_both)
        )
        resource.unmanage(self.env_assist.get_env(), ["A-bundle"])

    def test_bundle_empty(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_empty_cib_managed)
            .cib.push(resources=fixture_bundle_empty_cib_unmanaged_bundle)
        )
        resource.unmanage(self.env_assist.get_env(), ["A-bundle"])


class ManageBundle(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_unmanaged_primitive)
            .cib.push(resources=fixture_bundle_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_bundle(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_unmanaged_bundle)
            .cib.push(resources=fixture_bundle_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_both(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_unmanaged_both)
            .cib.push(resources=fixture_bundle_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_bundle(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_unmanaged_bundle)
            .cib.push(resources=fixture_bundle_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-bundle"])

    def test_bundle_unmanaged_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_unmanaged_primitive)
            .cib.push(resources=fixture_bundle_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-bundle"])

    def test_bundle_unmanaged_both(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_unmanaged_both)
            .cib.push(resources=fixture_bundle_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-bundle"])

    def test_bundle_empty(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_empty_cib_unmanaged_bundle)
            .cib.push(resources=fixture_bundle_empty_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A-bundle"])


class MoreResources(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

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
        (self.config.runner
            .cib.load(resources=self.fixture_cib_managed)
            .cib.push(resources=fixture_cib_unmanaged)
        )
        resource.unmanage(self.env_assist.get_env(), ["A", "C"])

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
        (self.config.runner
            .cib.load(resources=self.fixture_cib_unmanaged)
            .cib.push(resources=fixture_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A", "C"])

    def test_bad_resource_unmanage(self):
        (self.config.runner
            .cib.load(resources=self.fixture_cib_managed)
        )

        self.env_assist.assert_raise_library_error(
            lambda:
            resource.unmanage(self.env_assist.get_env(), ["B", "X", "Y", "A"]),
            [
                fixture.report_not_found("X", "resources"),
                fixture.report_not_found("Y", "resources"),
            ],
            expected_in_processor=False
        )

    def test_bad_resource_enable(self):
        (self.config.runner
            .cib.load(resources=self.fixture_cib_unmanaged)
        )

        self.env_assist.assert_raise_library_error(
            lambda:
            resource.manage(self.env_assist.get_env(), ["B", "X", "Y", "A"]),
            [
                fixture.report_not_found("X", "resources"),
                fixture.report_not_found("Y", "resources"),
            ],
            expected_in_processor=False
        )


class WithMonitor(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_unmanage_noop(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_managed)
            .cib.push(resources=fixture_primitive_cib_unmanaged)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_manage_noop(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_unmanaged)
            .cib.push(resources=fixture_primitive_cib_managed)
        )
        resource.manage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_managed_op_enabled)
            .cib.push(resources=fixture_primitive_cib_unmanaged_op_disabled)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_manage(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_unmanaged_op_disabled)
            .cib.push(resources=fixture_primitive_cib_managed_op_enabled)
        )
        resource.manage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_enabled_monitors(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_managed_op_enabled)
            .cib.push(resources=fixture_primitive_cib_unmanaged_op_enabled)
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], False)

    def test_manage_disabled_monitors(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_unmanaged_op_disabled)
            .cib.push(resources=fixture_primitive_cib_managed_op_disabled)
        )
        resource.manage(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([
            fixture_report_no_monitors("A"),
        ])

    def test_unmanage_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_managed_op_enabled)
            .cib.push(
                resources=fixture_clone_cib_unmanaged_primitive_op_disabled
            )
        )
        resource.unmanage(self.env_assist.get_env(), ["A-clone"], True)

    def test_unmanage_in_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_managed_op_enabled)
            .cib.push(
                resources=fixture_clone_cib_unmanaged_primitive_op_disabled
            )
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_master(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_managed_op_enabled)
            .cib.push(
                resources=fixture_master_cib_unmanaged_primitive_op_disabled
            )
        )
        resource.unmanage(self.env_assist.get_env(), ["A-master"], True)

    def test_unmanage_in_master(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_managed_op_enabled)
            .cib.push(
                resources=fixture_master_cib_unmanaged_primitive_op_disabled
            )
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_clone_with_group(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_managed_op_enabled)
            .cib.push(resources=
                fixture_clone_group_cib_unmanaged_all_primitives_op_disabled
            )
        )
        resource.unmanage(self.env_assist.get_env(), ["A-clone"], True)

    def test_unmanage_group_in_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_managed_op_enabled)
            .cib.push(resources=
                fixture_clone_group_cib_unmanaged_all_primitives_op_disabled
            )
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_in_cloned_group(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_managed_op_enabled)
            .cib.push(resources=
                fixture_clone_group_cib_unmanaged_primitive_op_disabled
            )
        )
        resource.unmanage(self.env_assist.get_env(), ["A1"], True)

    def test_unmanage_bundle(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_managed_op_enabled)
            .cib.push(resources=fixture_bundle_cib_unmanaged_both_op_disabled)
        )
        resource.unmanage(self.env_assist.get_env(), ["A-bundle"], True)

    def test_unmanage_in_bundle(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_managed_op_enabled)
            .cib.push(
                resources=fixture_bundle_cib_unmanaged_primitive_op_disabled
            )
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_bundle_empty(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_empty_cib_managed)
            .cib.push(resources=fixture_bundle_empty_cib_unmanaged_bundle)
        )
        resource.unmanage(self.env_assist.get_env(), ["A-bundle"], True)

from __future__ import (
    absolute_import,
    division,
    print_function,
)

from functools import partial

import pcs.lib.commands.test.resource.fixture as fixture
from pcs.common import report_codes
from pcs.lib.commands import resource
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.misc import (
    outdent,
    skip_unless_pacemaker_supports_bundle,
)
from pcs.test.tools.pcs_unittest import TestCase


TIMEOUT=10

get_env_tools = partial(
    get_env_tools,
    default_wait_timeout=10
)

fixture_primitive_cib_enabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
        </primitive>
    </resources>
"""
fixture_primitive_cib_disabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        </primitive>
    </resources>
"""
fixture_primitive_status_managed = """
    <resources>
        <resource id="A" managed="true" />
    </resources>
"""
fixture_primitive_status_unmanaged = """
    <resources>
        <resource id="A" managed="false" />
    </resources>
"""

fixture_two_primitives_cib_enabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
        </primitive>
        <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
        </primitive>
    </resources>
"""
fixture_two_primitives_cib_disabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        </primitive>
        <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
        </primitive>
    </resources>
"""
fixture_two_primitives_cib_disabled_both = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        </primitive>
        <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
            <meta_attributes id="B-meta_attributes">
                <nvpair id="B-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        </primitive>
    </resources>
"""
fixture_two_primitives_status_managed = """
    <resources>
        <resource id="A" managed="true" />
        <resource id="B" managed="true" />
    </resources>
"""

fixture_group_cib_enabled = """
    <resources>
        <group id="A">
            <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </group>
    </resources>
"""
fixture_group_cib_disabled_group = """
    <resources>
        <group id="A">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </group>
    </resources>
"""
fixture_group_cib_disabled_primitive = """
    <resources>
        <group id="A">
            <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A1-meta_attributes">
                    <nvpair id="A1-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
            <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </group>
    </resources>
"""
fixture_group_cib_disabled_both = """
    <resources>
        <group id="A">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A1-meta_attributes">
                    <nvpair id="A1-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
            <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </group>
    </resources>
"""
fixture_group_status_managed = """
    <resources>
        <group id="A" number_resources="2">
            <resource id="A1" managed="true" />
            <resource id="A2" managed="true" />
        </group>
    </resources>
"""
fixture_group_status_unmanaged = """
    <resources>
        <group id="A" number_resources="2">
            <resource id="A1" managed="false" />
            <resource id="A2" managed="false" />
        </group>
    </resources>
"""

fixture_clone_cib_enabled = """
    <resources>
        <clone id="A-clone">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </clone>
    </resources>
"""
fixture_clone_cib_disabled_clone = """
    <resources>
        <clone id="A-clone">
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </clone>
    </resources>
"""
fixture_clone_cib_disabled_primitive = """
    <resources>
        <clone id="A-clone">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
        </clone>
    </resources>
"""
fixture_clone_cib_disabled_both = """
    <resources>
        <clone id="A-clone">
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
        </clone>
    </resources>
"""
fixture_clone_status_managed = """
    <resources>
        <clone id="A-clone" managed="true" multi_state="false" unique="false">
            <resource id="A" managed="true" />
            <resource id="A" managed="true" />
        </clone>
    </resources>
"""
fixture_clone_status_unmanaged = """
    <resources>
        <clone id="A-clone" managed="false" multi_state="false" unique="false">
            <resource id="A" managed="false" />
            <resource id="A" managed="false" />
        </clone>
    </resources>
"""

fixture_master_cib_enabled = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_disabled_master = """
    <resources>
        <master id="A-master">
            <meta_attributes id="A-master-meta_attributes">
                <nvpair id="A-master-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_disabled_primitive = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_disabled_both = """
    <resources>
        <master id="A-master">
            <meta_attributes id="A-master-meta_attributes">
                <nvpair id="A-master-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
        </master>
    </resources>
"""
fixture_master_status_managed = """
    <resources>
        <clone id="A-master" managed="true" multi_state="true" unique="false">
            <resource id="A" managed="true" />
            <resource id="A" managed="true" />
        </clone>
    </resources>
"""
fixture_master_status_unmanaged = """
    <resources>
        <clone id="A-master" managed="false" multi_state="true" unique="false">
            <resource id="A" managed="false" />
            <resource id="A" managed="false" />
        </clone>
    </resources>
"""

fixture_clone_group_cib_enabled = """
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
fixture_clone_group_cib_disabled_clone = """
    <resources>
        <clone id="A-clone">
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
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
fixture_clone_group_cib_disabled_group = """
    <resources>
        <clone id="A-clone">
            <group id="A">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
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
fixture_clone_group_cib_disabled_primitive = """
    <resources>
        <clone id="A-clone">
            <group id="A">
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A1-meta_attributes">
                        <nvpair id="A1-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
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
fixture_clone_group_cib_disabled_clone_group = """
    <resources>
        <clone id="A-clone">
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <group id="A">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
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
fixture_clone_group_cib_disabled_all = """
    <resources>
        <clone id="A-clone">
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <group id="A">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A1-meta_attributes">
                        <nvpair id="A1-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
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
fixture_clone_group_status_managed = """
    <resources>
        <clone id="A-clone" managed="true" multi_state="false" unique="false">
            <group id="A:0" number_resources="2">
                <resource id="A1" managed="true" />
                <resource id="A2" managed="true" />
            </group>
            <group id="A:1" number_resources="2">
                <resource id="A1" managed="true" />
                <resource id="A2" managed="true" />
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_status_unmanaged = """
    <resources>
        <clone id="A-clone" managed="false" multi_state="false" unique="false">
            <group id="A:0" number_resources="2">
                <resource id="A1" managed="false" />
                <resource id="A2" managed="false" />
            </group>
            <group id="A:1" number_resources="2">
                <resource id="A1" managed="false" />
                <resource id="A2" managed="false" />
            </group>
        </clone>
    </resources>
"""

fixture_bundle_cib_enabled = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_cib_disabled_primitive = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_cib_disabled_bundle = """
    <resources>
        <bundle id="A-bundle">
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy" />
        </bundle>
    </resources>
"""
fixture_bundle_cib_disabled_both = """
    <resources>
        <bundle id="A-bundle">
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_status_managed = """
    <resources>
        <bundle id="A-bundle" type="docker" image="pcmktest:http"
            unique="false" managed="true" failed="false"
        >
            <replica id="0">
                <resource id="A" />
            </replica>
            <replica id="1">
                <resource id="A" />
            </replica>
        </bundle>
    </resources>
"""
fixture_bundle_status_unmanaged = """
    <resources>
        <bundle id="A-bundle" type="docker" image="pcmktest:http"
            unique="false" managed="false" failed="false"
        >
            <replica id="0">
                <resource id="A" managed="false" />
            </replica>
            <replica id="1">
                <resource id="A" managed="false" />
            </replica>
        </bundle>
    </resources>
"""

def fixture_report_unmanaged(resource):
    return (
        severities.WARNING,
        report_codes.RESOURCE_IS_UNMANAGED,
        {
            "resource_id": resource,
        },
        None
    )

class DisablePrimitive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_nonexistent_resource(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_enabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(self.env_assist.get_env(), ["B"], False),
            [
                fixture.report_not_found("B", "resources")
            ],
            expected_in_processor=False
        )

    def test_nonexistent_resource_in_status(self):
        (self.config.runner
            .cib.load(resources=fixture_two_primitives_cib_enabled)
            .pcmk.load_state(resources=fixture_primitive_status_managed)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(self.env_assist.get_env(), ["B"], False),
            [
                fixture.report_not_found("B")
            ],
        )

    def test_correct_resource(self):
        (self.config.runner
            .cib.load(resources=fixture_two_primitives_cib_enabled)
            .pcmk.load_state(resources=fixture_two_primitives_status_managed)
            .cib.push(resources=fixture_two_primitives_cib_disabled)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)

    def test_unmanaged(self):
        # The code doesn't care what causes the resource to be unmanaged
        # (cluster property, resource's meta-attribute or whatever). It only
        # checks the cluster state (crm_mon).
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_enabled)
            .pcmk.load_state(resources=fixture_primitive_status_unmanaged)
            .cib.push(resources=fixture_primitive_cib_disabled)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([fixture_report_unmanaged("A")])


class EnablePrimitive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_nonexistent_resource(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_disabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(self.env_assist.get_env(), ["B"], False),
            [
                fixture.report_not_found("B", "resources")
            ],
            expected_in_processor=False
        )

    def test_nonexistent_resource_in_status(self):
        (self.config.runner
            .cib.load(resources=fixture_two_primitives_cib_disabled)
            .pcmk.load_state(resources=fixture_primitive_status_managed)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(self.env_assist.get_env(), ["B"], False),
            [
                fixture.report_not_found("B")
            ]
        )

    def test_correct_resource(self):
        (self.config.runner
            .cib.load(resources=fixture_two_primitives_cib_disabled_both)
            .pcmk.load_state(resources=fixture_two_primitives_status_managed)
            .cib.push(resources=fixture_two_primitives_cib_disabled)
        )
        resource.enable(self.env_assist.get_env(), ["B"], False)

    def test_unmanaged(self):
        # The code doesn't care what causes the resource to be unmanaged
        # (cluster property, resource's meta-attribute or whatever). It only
        # checks the cluster state (crm_mon).
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_disabled)
            .pcmk.load_state(resources=fixture_primitive_status_unmanaged)
            .cib.push(resources=fixture_primitive_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([fixture_report_unmanaged("A")])


class MoreResources(TestCase):
    fixture_cib_enabled = """
        <resources>
            <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="D" provider="heartbeat" type="Dummy">
            </primitive>
        </resources>
    """
    fixture_cib_disabled = """
        <resources>
            <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                <meta_attributes id="B-meta_attributes">
                    <nvpair id="B-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                <meta_attributes id="C-meta_attributes">
                    <nvpair id="C-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="D" provider="heartbeat" type="Dummy">
                <meta_attributes id="D-meta_attributes">
                    <nvpair id="D-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
        </resources>
    """
    fixture_status = """
        <resources>
            <resource id="A" managed="true" />
            <resource id="B" managed="false" />
            <resource id="C" managed="true" />
            <resource id="D" managed="false" />
        </resources>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success_enable(self):
        fixture_enabled = """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                </primitive>
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                </primitive>
                <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                    <meta_attributes id="C-meta_attributes">
                        <nvpair id="C-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="D" provider="heartbeat" type="Dummy">
                </primitive>
            </resources>
        """
        (self.config.runner
            .cib.load(resources=self.fixture_cib_disabled)
            .pcmk.load_state(resources=self.fixture_status)
            .cib.push(resources=fixture_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A", "B", "D"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("B"),
            fixture_report_unmanaged("D"),
        ])

    def test_success_disable(self):
        fixture_disabled = """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                    <meta_attributes id="B-meta_attributes">
                        <nvpair id="B-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                </primitive>
                <primitive class="ocf" id="D" provider="heartbeat" type="Dummy">
                    <meta_attributes id="D-meta_attributes">
                        <nvpair id="D-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                </primitive>
            </resources>
        """
        (self.config.runner
            .cib.load(resources=self.fixture_cib_enabled)
            .pcmk.load_state(resources=self.fixture_status)
            .cib.push(resources=fixture_disabled)
        )
        resource.disable(self.env_assist.get_env(), ["A", "B", "D"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("B"),
            fixture_report_unmanaged("D"),
        ])

    def test_bad_resource_enable(self):
        (self.config.runner
            .cib.load(resources=self.fixture_cib_disabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(
                self.env_assist.get_env(),
                ["B", "X", "Y", "A"],
                wait=False
            ),
            [
                fixture.report_not_found("X", "resources"),
                fixture.report_not_found("Y", "resources"),
            ],
            expected_in_processor=False
        )

    def test_bad_resource_disable(self):
        (self.config.runner
            .cib.load(resources=self.fixture_cib_enabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(
                self.env_assist.get_env(),
                ["B", "X", "Y", "A"],
                wait=False
            ),
            [
                fixture.report_not_found("X", "resources"),
                fixture.report_not_found("Y", "resources"),
            ],
            expected_in_processor=False
        )

class Wait(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.can_wait()

    fixture_status_running = """
        <resources>
            <resource id="A" managed="true" role="Started">
                <node name="node1" id="1" cached="false"/>
            </resource>
            <resource id="B" managed="true" role="Started">
                <node name="node2" id="1" cached="false"/>
            </resource>
        </resources>
    """
    fixture_status_stopped = """
        <resources>
            <resource id="A" managed="true" role="Stopped">
            </resource>
            <resource id="B" managed="true" role="Stopped">
            </resource>
        </resources>
    """
    fixture_status_mixed = """
        <resources>
            <resource id="A" managed="true" role="Stopped">
            </resource>
            <resource id="B" managed="true" role="Stopped">
            </resource>
        </resources>
    """
    fixture_wait_timeout_error = outdent(
        """\
        Pending actions:
                Action 12: B-node2-stop on node2
        Error performing operation: Timer expired
        """
    )

    def test_enable_dont_wait_on_error(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_disabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(self.env_assist.get_env(), ["B"], 10),
            [
                fixture.report_not_found("B", "resources"),
            ],
            expected_in_processor=False
        )

    def test_disable_dont_wait_on_error(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_enabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(self.env_assist.get_env(), ["B"], 10),
            [
                fixture.report_not_found("B", "resources"),
            ],
            expected_in_processor=False
        )

    def test_enable_resource_stopped(self):
        (self.config.runner
            .cib.load(resources=fixture_two_primitives_cib_disabled_both)
            .pcmk.load_state(resources=self.fixture_status_stopped)
            .cib.push(resources=fixture_two_primitives_cib_enabled)
            .pcmk.wait()
            .pcmk.load_state(resources=self.fixture_status_stopped, name="")
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(self.env_assist.get_env(), ["A", "B"], 10),
            [
                fixture.report_resource_not_running("A", severities.ERROR),
                fixture.report_resource_not_running("B", severities.ERROR),
            ]
        )

    def test_disable_resource_stopped(self):
        (self.config.runner
            .cib.load(resources=fixture_two_primitives_cib_enabled)
            .pcmk.load_state(resources=self.fixture_status_running)
            .cib.push(resources=fixture_two_primitives_cib_disabled_both)
            .pcmk.wait()
            .pcmk.load_state(resources=self.fixture_status_stopped, name="")
        )

        resource.disable(self.env_assist.get_env(), ["A", "B"], 10)
        self.env_assist.assert_reports([
            fixture.report_resource_not_running("A"),
            fixture.report_resource_not_running("B"),
        ])

    def test_enable_resource_running(self):
        (self.config.runner
            .cib.load(resources=fixture_two_primitives_cib_disabled_both)
            .pcmk.load_state(resources=self.fixture_status_stopped)
            .cib.push(resources=fixture_two_primitives_cib_enabled)
            .pcmk.wait()
            .pcmk.load_state(resources=self.fixture_status_running, name="")
        )

        resource.enable(self.env_assist.get_env(), ["A", "B"], 10)

        self.env_assist.assert_reports([
            fixture.report_resource_running("A", {"Started": ["node1"]}),
            fixture.report_resource_running("B", {"Started": ["node2"]}),
        ])

    def test_disable_resource_running(self):
        (self.config.runner
            .cib.load(resources=fixture_two_primitives_cib_enabled)
            .pcmk.load_state(resources=self.fixture_status_running)
            .cib.push(resources=fixture_two_primitives_cib_disabled_both)
            .pcmk.wait()
            .pcmk.load_state(resources=self.fixture_status_running, name="")
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(self.env_assist.get_env(), ["A", "B"], 10),
            [
                fixture.report_resource_running(
                    "A", {"Started": ["node1"]}, severities.ERROR
                ),
                fixture.report_resource_running(
                    "B", {"Started": ["node2"]}, severities.ERROR
                ),
            ]
        )

    def test_enable_wait_timeout(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_disabled)
            .pcmk.load_state(resources=self.fixture_status_stopped)
            .cib.push(resources=fixture_primitive_cib_enabled)
            .pcmk.wait(stderr=self.fixture_wait_timeout_error)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(self.env_assist.get_env(), ["A"], 10),
            [
                fixture.report_wait_for_idle_timed_out(
                    self.fixture_wait_timeout_error
                )
            ],
            expected_in_processor=False
        )

    def test_disable_wait_timeout(self):
        (self.config.runner
            .cib.load(resources=fixture_primitive_cib_enabled)
            .pcmk.load_state(resources=self.fixture_status_running)
            .cib.push(resources=fixture_primitive_cib_disabled)
            .pcmk.wait(stderr=self.fixture_wait_timeout_error)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(self.env_assist.get_env(), ["A"], 10),
            [
                fixture.report_wait_for_idle_timed_out(
                    self.fixture_wait_timeout_error
                )
            ],
            expected_in_processor=False
        )


class WaitClone(TestCase):
    fixture_status_running = """
        <resources>
            <clone id="A-clone" managed="true" multi_state="false" unique="false">
                <resource id="A" managed="true" role="Started">
                    <node name="node1" id="1" cached="false"/>
                </resource>
                <resource id="A" managed="true" role="Started">
                    <node name="node2" id="2" cached="false"/>
                </resource>
            </clone>
        </resources>
    """
    fixture_status_stopped = """
        <resources>
            <clone id="A-clone" managed="true" multi_state="false" unique="false">
                <resource id="A" managed="true" role="Stopped">
                </resource>
                <resource id="A" managed="true" role="Stopped">
                </resource>
            </clone>
        </resources>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.can_wait()

    def test_disable_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_enabled)
            .pcmk.load_state(resources=self.fixture_status_running)
            .cib.push(resources=fixture_clone_cib_disabled_clone)
            .pcmk.wait()
            .pcmk.load_state(resources=self.fixture_status_stopped, name="")
        )

        resource.disable(self.env_assist.get_env(), ["A-clone"], 10)
        self.env_assist.assert_reports([
            (
                severities.INFO,
                report_codes.RESOURCE_DOES_NOT_RUN,
                {
                    "resource_id": "A-clone",
                },
                None
            )
        ])

    def test_enable_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_disabled_clone)
            .pcmk.load_state(resources=self.fixture_status_stopped)
            .cib.push(resources=fixture_clone_cib_enabled)
            .pcmk.wait()
            .pcmk.load_state(resources=self.fixture_status_running, name="")
        )

        resource.enable(self.env_assist.get_env(), ["A-clone"], 10)
        self.env_assist.assert_reports([
            (
                severities.INFO,
                report_codes.RESOURCE_RUNNING_ON_NODES,
                {
                    "resource_id": "A-clone",
                    "roles_with_nodes": {"Started": ["node1", "node2"]},
                },
                None
            )
        ])

class DisableGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_group_cib_enabled)

    def test_primitive(self):
        (self.config.runner
            .pcmk.load_state(resources=fixture_group_status_managed)
            .cib.push(resources=fixture_group_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A1"], wait=False)

    def test_group(self):
        (self.config.runner
            .pcmk.load_state(resources=fixture_group_status_managed)
            .cib.push(resources=fixture_group_cib_disabled_group)
        )
        resource.disable(self.env_assist.get_env(), ["A"], wait=False)

    def test_primitive_unmanaged(self):
        (self.config.runner
            .pcmk.load_state(resources=fixture_group_status_unmanaged)
            .cib.push(resources=fixture_group_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A1"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A1"),
        ])

    def test_group_unmanaged(self):
        (self.config.runner
            .pcmk.load_state(resources=fixture_group_status_unmanaged)
            .cib.push(resources=fixture_group_cib_disabled_group)
        )
        resource.disable(self.env_assist.get_env(), ["A"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])

class EnableGroupNew(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_group_status_managed)
            .cib.push(resources=fixture_group_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A1"], wait=False)

    def test_primitive_disabled_both(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_disabled_both)
            .pcmk.load_state(resources=fixture_group_status_managed)
            .cib.push(resources=fixture_group_cib_disabled_group)
        )
        resource.enable(self.env_assist.get_env(), ["A1"], wait=False)

    def test_group(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_disabled_group)
            .pcmk.load_state(resources=fixture_group_status_managed)
            .cib.push(resources=fixture_group_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)

    def test_group_both_disabled(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_disabled_both)
            .pcmk.load_state(resources=fixture_group_status_managed)
            .cib.push(resources=fixture_group_cib_disabled_primitive)
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)

    def test_primitive_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_group_status_unmanaged)
            .cib.push(resources=fixture_group_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A1"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A1"),
        ])

    def test_group_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_group_cib_disabled_group)
            .pcmk.load_state(resources=fixture_group_status_unmanaged)
            .cib.push(resources=fixture_group_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])


class DisableClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_clone_cib_enabled)

    def test_primitive(self):
        (self.config.runner
            .pcmk.load_state(resources=fixture_clone_status_managed)
            .cib.push(resources=fixture_clone_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A"], wait=False)

    def test_clone(self):
        (self.config.runner
            .pcmk.load_state(resources=fixture_clone_status_managed)
            .cib.push(resources=fixture_clone_cib_disabled_clone)
        )
        resource.disable(self.env_assist.get_env(), ["A-clone"], wait=False)

    def test_primitive_unmanaged(self):
        (self.config.runner
            .pcmk.load_state(resources=fixture_clone_status_unmanaged)
            .cib.push(resources=fixture_clone_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])

    def test_clone_unmanaged(self):
        (self.config.runner
            .pcmk.load_state(resources=fixture_clone_status_unmanaged)
            .cib.push(resources=fixture_clone_cib_disabled_clone)
        )
        resource.disable(self.env_assist.get_env(), ["A-clone"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
        ])

class EnableClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_clone_status_managed)
            .cib.push(resources=fixture_clone_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)

    def test_primitive_disabled_both(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_disabled_both)
            .pcmk.load_state(resources=fixture_clone_status_managed)
            .cib.push(resources=fixture_clone_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)

    def test_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_disabled_clone)
            .pcmk.load_state(resources=fixture_clone_status_managed)
            .cib.push(resources=fixture_clone_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], wait=False)

    def test_clone_disabled_both(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_disabled_both)
            .pcmk.load_state(resources=fixture_clone_status_managed)
            .cib.push(resources=fixture_clone_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], wait=False)

    def test_primitive_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_clone_status_unmanaged)
            .cib.push(resources=fixture_clone_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
            fixture_report_unmanaged("A"),
        ])

    def test_clone_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_cib_disabled_clone)
            .pcmk.load_state(resources=fixture_clone_status_unmanaged)
            .cib.push(resources=fixture_clone_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
            fixture_report_unmanaged("A"),
        ])

class DisableMaster(TestCase):
    # same as clone, minimum tests in here
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config.runner
            .cib.load(resources=fixture_master_cib_enabled)
            .pcmk.load_state(resources=fixture_master_status_managed)
        )

    def test_primitive(self):
        self.config.runner.cib.push(
            resources=fixture_master_cib_disabled_primitive
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)

    def test_master(self):
        self.config.runner.cib.push(
            resources=fixture_master_cib_disabled_master
        )
        resource.disable(self.env_assist.get_env(), ["A-master"], False)

class EnableMaster(TestCase):
    # same as clone, minimum tests in here
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_master_status_managed)
            .cib.push(resources=fixture_master_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_primitive_disabled_both(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_disabled_both)
            .pcmk.load_state(resources=fixture_master_status_managed)
            .cib.push(resources=fixture_master_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_master(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_disabled_master)
            .pcmk.load_state(resources=fixture_master_status_managed)
            .cib.push(resources=fixture_master_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A-master"], False)

    def test_master_disabled_both(self):
        (self.config.runner
            .cib.load(resources=fixture_master_cib_disabled_both)
            .pcmk.load_state(resources=fixture_master_status_managed)
            .cib.push(resources=fixture_master_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A-master"], False)

class DisableClonedGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_enabled)
            .pcmk.load_state(resources=fixture_clone_group_status_managed)
            .cib.push(resources=fixture_clone_group_cib_disabled_clone)
        )
        resource.disable(self.env_assist.get_env(), ["A-clone"], False)

    def test_group(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_enabled)
            .pcmk.load_state(resources=fixture_clone_group_status_managed)
            .cib.push(resources=fixture_clone_group_cib_disabled_group)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_enabled)
            .pcmk.load_state(resources=fixture_clone_group_status_managed)
            .cib.push(resources=fixture_clone_group_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A1"], False)

    def test_clone_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_enabled)
            .pcmk.load_state(resources=fixture_clone_group_status_unmanaged)
            .cib.push(resources=fixture_clone_group_cib_disabled_clone)
        )
        resource.disable(self.env_assist.get_env(), ["A-clone"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
        ])

    def test_group_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_enabled)
            .pcmk.load_state(resources=fixture_clone_group_status_unmanaged)
            .cib.push(resources=fixture_clone_group_cib_disabled_group)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])

    def test_primitive_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_enabled)
            .pcmk.load_state(resources=fixture_clone_group_status_unmanaged)
            .cib.push(resources=fixture_clone_group_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A1"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A1"),
        ])


class EnableClonedGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_clone(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_disabled_clone)
            .pcmk.load_state(resources=fixture_clone_group_status_managed)
            .cib.push(resources=fixture_clone_group_cib_enabled,)
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], False)

    def test_clone_disabled_all(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_disabled_all)
            .pcmk.load_state(resources=fixture_clone_group_status_managed)
            .cib.push(resources=fixture_clone_group_cib_disabled_primitive)
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], False)

    def test_group(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_disabled_group)
            .pcmk.load_state(resources=fixture_clone_group_status_managed)
            .cib.push(resources=fixture_clone_group_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_group_disabled_all(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_disabled_all)
            .pcmk.load_state(resources=fixture_clone_group_status_managed)
            .cib.push(resources=fixture_clone_group_cib_disabled_primitive)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_clone_group_status_managed)
            .cib.push(resources=fixture_clone_group_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A1"], False)

    def test_primitive_disabled_all(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_disabled_all)
            .pcmk.load_state(resources=fixture_clone_group_status_managed)
            .cib.push(resources=fixture_clone_group_cib_disabled_clone_group)
        )
        resource.enable(self.env_assist.get_env(), ["A1"], False)

    def test_clone_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_disabled_clone)
            .pcmk.load_state(resources=fixture_clone_group_status_unmanaged)
            .cib.push(resources=fixture_clone_group_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
            fixture_report_unmanaged("A"),
        ])

    def test_group_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_disabled_group)
            .pcmk.load_state(resources=fixture_clone_group_status_unmanaged)
            .cib.push(resources=fixture_clone_group_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
            fixture_report_unmanaged("A-clone"),
        ])

    def test_primitive_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_clone_group_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_clone_group_status_unmanaged)
            .cib.push(resources=fixture_clone_group_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A1"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A1"),
        ])


@skip_unless_pacemaker_supports_bundle
class DisableBundle(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_enabled)
            .pcmk.load_state(resources=fixture_bundle_status_managed)
            .cib.push(resources=fixture_bundle_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)

    def test_bundle(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_enabled)
            .pcmk.load_state(resources=fixture_bundle_status_managed)
            .cib.push(resources=fixture_bundle_cib_disabled_bundle)
        )
        resource.disable(self.env_assist.get_env(), ["A-bundle"], False)

    def test_primitive_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_enabled)
            .pcmk.load_state(resources=fixture_bundle_status_unmanaged)
            .cib.push(resources=fixture_bundle_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])

    def test_bundle_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_enabled)
            .pcmk.load_state(resources=fixture_bundle_status_unmanaged)
            .cib.push(resources=fixture_bundle_cib_disabled_bundle)
        )
        resource.disable(self.env_assist.get_env(), ["A-bundle"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-bundle"),
        ])


@skip_unless_pacemaker_supports_bundle
class EnableBundle(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_bundle_status_managed)
            .cib.push(resources=fixture_bundle_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_primitive_disabled_both(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_disabled_both)
            .pcmk.load_state(resources=fixture_bundle_status_managed)
            .cib.push(resources=fixture_bundle_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_bundle(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_disabled_bundle)
            .pcmk.load_state(resources=fixture_bundle_status_managed)
            .cib.push(resources=fixture_bundle_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A-bundle"], False)

    def test_bundle_disabled_both(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_disabled_both)
            .pcmk.load_state(resources=fixture_bundle_status_managed)
            .cib.push(resources=fixture_bundle_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A-bundle"], False)

    def test_primitive_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_bundle_status_unmanaged)
            .cib.push(resources=fixture_bundle_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
            fixture_report_unmanaged("A-bundle"),
        ])

    def test_bundle_unmanaged(self):
        (self.config.runner
            .cib.load(resources=fixture_bundle_cib_disabled_primitive)
            .pcmk.load_state(resources=fixture_bundle_status_unmanaged)
            .cib.push(resources=fixture_bundle_cib_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A-bundle"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-bundle"),
            fixture_report_unmanaged("A"),
        ])

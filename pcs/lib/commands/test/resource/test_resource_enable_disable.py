from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib.commands import resource
from pcs.lib.commands.test.resource.common import ResourceWithStateTest
import pcs.lib.commands.test.resource.fixture as fixture
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.misc import (
    outdent,
    skip_unless_pacemaker_supports_bundle,
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
            unique="false" managed="true" failed="false"
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


class DisablePrimitive(ResourceWithStateTest):
    def test_nonexistent_resource(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(fixture_primitive_cib_enabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["B"], False),
            fixture.report_not_found("B", "resources")
        )
        self.runner.assert_everything_launched()

    def test_nonexistent_resource_in_status(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(fixture_two_primitives_cib_enabled)
            )
            +
            fixture.call_status(
                fixture.state_complete(fixture_primitive_status_managed)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["B"], False),
            fixture.report_not_found("B")
        )
        self.runner.assert_everything_launched()

    def test_correct_resource(self):
        self.assert_command_effect(
            fixture_two_primitives_cib_enabled,
            fixture_two_primitives_status_managed,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_two_primitives_cib_disabled
        )

    def test_unmanaged(self):
        # The code doesn't care what causes the resource to be unmanaged
        # (cluster property, resource's meta-attribute or whatever). It only
        # checks the cluster state (crm_mon).
        self.assert_command_effect(
            fixture_primitive_cib_enabled,
            fixture_primitive_status_unmanaged,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_primitive_cib_disabled,
            reports=[
                fixture_report_unmanaged("A"),
            ]
        )


class EnablePrimitive(ResourceWithStateTest):
    def test_nonexistent_resource(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(fixture_primitive_cib_disabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["B"], False),
            fixture.report_not_found("B", "resources")
        )
        self.runner.assert_everything_launched()

    def test_nonexistent_resource_in_status(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(fixture_two_primitives_cib_disabled)
            )
            +
            fixture.call_status(
                fixture.state_complete(fixture_primitive_status_managed)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["B"], False),
            fixture.report_not_found("B")
        )
        self.runner.assert_everything_launched()

    def test_correct_resource(self):
        self.assert_command_effect(
            fixture_two_primitives_cib_disabled_both,
            fixture_two_primitives_status_managed,
            lambda: resource.enable(self.env, ["B"], False),
            fixture_two_primitives_cib_disabled
        )

    def test_unmanaged(self):
        # The code doesn't care what causes the resource to be unmanaged
        # (cluster property, resource's meta-attribute or whatever). It only
        # checks the cluster state (crm_mon).
        self.assert_command_effect(
            fixture_primitive_cib_disabled,
            fixture_primitive_status_unmanaged,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_primitive_cib_enabled,
            reports=[
                fixture_report_unmanaged("A"),
            ]
        )


class MoreResources(ResourceWithStateTest):
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
        self.assert_command_effect(
            self.fixture_cib_disabled,
            self.fixture_status,
            lambda: resource.enable(self.env, ["A", "B", "D"], False),
            fixture_enabled,
            reports=[
                fixture_report_unmanaged("B"),
                fixture_report_unmanaged("D"),
            ]
        )

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
        self.assert_command_effect(
            self.fixture_cib_enabled,
            self.fixture_status,
            lambda: resource.disable(self.env, ["A", "B", "D"], False),
            fixture_disabled,
            reports=[
                fixture_report_unmanaged("B"),
                fixture_report_unmanaged("D"),
            ]
        )

    def test_bad_resource_enable(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(self.fixture_cib_disabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["B", "X", "Y", "A"], False),
            fixture.report_not_found("X", "resources"),
            fixture.report_not_found("Y", "resources"),
        )
        self.runner.assert_everything_launched()

    def test_bad_resource_disable(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(self.fixture_cib_enabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["B", "X", "Y", "A"], False),
            fixture.report_not_found("X", "resources"),
            fixture.report_not_found("Y", "resources"),
        )
        self.runner.assert_everything_launched()


class Wait(ResourceWithStateTest):
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
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.call_cib_load(
                fixture.cib_resources(fixture_primitive_cib_disabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["B"], 10),
            fixture.report_not_found("B", "resources"),
        )
        self.runner.assert_everything_launched()

    def test_disable_dont_wait_on_error(self):
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.call_cib_load(
                fixture.cib_resources(fixture_primitive_cib_enabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["B"], 10),
            fixture.report_not_found("B", "resources"),
        )
        self.runner.assert_everything_launched()

    def test_enable_resource_stopped(self):
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.calls_cib_and_status(
                fixture_two_primitives_cib_disabled_both,
                self.fixture_status_stopped,
                fixture_two_primitives_cib_enabled
            )
            +
            fixture.call_wait(10)
            +
            fixture.call_status(
                fixture.state_complete(self.fixture_status_stopped)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["A", "B"], 10),
            fixture.report_resource_not_running("A", severities.ERROR),
            fixture.report_resource_not_running("B", severities.ERROR),
        )
        self.runner.assert_everything_launched()

    def test_disable_resource_stopped(self):
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.calls_cib_and_status(
                fixture_two_primitives_cib_enabled,
                self.fixture_status_running,
                fixture_two_primitives_cib_disabled_both
            )
            +
            fixture.call_wait(10)
            +
            fixture.call_status(
                fixture.state_complete(self.fixture_status_stopped)
            )
        )

        resource.disable(self.env, ["A", "B"], 10)
        self.env.report_processor.assert_reports([
            fixture.report_resource_not_running("A"),
            fixture.report_resource_not_running("B"),
        ])
        self.runner.assert_everything_launched()

    def test_enable_resource_running(self):
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.calls_cib_and_status(
                fixture_two_primitives_cib_disabled_both,
                self.fixture_status_stopped,
                fixture_two_primitives_cib_enabled
            )
            +
            fixture.call_wait(10)
            +
            fixture.call_status(
                fixture.state_complete(self.fixture_status_running)
            )
        )

        resource.enable(self.env, ["A", "B"], 10)

        self.env.report_processor.assert_reports([
            fixture.report_resource_running("A", {"Started": ["node1"]}),
            fixture.report_resource_running("B", {"Started": ["node2"]}),
        ])
        self.runner.assert_everything_launched()

    def test_disable_resource_running(self):
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.calls_cib_and_status(
                fixture_two_primitives_cib_enabled,
                self.fixture_status_running,
                fixture_two_primitives_cib_disabled_both
            )
            +
            fixture.call_wait(10)
            +
            fixture.call_status(
                fixture.state_complete(self.fixture_status_running)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["A", "B"], 10),
            fixture.report_resource_running(
                "A", {"Started": ["node1"]}, severities.ERROR
            ),
            fixture.report_resource_running(
                "B", {"Started": ["node2"]}, severities.ERROR
            ),
        )
        self.runner.assert_everything_launched()

    def test_enable_wait_timeout(self):
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.calls_cib_and_status(
                fixture_primitive_cib_disabled,
                self.fixture_status_stopped,
                fixture_primitive_cib_enabled
            )
            +
            fixture.call_wait(
                10, retval=62, stderr=self.fixture_wait_timeout_error
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["A"], 10),
            fixture.report_wait_for_idle_timed_out(
                self.fixture_wait_timeout_error
            ),
        )
        self.runner.assert_everything_launched()

    def test_disable_wait_timeout(self):
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.calls_cib_and_status(
                fixture_primitive_cib_enabled,
                self.fixture_status_running,
                fixture_primitive_cib_disabled
            )
            +
            fixture.call_wait(
                10, retval=62, stderr=self.fixture_wait_timeout_error
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["A"], 10),
            fixture.report_wait_for_idle_timed_out(
                self.fixture_wait_timeout_error
            ),
        )
        self.runner.assert_everything_launched()


class WaitClone(ResourceWithStateTest):
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
    def test_disable_clone(self):
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.calls_cib_and_status(
                fixture_clone_cib_enabled,
                self.fixture_status_running,
                fixture_clone_cib_disabled_clone
            )
            +
            fixture.call_wait(10)
            +
            fixture.call_status(
                fixture.state_complete(self.fixture_status_stopped)
            )
        )

        resource.disable(self.env, ["A-clone"], 10)
        self.env.report_processor.assert_reports([
            (
                severities.INFO,
                report_codes.RESOURCE_DOES_NOT_RUN,
                {
                    "resource_id": "A-clone",
                },
                None
            )
        ])
        self.runner.assert_everything_launched()

    def test_enable_clone(self):
        self.runner.set_runs(
            fixture.call_wait_supported()
            +
            fixture.calls_cib_and_status(
                fixture_clone_cib_disabled_clone,
                self.fixture_status_stopped,
                fixture_clone_cib_enabled
            )
            +
            fixture.call_wait(10)
            +
            fixture.call_status(
                fixture.state_complete(self.fixture_status_running)
            )
        )

        resource.enable(self.env, ["A-clone"], 10)

        self.env.report_processor.assert_reports([
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
        self.runner.assert_everything_launched()


class DisableGroup(ResourceWithStateTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_group_cib_enabled,
            fixture_group_status_managed,
            lambda: resource.disable(self.env, ["A1"], False),
            fixture_group_cib_disabled_primitive
        )

    def test_group(self):
        self.assert_command_effect(
            fixture_group_cib_enabled,
            fixture_group_status_managed,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_group_cib_disabled_group
        )

    def test_primitive_unmanaged(self):
        self.assert_command_effect(
            fixture_group_cib_enabled,
            fixture_group_status_unmanaged,
            lambda: resource.disable(self.env, ["A1"], False),
            fixture_group_cib_disabled_primitive,
            reports=[
                fixture_report_unmanaged("A1"),
            ]
        )

    def test_group_unmanaged(self):
        self.assert_command_effect(
            fixture_group_cib_enabled,
            fixture_group_status_unmanaged,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_group_cib_disabled_group,
            reports=[
                fixture_report_unmanaged("A"),
            ]
        )


class EnableGroup(ResourceWithStateTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_group_cib_disabled_primitive,
            fixture_group_status_managed,
            lambda: resource.enable(self.env, ["A1"], False),
            fixture_group_cib_enabled
        )

    def test_primitive_disabled_both(self):
        self.assert_command_effect(
            fixture_group_cib_disabled_both,
            fixture_group_status_managed,
            lambda: resource.enable(self.env, ["A1"], False),
            fixture_group_cib_disabled_group
        )

    def test_group(self):
        self.assert_command_effect(
            fixture_group_cib_disabled_group,
            fixture_group_status_managed,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_group_cib_enabled
        )

    def test_group_both_disabled(self):
        self.assert_command_effect(
            fixture_group_cib_disabled_both,
            fixture_group_status_managed,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_group_cib_disabled_primitive
        )

    def test_primitive_unmanaged(self):
        self.assert_command_effect(
            fixture_group_cib_disabled_primitive,
            fixture_group_status_unmanaged,
            lambda: resource.enable(self.env, ["A1"], False),
            fixture_group_cib_enabled,
            reports=[
                fixture_report_unmanaged("A1"),
            ]
        )

    def test_group_unmanaged(self):
        self.assert_command_effect(
            fixture_group_cib_disabled_group,
            fixture_group_status_unmanaged,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_group_cib_enabled,
            reports=[
                fixture_report_unmanaged("A"),
            ]
        )


class DisableClone(ResourceWithStateTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_clone_cib_enabled,
            fixture_clone_status_managed,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_clone_cib_disabled_primitive
        )

    def test_clone(self):
        self.assert_command_effect(
            fixture_clone_cib_enabled,
            fixture_clone_status_managed,
            lambda: resource.disable(self.env, ["A-clone"], False),
            fixture_clone_cib_disabled_clone
        )

    def test_primitive_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_cib_enabled,
            fixture_clone_status_unmanaged,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_clone_cib_disabled_primitive,
            reports=[
                fixture_report_unmanaged("A"),
            ]
        )

    def test_clone_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_cib_enabled,
            fixture_clone_status_unmanaged,
            lambda: resource.disable(self.env, ["A-clone"], False),
            fixture_clone_cib_disabled_clone,
            reports=[
                fixture_report_unmanaged("A-clone"),
            ]
        )


class EnableClone(ResourceWithStateTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_clone_cib_disabled_primitive,
            fixture_clone_status_managed,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_clone_cib_enabled
        )

    def test_primitive_disabled_both(self):
        self.assert_command_effect(
            fixture_clone_cib_disabled_both,
            fixture_clone_status_managed,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_clone_cib_enabled
        )

    def test_clone(self):
        self.assert_command_effect(
            fixture_clone_cib_disabled_clone,
            fixture_clone_status_managed,
            lambda: resource.enable(self.env, ["A-clone"], False),
            fixture_clone_cib_enabled
        )

    def test_clone_disabled_both(self):
        self.assert_command_effect(
            fixture_clone_cib_disabled_both,
            fixture_clone_status_managed,
            lambda: resource.enable(self.env, ["A-clone"], False),
            fixture_clone_cib_enabled
        )

    def test_primitive_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_cib_disabled_primitive,
            fixture_clone_status_unmanaged,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_clone_cib_enabled,
            reports=[
                fixture_report_unmanaged("A-clone"),
                fixture_report_unmanaged("A"),
            ]
        )

    def test_clone_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_cib_disabled_clone,
            fixture_clone_status_unmanaged,
            lambda: resource.enable(self.env, ["A-clone"], False),
            fixture_clone_cib_enabled,
            reports=[
                fixture_report_unmanaged("A-clone"),
                fixture_report_unmanaged("A"),
            ]
        )


class DisableMaster(ResourceWithStateTest):
    # same as clone, minimum tests in here
    def test_primitive(self):
        self.assert_command_effect(
            fixture_master_cib_enabled,
            fixture_master_status_managed,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_master_cib_disabled_primitive
        )

    def test_master(self):
        self.assert_command_effect(
            fixture_master_cib_enabled,
            fixture_master_status_managed,
            lambda: resource.disable(self.env, ["A-master"], False),
            fixture_master_cib_disabled_master
        )


class EnableMaster(ResourceWithStateTest):
    # same as clone, minimum tests in here
    def test_primitive(self):
        self.assert_command_effect(
            fixture_master_cib_disabled_primitive,
            fixture_master_status_managed,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_master_cib_enabled
        )

    def test_primitive_disabled_both(self):
        self.assert_command_effect(
            fixture_master_cib_disabled_both,
            fixture_master_status_managed,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_master_cib_enabled
        )

    def test_master(self):
        self.assert_command_effect(
            fixture_master_cib_disabled_master,
            fixture_master_status_managed,
            lambda: resource.enable(self.env, ["A-master"], False),
            fixture_master_cib_enabled
        )

    def test_master_disabled_both(self):
        self.assert_command_effect(
            fixture_master_cib_disabled_both,
            fixture_master_status_managed,
            lambda: resource.enable(self.env, ["A-master"], False),
            fixture_master_cib_enabled
        )

class DisableClonedGroup(ResourceWithStateTest):
    def test_clone(self):
        self.assert_command_effect(
            fixture_clone_group_cib_enabled,
            fixture_clone_group_status_managed,
            lambda: resource.disable(self.env, ["A-clone"], False),
            fixture_clone_group_cib_disabled_clone
        )

    def test_group(self):
        self.assert_command_effect(
            fixture_clone_group_cib_enabled,
            fixture_clone_group_status_managed,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_clone_group_cib_disabled_group
        )

    def test_primitive(self):
        self.assert_command_effect(
            fixture_clone_group_cib_enabled,
            fixture_clone_group_status_managed,
            lambda: resource.disable(self.env, ["A1"], False),
            fixture_clone_group_cib_disabled_primitive
        )

    def test_clone_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_group_cib_enabled,
            fixture_clone_group_status_unmanaged,
            lambda: resource.disable(self.env, ["A-clone"], False),
            fixture_clone_group_cib_disabled_clone,
            reports=[
                fixture_report_unmanaged("A-clone"),
            ]
        )

    def test_group_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_group_cib_enabled,
            fixture_clone_group_status_unmanaged,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_clone_group_cib_disabled_group,
            reports=[
                fixture_report_unmanaged("A"),
            ]
        )

    def test_primitive_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_group_cib_enabled,
            fixture_clone_group_status_unmanaged,
            lambda: resource.disable(self.env, ["A1"], False),
            fixture_clone_group_cib_disabled_primitive,
            reports=[
                fixture_report_unmanaged("A1"),
            ]
        )


class EnableClonedGroup(ResourceWithStateTest):
    def test_clone(self):
        self.assert_command_effect(
            fixture_clone_group_cib_disabled_clone,
            fixture_clone_group_status_managed,
            lambda: resource.enable(self.env, ["A-clone"], False),
            fixture_clone_group_cib_enabled,
        )

    def test_clone_disabled_all(self):
        self.assert_command_effect(
            fixture_clone_group_cib_disabled_all,
            fixture_clone_group_status_managed,
            lambda: resource.enable(self.env, ["A-clone"], False),
            fixture_clone_group_cib_disabled_primitive
        )

    def test_group(self):
        self.assert_command_effect(
            fixture_clone_group_cib_disabled_group,
            fixture_clone_group_status_managed,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_clone_group_cib_enabled
        )

    def test_group_disabled_all(self):
        self.assert_command_effect(
            fixture_clone_group_cib_disabled_all,
            fixture_clone_group_status_managed,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_clone_group_cib_disabled_primitive
        )

    def test_primitive(self):
        self.assert_command_effect(
            fixture_clone_group_cib_disabled_primitive,
            fixture_clone_group_status_managed,
            lambda: resource.enable(self.env, ["A1"], False),
            fixture_clone_group_cib_enabled
        )

    def test_primitive_disabled_all(self):
        self.assert_command_effect(
            fixture_clone_group_cib_disabled_all,
            fixture_clone_group_status_managed,
            lambda: resource.enable(self.env, ["A1"], False),
            fixture_clone_group_cib_disabled_clone_group
        )

    def test_clone_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_group_cib_disabled_clone,
            fixture_clone_group_status_unmanaged,
            lambda: resource.enable(self.env, ["A-clone"], False),
            fixture_clone_group_cib_enabled,
            reports=[
                fixture_report_unmanaged("A-clone"),
                fixture_report_unmanaged("A"),
            ]
        )

    def test_group_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_group_cib_disabled_group,
            fixture_clone_group_status_unmanaged,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_clone_group_cib_enabled,
            reports=[
                fixture_report_unmanaged("A"),
                fixture_report_unmanaged("A-clone"),
            ]
        )

    def test_primitive_unmanaged(self):
        self.assert_command_effect(
            fixture_clone_group_cib_disabled_primitive,
            fixture_clone_group_status_unmanaged,
            lambda: resource.enable(self.env, ["A1"], False),
            fixture_clone_group_cib_enabled,
            reports=[
                fixture_report_unmanaged("A1"),
            ]
        )


@skip_unless_pacemaker_supports_bundle
class DisableBundle(ResourceWithStateTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_bundle_cib_enabled,
            fixture_bundle_status_managed,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_bundle_cib_disabled_primitive
        )

    def test_bundle(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(fixture_bundle_cib_enabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["A-bundle"], False),
            fixture.report_not_for_bundles("A-bundle")
        )
        self.runner.assert_everything_launched()

    def test_primitive_unmanaged(self):
        self.assert_command_effect(
            fixture_bundle_cib_enabled,
            fixture_bundle_status_unmanaged,
            lambda: resource.disable(self.env, ["A"], False),
            fixture_bundle_cib_disabled_primitive,
            reports=[
                fixture_report_unmanaged("A"),
            ]
        )


@skip_unless_pacemaker_supports_bundle
class EnableBundle(ResourceWithStateTest):
    def test_primitive(self):
        self.assert_command_effect(
            fixture_bundle_cib_disabled_primitive,
            fixture_bundle_status_managed,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_bundle_cib_enabled
        )

    def test_bundle(self):
        self.runner.set_runs(
            fixture.call_cib_load(
                fixture.cib_resources(fixture_bundle_cib_enabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["A-bundle"], False),
            fixture.report_not_for_bundles("A-bundle")
        )
        self.runner.assert_everything_launched()

    def test_primitive_unmanaged(self):
        self.assert_command_effect(
            fixture_bundle_cib_disabled_primitive,
            fixture_bundle_status_unmanaged,
            lambda: resource.enable(self.env, ["A"], False),
            fixture_bundle_cib_enabled,
            reports=[
                fixture_report_unmanaged("A"),
            ]
        )

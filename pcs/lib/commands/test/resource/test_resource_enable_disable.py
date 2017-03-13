from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
from lxml import etree

from pcs.common import report_codes
from pcs.lib.commands import resource
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.integration_lib import (
    Call,
    Runner,
)
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.misc import (
    get_test_resource as rc,
    outdent,
)
from pcs.test.tools.pcs_unittest import TestCase, mock
from pcs.test.tools.xml import etree_to_str


runner = Runner()

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

def fixture_call_cib_load(cib):
    return [
        Call("cibadmin --local --query", cib),
    ]

def fixture_call_cib_push(cib):
    return [
        Call(
            "cibadmin --replace --verbose --xml-pipe --scope configuration",
            check_stdin=Call.create_check_stdin_xml(cib)
        ),
    ]

def fixture_call_status(status):
    return [
        Call("/usr/sbin/crm_mon --one-shot --as-xml --inactive", status),
    ]

def fixture_call_wait_supported():
    return [
        Call("crm_resource -?", "--wait"),
    ]

def fixture_call_wait(timeout, retval=0, stderr=""):
    return [
        Call(
            "crm_resource --wait --timeout={}".format(timeout),
            stderr=stderr,
            returncode=retval
        ),
    ]

def fixture_calls_cib_and_status(cib_pre, status, cib_post):
    return (
        fixture_call_cib_load(fixture_cib_resources(cib_pre))
        +
        fixture_call_status(fixture_state_complete(status))
        +
        fixture_call_cib_push(fixture_cib_resources(cib_post))
    )

def fixture_cib_resources(cib_resources_xml):
    cib_xml = open(rc("cib-empty.xml")).read()
    cib = etree.fromstring(cib_xml)
    resources_section = cib.find(".//resources")
    for child in etree.fromstring(cib_resources_xml):
        resources_section.append(child)
    return etree_to_str(cib)

def fixture_state_complete(resource_status_xml):
    status = etree.parse(rc("crm_mon.minimal.xml")).getroot()
    resource_status = etree.fromstring(resource_status_xml)
    for resource in resource_status.xpath(".//resource"):
        resource.attrib.update({
            "resource_agent": "ocf::heartbeat:Dummy",
            "active": "true",
            "orphaned": "false",
            "blocked": "false",
            "failed": "false",
            "failure_ignored": "false",
            "nodes_running_on": "1",
        })
        if "role" not in resource.attrib:
            resource.attrib["role"] = "Started"
    for clone in resource_status.xpath(".//clone"):
        clone.attrib.update({
            "failed": "false",
            "failure_ignored": "false",
        })
    status.append(resource_status)
    return etree_to_str(status)

def fixture_report_unmanaged(resource):
    return (
        severities.WARNING,
        report_codes.RESOURCE_IS_UNMANAGED,
        {
            "resource_id": resource,
        },
        None
    )

def fixture_report_not_found(res_id, context_type=""):
    return (
        severities.ERROR,
        report_codes.ID_NOT_FOUND,
        {
            "context_type": context_type,
            "context_id": "",
            "id": res_id,
            "id_description": "resource/clone/master/group",
        },
        None
    )

def fixture_report_resource_not_running(resource, severity=severities.INFO):
    return (
        severity,
        report_codes.RESOURCE_DOES_NOT_RUN,
        {
            "resource_id": resource,
        },
        None
    )

def fixture_report_resource_running(resource, roles, severity=severities.INFO):
    return (
        severity,
        report_codes.RESOURCE_RUNNING_ON_NODES,
        {
            "resource_id": resource,
            "roles_with_nodes": roles,
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

    def assert_command_effect(
        self, cib_pre, status, cmd, cib_post, reports=None
    ):
        runner.set_runs(
            fixture_calls_cib_and_status(cib_pre, status, cib_post)
        )
        cmd()
        self.env.report_processor.assert_reports(reports if reports else [])
        runner.assert_everything_launched()


class DisablePrimitive(CommonResourceTest):
    def test_nonexistent_resource(self):
        runner.set_runs(
            fixture_call_cib_load(
                fixture_cib_resources(fixture_primitive_cib_enabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["B"], False),
            fixture_report_not_found("B", "resources")
        )
        runner.assert_everything_launched()

    def test_nonexistent_resource_in_status(self):
        runner.set_runs(
            fixture_call_cib_load(
                fixture_cib_resources(fixture_two_primitives_cib_enabled)
            )
            +
            fixture_call_status(
                fixture_state_complete(fixture_primitive_status_managed)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["B"], False),
            fixture_report_not_found("B")
        )
        runner.assert_everything_launched()

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


class EnablePrimitive(CommonResourceTest):
    def test_nonexistent_resource(self):
        runner.set_runs(
            fixture_call_cib_load(
                fixture_cib_resources(fixture_primitive_cib_disabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["B"], False),
            fixture_report_not_found("B", "resources")
        )
        runner.assert_everything_launched()

    def test_nonexistent_resource_in_status(self):
        runner.set_runs(
            fixture_call_cib_load(
                fixture_cib_resources(fixture_two_primitives_cib_disabled)
            )
            +
            fixture_call_status(
                fixture_state_complete(fixture_primitive_status_managed)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["B"], False),
            fixture_report_not_found("B")
        )
        runner.assert_everything_launched()

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


class MoreResources(CommonResourceTest):
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
        runner.set_runs(
            fixture_call_cib_load(
                fixture_cib_resources(self.fixture_cib_disabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["B", "X", "Y", "A"], False),
            fixture_report_not_found("X", "resources"),
            fixture_report_not_found("Y", "resources"),
        )
        runner.assert_everything_launched()

    def test_bad_resource_disable(self):
        runner.set_runs(
            fixture_call_cib_load(
                fixture_cib_resources(self.fixture_cib_enabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["B", "X", "Y", "A"], False),
            fixture_report_not_found("X", "resources"),
            fixture_report_not_found("Y", "resources"),
        )
        runner.assert_everything_launched()


class Wait(CommonResourceTest):
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
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_call_cib_load(
                fixture_cib_resources(fixture_primitive_cib_disabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["B"], 10),
            fixture_report_not_found("B", "resources"),
        )
        runner.assert_everything_launched()

    def test_disable_dont_wait_on_error(self):
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_call_cib_load(
                fixture_cib_resources(fixture_primitive_cib_enabled)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["B"], 10),
            fixture_report_not_found("B", "resources"),
        )
        runner.assert_everything_launched()

    def test_enable_resource_stopped(self):
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_calls_cib_and_status(
                fixture_two_primitives_cib_disabled_both,
                self.fixture_status_stopped,
                fixture_two_primitives_cib_enabled
            )
            +
            fixture_call_wait(10)
            +
            fixture_call_status(
                fixture_state_complete(self.fixture_status_stopped)
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["A", "B"], 10),
            fixture_report_resource_not_running("A", severities.ERROR),
            fixture_report_resource_not_running("B", severities.ERROR),
        )
        runner.assert_everything_launched()

    def test_disable_resource_stopped(self):
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_calls_cib_and_status(
                fixture_two_primitives_cib_enabled,
                self.fixture_status_running,
                fixture_two_primitives_cib_disabled_both
            )
            +
            fixture_call_wait(10)
            +
            fixture_call_status(
                fixture_state_complete(self.fixture_status_stopped)
            )
        )

        resource.disable(self.env, ["A", "B"], 10)
        self.env.report_processor.assert_reports([
            fixture_report_resource_not_running("A"),
            fixture_report_resource_not_running("B"),
        ])
        runner.assert_everything_launched()

    def test_enable_resource_running(self):
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_calls_cib_and_status(
                fixture_two_primitives_cib_disabled_both,
                self.fixture_status_stopped,
                fixture_two_primitives_cib_enabled
            )
            +
            fixture_call_wait(10)
            +
            fixture_call_status(
                fixture_state_complete(self.fixture_status_running)
            )
        )

        resource.enable(self.env, ["A", "B"], 10)

        self.env.report_processor.assert_reports([
            fixture_report_resource_running("A", {"Started": ["node1"]}),
            fixture_report_resource_running("B", {"Started": ["node2"]}),
        ])
        runner.assert_everything_launched()

    def test_disable_resource_running(self):
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_calls_cib_and_status(
                fixture_two_primitives_cib_enabled,
                self.fixture_status_running,
                fixture_two_primitives_cib_disabled_both
            )
            +
            fixture_call_wait(10)
            +
            fixture_call_status(
                fixture_state_complete(self.fixture_status_running)
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["A", "B"], 10),
            fixture_report_resource_running(
                "A", {"Started": ["node1"]}, severities.ERROR
            ),
            fixture_report_resource_running(
                "B", {"Started": ["node2"]}, severities.ERROR
            ),
        )
        runner.assert_everything_launched()

    def test_enable_wait_timeout(self):
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_calls_cib_and_status(
                fixture_primitive_cib_disabled,
                self.fixture_status_stopped,
                fixture_primitive_cib_enabled
            )
            +
            fixture_call_wait(
                10, retval=62, stderr=self.fixture_wait_timeout_error
            )
        )

        assert_raise_library_error(
            lambda: resource.enable(self.env, ["A"], 10),
            (
                severities.ERROR,
                report_codes.WAIT_FOR_IDLE_TIMED_OUT,
                {
                    "reason": self.fixture_wait_timeout_error.strip(),
                },
                None
            )
        )
        runner.assert_everything_launched()

    def test_disable_wait_timeout(self):
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_calls_cib_and_status(
                fixture_primitive_cib_enabled,
                self.fixture_status_running,
                fixture_primitive_cib_disabled
            )
            +
            fixture_call_wait(
                10, retval=62, stderr=self.fixture_wait_timeout_error
            )
        )

        assert_raise_library_error(
            lambda: resource.disable(self.env, ["A"], 10),
            (
                severities.ERROR,
                report_codes.WAIT_FOR_IDLE_TIMED_OUT,
                {
                    "reason": self.fixture_wait_timeout_error.strip(),
                },
                None
            )
        )
        runner.assert_everything_launched()


class WaitClone(CommonResourceTest):
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
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_calls_cib_and_status(
                fixture_clone_cib_enabled,
                self.fixture_status_running,
                fixture_clone_cib_disabled_clone
            )
            +
            fixture_call_wait(10)
            +
            fixture_call_status(
                fixture_state_complete(self.fixture_status_stopped)
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
        runner.assert_everything_launched()

    def test_enable_clone(self):
        runner.set_runs(
            fixture_call_wait_supported()
            +
            fixture_calls_cib_and_status(
                fixture_clone_cib_disabled_clone,
                self.fixture_status_stopped,
                fixture_clone_cib_enabled
            )
            +
            fixture_call_wait(10)
            +
            fixture_call_status(
                fixture_state_complete(self.fixture_status_running)
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
        runner.assert_everything_launched()


class DisableGroup(CommonResourceTest):
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


class EnableGroup(CommonResourceTest):
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


class DisableClone(CommonResourceTest):
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


class EnableClone(CommonResourceTest):
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


class DisableMaster(CommonResourceTest):
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


class EnableMaster(CommonResourceTest):
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

class DisableClonedGroup(CommonResourceTest):
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


class EnableClonedGroup(CommonResourceTest):
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

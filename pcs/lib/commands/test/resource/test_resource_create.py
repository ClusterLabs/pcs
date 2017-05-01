from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial
import logging

from lxml import etree

from pcs.test.tools.pcs_unittest import TestCase, mock
from pcs.common import report_codes
from pcs.lib.env import LibraryEnvironment
from pcs.lib.commands import resource
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.lib.commands.test.resource.common import ResourceWithoutStateTest
import pcs.lib.commands.test.resource.fixture as fixture
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.integration_lib import (
    Call,
    Runner,
)
from pcs.test.tools.misc import (
    get_test_resource as rc,
    outdent,
    skip_unless_pacemaker_supports_bundle,
)
from pcs.test.tools.xml import etree_to_str


runner = Runner()

fixture_cib_resources_xml_simplest = """<resources>
    <primitive class="ocf" id="A" provider="heartbeat"
        type="Dummy"
    >
        <operations>
            <op id="A-monitor-interval-10" interval="10" name="monitor"
                timeout="20"
            />
            <op id="A-start-interval-0s" interval="0s" name="start"
                timeout="20"
            />
            <op id="A-stop-interval-0s" interval="0s" name="stop" timeout="20"/>
        </operations>
    </primitive>
</resources>"""

fixture_cib_resources_xml_simplest_disabled = """<resources>
    <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
        <meta_attributes id="A-meta_attributes">
            <nvpair id="A-meta_attributes-target-role" name="target-role"
                value="Stopped"
            />
        </meta_attributes>
        <operations>
            <op id="A-monitor-interval-10" interval="10" name="monitor"
                timeout="20"
            />
            <op id="A-start-interval-0s" interval="0s" name="start"
                timeout="20"
            />
            <op id="A-stop-interval-0s" interval="0s" name="stop" timeout="20"/>
        </operations>
    </primitive>
</resources>"""

fixture_cib_resources_xml_master_simplest = """<resources>
    <master id="A-master">
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <operations>
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-start-interval-0s" interval="0s" name="start"
                    timeout="20"
                />
                <op id="A-stop-interval-0s" interval="0s" name="stop"
                    timeout="20"
                />
            </operations>
        </primitive>
    </master>
</resources>"""


fixture_cib_resources_xml_master_simplest_disabled = """<resources>
    <master id="A-master">
        <meta_attributes id="A-master-meta_attributes">
            <nvpair id="A-master-meta_attributes-target-role" name="target-role"
                value="Stopped"
            />
        </meta_attributes>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <operations>
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-start-interval-0s" interval="0s" name="start"
                    timeout="20"
                />
                <op id="A-stop-interval-0s" interval="0s" name="stop"
                    timeout="20"
                />
            </operations>
        </primitive>
    </master>
</resources>"""

fixture_cib_resources_xml_master_simplest_disabled_meta_after = """<resources>
    <master id="A-master">
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <operations>
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-start-interval-0s" interval="0s" name="start"
                    timeout="20"
                />
                <op id="A-stop-interval-0s" interval="0s" name="stop"
                    timeout="20"
                />
            </operations>
        </primitive>
        <meta_attributes id="A-master-meta_attributes">
            <nvpair id="A-master-meta_attributes-target-role" name="target-role"
                value="Stopped"
            />
        </meta_attributes>
    </master>
</resources>"""

fixture_cib_resources_xml_group_simplest = """<resources>
    <group id="G">
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <operations>
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-start-interval-0s" interval="0s" name="start"
                    timeout="20"
                />
                <op id="A-stop-interval-0s" interval="0s" name="stop"
                    timeout="20"
                />
            </operations>
        </primitive>
    </group>
</resources>"""


fixture_cib_resources_xml_group_simplest_disabled = """<resources>
    <group id="G">
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role" name="target-role"
                    value="Stopped"
                />
            </meta_attributes>
            <operations>
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-start-interval-0s" interval="0s" name="start"
                    timeout="20"
                />
                <op id="A-stop-interval-0s" interval="0s" name="stop"
                    timeout="20"
                />
            </operations>
        </primitive>
    </group>
</resources>"""


fixture_cib_resources_xml_clone_simplest = """<resources>
    <clone id="A-clone">
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <operations>
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-start-interval-0s" interval="0s" name="start"
                    timeout="20"
                />
                <op id="A-stop-interval-0s" interval="0s" name="stop"
                    timeout="20"
                />
            </operations>
        </primitive>
    </clone>
</resources>"""

fixture_cib_resources_xml_clone_simplest_disabled = """<resources>
    <clone id="A-clone">
        <meta_attributes id="A-clone-meta_attributes">
            <nvpair id="A-clone-meta_attributes-target-role"
                name="target-role"
                value="Stopped"
            />
        </meta_attributes>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <operations>
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-start-interval-0s" interval="0s" name="start"
                    timeout="20"
                />
                <op id="A-stop-interval-0s" interval="0s" name="stop"
                    timeout="20"
                />
            </operations>
        </primitive>
    </clone>
</resources>"""

def fixture_state_resources_xml(role="Started", failed="false"):
    return(
        """
        <resources>
            <resource
                id="A"
                resource_agent="ocf::heartbeat:Dummy"
                role="{role}"
                active="true"
                orphaned="false"
                managed="true"
                failed="{failed}"
                failure_ignored="false"
                nodes_running_on="1"
            >
                <node name="node1" id="1" cached="false"/>
            </resource>
        </resources>
        """.format(
            role=role,
            failed=failed,
        )
    )

def fixture_cib_calls(cib_resources_xml):
    cib_xml = open(rc("cib-empty.xml")).read()

    cib = etree.fromstring(cib_xml)
    resources_section = cib.find(".//resources")
    for child in etree.fromstring(cib_resources_xml):
        resources_section.append(child)

    return [
        #TODO everytime we call env.get_cib, we call cibadmin --local --query
        #it is needed to rethink caching cib
        Call("cibadmin --local --query", cib_xml),
        Call("cibadmin --local --query", cib_xml),
        Call("cibadmin --local --query", cib_xml),
        Call(
            "cibadmin --replace --verbose --xml-pipe --scope configuration",
            check_stdin=Call.create_check_stdin_xml(etree_to_str(cib))
        ),
    ]

def fixture_agent_load_calls():
    return [
        Call(
            "crm_resource --show-metadata ocf:heartbeat:Dummy",
            open(rc("resource_agent_ocf_heartbeat_dummy.xml")).read()
        ),
    ]


def fixture_pre_timeout_calls(cib_resources_xml):
    return (
        fixture_agent_load_calls()
        +
        [
            Call("crm_resource -?", "--wait"),
        ]
        +
        fixture_cib_calls(cib_resources_xml)
    )

def fixture_wait_and_get_state_calls(state_resource_xml):
    crm_mon = etree.fromstring(open(rc("crm_mon.minimal.xml")).read())
    crm_mon.append(etree.fromstring(state_resource_xml))

    return [
        Call("crm_resource --wait --timeout=10"),
        Call(
            "crm_mon --one-shot --as-xml --inactive",
            etree_to_str(crm_mon),
        ),
    ]

def fixture_calls_including_waiting(cib_resources_xml, state_resources_xml):
    return (
        fixture_pre_timeout_calls(cib_resources_xml)
        +
        fixture_wait_and_get_state_calls(state_resources_xml)
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
        self.create = partial(self.get_create(), self.env)

    def assert_command_effect(self, cmd, cib_resources_xml, reports=None):
        runner.set_runs(
            fixture_agent_load_calls()
            +
            fixture_cib_calls(cib_resources_xml)
        )
        cmd()
        self.env.report_processor.assert_reports(reports if reports else [])
        runner.assert_everything_launched()

    def assert_wait_fail(self, command, cib_resources_xml):
        wait_error_message = outdent(
            """\
            Pending actions:
                    Action 39: stonith-vm-rhel72-1-reboot  on vm-rhel72-1
            Error performing operation: Timer expired
            """
        )

        runner.set_runs(fixture_pre_timeout_calls(cib_resources_xml) + [
            Call(
                "crm_resource --wait --timeout=10",
                stderr=wait_error_message,
                returncode=62,
            ),
        ])

        assert_raise_library_error(
            command,
            (
                severities.ERROR,
                report_codes.WAIT_FOR_IDLE_TIMED_OUT,
                {
                    "reason": wait_error_message.strip(),
                },
                None
            )
        )
        runner.assert_everything_launched()

    def assert_wait_ok_run_fail(
        self, command, cib_resources_xml, state_resources_xml
    ):
        runner.set_runs(fixture_calls_including_waiting(
            cib_resources_xml,
            state_resources_xml
        ))

        assert_raise_library_error(
            command,
            (
                severities.ERROR,
                report_codes.RESOURCE_DOES_NOT_RUN,
                {
                    "resource_id": "A",
                },
                None
            )
        )
        runner.assert_everything_launched()

    def assert_wait_ok_run_ok(
        self, command, cib_resources_xml, state_resources_xml
    ):
        runner.set_runs(fixture_calls_including_waiting(
            cib_resources_xml,
            state_resources_xml
        ))
        command()
        self.env.report_processor.assert_reports([
            (
                severities.INFO,
                report_codes.RESOURCE_RUNNING_ON_NODES,
                {
                    "roles_with_nodes": {"Started": ["node1"]},
                    "resource_id": "A",
                },
                None
            ),
        ])
        runner.assert_everything_launched()

    def assert_wait_ok_disable_fail(
        self, command, cib_resources_xml, state_resources_xml
    ):
        runner.set_runs(fixture_calls_including_waiting(
            cib_resources_xml,
            state_resources_xml
        ))

        assert_raise_library_error(
            command,
            (
                severities.ERROR,
                report_codes.RESOURCE_RUNNING_ON_NODES,
                {
                    'roles_with_nodes': {'Started': ['node1']},
                    'resource_id': 'A'
                },
                None
            )
        )
        runner.assert_everything_launched()

    def assert_wait_ok_disable_ok(
        self, command, cib_resources_xml, state_resources_xml
    ):
        runner.set_runs(fixture_calls_including_waiting(
            cib_resources_xml,
            state_resources_xml
        ))
        command()
        self.env.report_processor.assert_reports([
            (
                severities.INFO,
                report_codes.RESOURCE_DOES_NOT_RUN,
                {
                    "resource_id": "A",
                },
                None
            ),
        ])
        runner.assert_everything_launched()

class Create(CommonResourceTest):
    def get_create(self):
        return resource.create

    def simplest_create(self, wait=False, disabled=False, meta_attributes=None):
        return self.create(
            "A", "ocf:heartbeat:Dummy",
            operations=[],
            meta_attributes=meta_attributes if meta_attributes else {},
            instance_attributes={},
            wait=wait,
            ensure_disabled=disabled
        )

    def test_simplest_resource(self):
        self.assert_command_effect(
            self.simplest_create,
            fixture_cib_resources_xml_simplest
        )

    def test_resource_with_operation(self):
        self.assert_command_effect(
            lambda: self.create(
                "A", "ocf:heartbeat:Dummy",
                operations=[
                    {"name": "monitor", "timeout": "10s", "interval": "10"}
                ],
                meta_attributes={},
                instance_attributes={},
            ),
            """<resources>
                <primitive class="ocf" id="A" provider="heartbeat"
                    type="Dummy"
                >
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor" timeout="10s"
                        />
                        <op id="A-start-interval-0s" interval="0s"
                            name="start" timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s"
                            name="stop" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_fail_wait(self):
        self.assert_wait_fail(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_simplest,
        )

    def test_wait_ok_run_fail(self):
        self.assert_wait_ok_run_fail(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_simplest,
            fixture_state_resources_xml(failed="true"),
        )

    def test_wait_ok_run_ok(self):
        self.assert_wait_ok_run_ok(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_simplest,
            fixture_state_resources_xml(),
        )

    def test_wait_ok_disable_fail(self):
        self.assert_wait_ok_disable_fail(
            lambda: self.simplest_create(wait="10", disabled=True),
            fixture_cib_resources_xml_simplest_disabled,
            fixture_state_resources_xml(),
        )

    def test_wait_ok_disable_ok(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(wait="10", disabled=True),
            fixture_cib_resources_xml_simplest_disabled,
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_target_role(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                meta_attributes={"target-role": "Stopped"}
            ),
            fixture_cib_resources_xml_simplest_disabled,
            fixture_state_resources_xml(role="Stopped"),
        )

class CreateAsMaster(CommonResourceTest):
    def get_create(self):
        return resource.create_as_master

    def simplest_create(
        self, wait=False, disabled=False, meta_attributes=None,
        master_meta_options=None
    ):
        return self.create(
            "A", "ocf:heartbeat:Dummy",
            operations=[],
            meta_attributes=meta_attributes if meta_attributes else {},
            instance_attributes={},
            clone_meta_options=master_meta_options if master_meta_options
                else {}
            ,
            wait=wait,
            ensure_disabled=disabled
        )

    def test_simplest_resource(self):
        self.assert_command_effect(
            self.simplest_create,
            fixture_cib_resources_xml_master_simplest
        )

    def test_fail_wait(self):
        self.assert_wait_fail(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_master_simplest,
        )

    def test_wait_ok_run_fail(self):
        self.assert_wait_ok_run_fail(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_master_simplest,
            fixture_state_resources_xml(failed="true"),
        )

    def test_wait_ok_run_ok(self):
        self.assert_wait_ok_run_ok(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_master_simplest,
            fixture_state_resources_xml(),
        )

    def test_wait_ok_disable_fail(self):
        self.assert_wait_ok_disable_fail(
            lambda: self.simplest_create(wait="10", disabled=True),
            fixture_cib_resources_xml_master_simplest_disabled,
            fixture_state_resources_xml(),
        )

    def test_wait_ok_disable_ok(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(wait="10", disabled=True),
            fixture_cib_resources_xml_master_simplest_disabled,
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_target_role(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                meta_attributes={"target-role": "Stopped"}
            ),
            """<resources>
            <master id="A-master">
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
            </master>
            </resources>""",
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_target_role_in_master(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                master_meta_options={"target-role": "Stopped"}
            ),
            fixture_cib_resources_xml_master_simplest_disabled_meta_after,
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_clone_max(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                master_meta_options={"clone-max": "0"}
            ),
            """<resources>
            <master id="A-master">
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor"
                            timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
                <meta_attributes id="A-master-meta_attributes">
                    <nvpair id="A-master-meta_attributes-clone-max"
                        name="clone-max" value="0"
                    />
                </meta_attributes>
            </master>
        </resources>""",
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_clone_node_max(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                master_meta_options={"clone-node-max": "0"}
            ),
            """<resources>
            <master id="A-master">
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor"
                            timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
                <meta_attributes id="A-master-meta_attributes">
                    <nvpair id="A-master-meta_attributes-clone-node-max"
                        name="clone-node-max" value="0"
                    />
                </meta_attributes>
            </master>
        </resources>""",
            fixture_state_resources_xml(role="Stopped"),
        )

class CreateInGroup(CommonResourceTest):
    def get_create(self):
        return resource.create_in_group

    def simplest_create(self, wait=False, disabled=False, meta_attributes=None):
        return self.create(
            "A", "ocf:heartbeat:Dummy", "G",
            operations=[],
            meta_attributes=meta_attributes if meta_attributes else {},
            instance_attributes={},
            wait=wait,
            ensure_disabled=disabled
        )

    def test_simplest_resource(self):
        self.assert_command_effect(self.simplest_create, """<resources>
            <group id="G">
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
            </group>
        </resources>""")

    def test_fail_wait(self):
        self.assert_wait_fail(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_group_simplest,
        )

    def test_wait_ok_run_fail(self):
        self.assert_wait_ok_run_fail(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_group_simplest,
            fixture_state_resources_xml(failed="true"),
        )

    def test_wait_ok_run_ok(self):
        self.assert_wait_ok_run_ok(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_group_simplest,
            fixture_state_resources_xml(),
        )

    def test_wait_ok_disable_fail(self):
        self.assert_wait_ok_disable_fail(
            lambda: self.simplest_create(wait="10", disabled=True),
            fixture_cib_resources_xml_group_simplest_disabled,
            fixture_state_resources_xml(),
        )

    def test_wait_ok_disable_ok(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(wait="10", disabled=True),
            fixture_cib_resources_xml_group_simplest_disabled,
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_target_role(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                meta_attributes={"target-role": "Stopped"}
            ),
            fixture_cib_resources_xml_group_simplest_disabled,
            fixture_state_resources_xml(role="Stopped"),
        )

class CreateAsClone(CommonResourceTest):
    def get_create(self):
        return resource.create_as_clone

    def simplest_create(
        self, wait=False, disabled=False, meta_attributes=None,
        clone_options=None
    ):
        return self.create(
            "A", "ocf:heartbeat:Dummy",
            operations=[],
            meta_attributes=meta_attributes if meta_attributes else {},
            instance_attributes={},
            clone_meta_options=clone_options if clone_options else {},
            wait=wait,
            ensure_disabled=disabled
        )

    def test_simplest_resource(self):
        self.assert_command_effect(
            self.simplest_create,
            fixture_cib_resources_xml_clone_simplest
        )

    def test_fail_wait(self):
        self.assert_wait_fail(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_clone_simplest,
        )

    def test_wait_ok_run_fail(self):
        self.assert_wait_ok_run_fail(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_clone_simplest,
            fixture_state_resources_xml(failed="true"),
        )

    def test_wait_ok_run_ok(self):
        self.assert_wait_ok_run_ok(
            lambda: self.simplest_create(wait="10"),
            fixture_cib_resources_xml_clone_simplest,
            fixture_state_resources_xml(),
        )

    def test_wait_ok_disable_fail(self):
        self.assert_wait_ok_disable_fail(
            lambda: self.simplest_create(wait="10", disabled=True),
            fixture_cib_resources_xml_clone_simplest_disabled,
            fixture_state_resources_xml(),
        )

    def test_wait_ok_disable_ok(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(wait="10", disabled=True),
            fixture_cib_resources_xml_clone_simplest_disabled,
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_target_role(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                meta_attributes={"target-role": "Stopped"}
            ),
            """<resources>
            <clone id="A-clone">
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-target-role"
                            name="target-role"
                            value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
            </clone>
        </resources>"""
        ,
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_target_role_in_clone(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                clone_options={"target-role": "Stopped"}
            ),
            """<resources>
            <clone id="A-clone">
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor"
                            timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
                <meta_attributes id="A-clone-meta_attributes">
                    <nvpair id="A-clone-meta_attributes-target-role"
                        name="target-role" value="Stopped"
                    />
                </meta_attributes>
            </clone>
            </resources>""",
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_clone_max(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                clone_options={"clone-max": "0"}
            ),
            """<resources>
            <clone id="A-clone">
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor"
                            timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
                <meta_attributes id="A-clone-meta_attributes">
                    <nvpair id="A-clone-meta_attributes-clone-max"
                        name="clone-max" value="0"
                    />
                </meta_attributes>
            </clone>
            </resources>""",
            fixture_state_resources_xml(role="Stopped"),
        )

    def test_wait_ok_disable_ok_by_clone_node_max(self):
        self.assert_wait_ok_disable_ok(
            lambda: self.simplest_create(
                wait="10",
                clone_options={"clone-node-max": "0"}
            ),
            """<resources>
            <clone id="A-clone">
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor"
                            timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s" name="start"
                            timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s" name="stop"
                            timeout="20"
                        />
                    </operations>
                </primitive>
                <meta_attributes id="A-clone-meta_attributes">
                    <nvpair id="A-clone-meta_attributes-clone-node-max"
                        name="clone-node-max" value="0"
                    />
                </meta_attributes>
            </clone>
            </resources>""",
            fixture_state_resources_xml(role="Stopped"),
        )


class CreateInToBundle(ResourceWithoutStateTest):
    upgraded_cib = "cib-empty-2.8.xml"

    fixture_empty_resources = "<resources />"

    fixture_resources_pre = """
        <resources>
            <bundle id="B"/>
        </resources>
    """

    fixture_resources_post_simple = """
        <resources>
            <bundle id="B">
                <primitive
                    class="ocf" id="A" provider="heartbeat" type="Dummy"
                >
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s"
                            name="start" timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s"
                            name="stop" timeout="20"
                        />
                    </operations>
                </primitive>
            </bundle>
        </resources>
    """

    fixture_resources_post_disabled = """
        <resources>
            <bundle id="B">
                <primitive
                    class="ocf" id="A" provider="heartbeat" type="Dummy"
                >
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="A-start-interval-0s" interval="0s"
                            name="start" timeout="20"
                        />
                        <op id="A-stop-interval-0s" interval="0s"
                            name="stop" timeout="20"
                        />
                    </operations>
                </primitive>
            </bundle>
        </resources>
    """

    fixture_status_stopped = """
        <resources>
            <bundle id="B" managed="true">
                <replica id="0">
                    <resource id="B-0" managed="true" role="Stopped" />
                </replica>
            </bundle>
        </resources>
    """

    fixture_status_running_with_primitive = """
        <resources>
            <bundle id="B" managed="true">
                <replica id="0">
                    <resource id="B-0" managed="true" role="Started">
                        <node name="node1" id="1" cached="false"/>
                    </resource>
                    <resource id="A" managed="true" role="Started">
                        <node name="node1" id="1" cached="false"/>
                    </resource>
                </replica>
            </bundle>
        </resources>
    """

    fixture_status_primitive_not_running = """
        <resources>
            <bundle id="B" managed="true">
                <replica id="0">
                    <resource id="B-0" managed="true" role="Started">
                        <node name="node1" id="1" cached="false"/>
                    </resource>
                    <resource id="A" managed="true" role="Stopped"/>
                </replica>
            </bundle>
        </resources>
    """

    fixture_wait_timeout_error = outdent(
        """\
        Pending actions:
                Action 12: B-node2-stop on node2
        Error performing operation: Timer expired
        """
    )

    def simplest_create(self, wait=False, disabled=False, meta_attributes=None):
        return resource.create_into_bundle(
            self.env,
            "A", "ocf:heartbeat:Dummy",
            operations=[],
            meta_attributes=meta_attributes if meta_attributes else {},
            instance_attributes={},
            bundle_id="B",
            wait=wait,
            ensure_disabled=disabled
        )

    def test_upgrade_cib(self):
        self.runner.set_runs(
            fixture_agent_load_calls()
            +
            fixture.calls_cib_load_and_upgrade(self.fixture_empty_resources)
            +
            fixture.calls_cib(
                self.fixture_resources_pre,
                self.fixture_resources_post_simple,
                self.upgraded_cib,
            )
        )
        self.simplest_create()
        self.runner.assert_everything_launched()

    def test_simplest_resource(self):
        self.runner.set_runs(
            fixture_agent_load_calls()
            +
            fixture.calls_cib(
                self.fixture_resources_pre,
                self.fixture_resources_post_simple,
                self.upgraded_cib,
            )
        )
        self.simplest_create()
        self.runner.assert_everything_launched()

    def test_bundle_doesnt_exist(self):
        self.runner.set_runs(
            fixture_agent_load_calls()
            +
            fixture.call_cib_load(fixture.cib_resources(
                self.fixture_empty_resources, self.upgraded_cib,
            ))
        )
        assert_raise_library_error(
            self.simplest_create,
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "B",
                    "id_description": "bundle",
                    "context_type": "resources",
                    "context_id": "",
                }
            )
        )

    def test_id_not_bundle(self):
        resources_pre_update = """<resources>
            <primitive id="B"/>
        </resources>"""
        self.runner.set_runs(
            fixture_agent_load_calls()
            +
            fixture.call_cib_load(fixture.cib_resources(
                resources_pre_update, self.upgraded_cib,
            ))
        )
        assert_raise_library_error(
            self.simplest_create,
            (
                severities.ERROR,
                report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                {
                    "id": "B",
                    "expected_types": ["bundle"],
                    "current_type": "primitive",
                }
            )
        )

    def test_bundle_not_empty(self):
        resources_pre_update = """<resources>
            <bundle id="B">
                <primitive id="P"/>
            </bundle>
        </resources>"""
        self.runner.set_runs(
            fixture_agent_load_calls()
            +
            fixture.call_cib_load(fixture.cib_resources(
                resources_pre_update, self.upgraded_cib,
            ))
        )
        assert_raise_library_error(
            self.simplest_create,
            (
                severities.ERROR,
                report_codes.RESOURCE_BUNDLE_ALREADY_CONTAINS_A_RESOURCE,
                {
                    "bundle_id": "B",
                    "resource_id": "P",
                }
            )
        )

    def test_wait_fail(self):
        self.runner.set_runs(
            fixture.call_dummy_metadata() +
            fixture.call_wait_supported() +
            fixture.calls_cib(
                self.fixture_resources_pre,
                self.fixture_resources_post_simple,
                cib_base_file=self.upgraded_cib,
            ) +
            fixture.call_wait(10, 62, self.fixture_wait_timeout_error)
        )
        assert_raise_library_error(
            lambda: self.simplest_create(10),
            fixture.report_wait_for_idle_timed_out(
                self.fixture_wait_timeout_error
            ),
        )
        self.runner.assert_everything_launched()

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_run_ok(self):
        self.runner.set_runs(
            fixture.call_dummy_metadata() +
            fixture.call_wait_supported() +
            fixture.calls_cib(
                self.fixture_resources_pre,
                self.fixture_resources_post_simple,
                cib_base_file=self.upgraded_cib,
            ) +
            fixture.call_wait(10) +
            fixture.call_status(fixture.state_complete(
                self.fixture_status_running_with_primitive
            ))
        )
        self.simplest_create(10)
        self.env.report_processor.assert_reports([
            fixture.report_resource_running("A", {"Started": ["node1"]}),
        ])
        self.runner.assert_everything_launched()

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_run_fail(self):
        self.runner.set_runs(
            fixture.call_dummy_metadata() +
            fixture.call_wait_supported() +
            fixture.calls_cib(
                self.fixture_resources_pre,
                self.fixture_resources_post_simple,
                cib_base_file=self.upgraded_cib,
            ) +
            fixture.call_wait(10) +
            fixture.call_status(fixture.state_complete(
                self.fixture_status_primitive_not_running
            ))
        )
        assert_raise_library_error(
            lambda: self.simplest_create(10),
            fixture.report_resource_not_running("A", severities.ERROR),
        )
        self.runner.assert_everything_launched()

    @skip_unless_pacemaker_supports_bundle
    def test_disabled_wait_ok_not_running(self):
        self.runner.set_runs(
            fixture.call_dummy_metadata() +
            fixture.call_wait_supported() +
            fixture.calls_cib(
                self.fixture_resources_pre,
                self.fixture_resources_post_disabled,
                cib_base_file=self.upgraded_cib,
            ) +
            fixture.call_wait(10) +
            fixture.call_status(fixture.state_complete(
                self.fixture_status_primitive_not_running
            ))
        )
        self.simplest_create(10, disabled=True)
        self.env.report_processor.assert_reports([
            fixture.report_resource_not_running("A")
        ])
        self.runner.assert_everything_launched()

    @skip_unless_pacemaker_supports_bundle
    def test_disabled_wait_ok_running(self):
        self.runner.set_runs(
            fixture.call_dummy_metadata() +
            fixture.call_wait_supported() +
            fixture.calls_cib(
                self.fixture_resources_pre,
                self.fixture_resources_post_disabled,
                cib_base_file=self.upgraded_cib,
            ) +
            fixture.call_wait(10) +
            fixture.call_status(fixture.state_complete(
                self.fixture_status_running_with_primitive
            ))
        )
        assert_raise_library_error(
            lambda: self.simplest_create(10, disabled=True),
            fixture.report_resource_running(
                "A", {"Started": ["node1"]}, severities.ERROR
            ),
        )
        self.runner.assert_everything_launched()

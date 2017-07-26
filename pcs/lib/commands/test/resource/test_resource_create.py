from __future__ import (
    absolute_import,
    division,
    print_function,
)

from functools import partial

from pcs.common import report_codes
from pcs.lib.commands import resource
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.misc import (
    outdent,
    skip_unless_pacemaker_supports_bundle,
)
from pcs.test.tools.pcs_unittest import TestCase


TIMEOUT=10

get_env_tools = partial(
    get_env_tools,
    default_wait_timeout=TIMEOUT
)

def create(
    env, wait=False, disabled=False, meta_attributes=None, operations=None
):
    return resource.create(
        env,
        "A", "ocf:heartbeat:Dummy",
        operations=operations if operations else [],
        meta_attributes=meta_attributes if meta_attributes else {},
        instance_attributes={},
        wait=wait,
        ensure_disabled=disabled
    )

def create_master(
    env, wait=TIMEOUT, disabled=False, meta_attributes=None,
    master_meta_options=None
):
    return resource.create_as_master(
        env,
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
def create_group(env, wait=TIMEOUT, disabled=False, meta_attributes=None):
    return resource.create_in_group(
        env,
        "A", "ocf:heartbeat:Dummy", "G",
        operations=[],
        meta_attributes=meta_attributes if meta_attributes else {},
        instance_attributes={},
        wait=wait,
        ensure_disabled=disabled
    )

def create_clone(
    env, wait=TIMEOUT, disabled=False, meta_attributes=None, clone_options=None
):
    return resource.create_as_clone(
        env,
        "A", "ocf:heartbeat:Dummy",
        operations=[],
        meta_attributes=meta_attributes if meta_attributes else {},
        instance_attributes={},
        clone_meta_options=clone_options if clone_options else {},
        wait=wait,
        ensure_disabled=disabled
    )

def create_bundle(env, wait=TIMEOUT, disabled=False, meta_attributes=None):
    return resource.create_into_bundle(
        env,
        "A", "ocf:heartbeat:Dummy",
        operations=[],
        meta_attributes=meta_attributes if meta_attributes else {},
        instance_attributes={},
        bundle_id="B",
        wait=wait,
        ensure_disabled=disabled
    )

wait_error_message = outdent(
    """\
    Pending actions:
            Action 39: stonith-vm-rhel72-1-reboot  on vm-rhel72-1
    Error performing operation: Timer expired
    """
)

fixture_cib_resources_xml_primitive_simplest = """
    <resources>
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
    </resources>
"""

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

class Create(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config
            .runner.pcmk.load_agent()
            .runner.cib.load()
        )

    def test_simplest_resource(self):
        self.config.runner.cib.push(
            resources=fixture_cib_resources_xml_primitive_simplest
        )
        return create(self.env_assist.get_env())

    def test_resource_with_operation(self):
        self.config.runner.cib.push(
            resources="""
                <resources>
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
                </resources>
            """
        )

        create(
            self.env_assist.get_env(),
            operations=[
                {"name": "monitor", "timeout": "10s", "interval": "10"}
            ]
        )

class CreateWait(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config
            .runner.pcmk.load_agent()
            .runner.pcmk.can_wait()
            .runner.cib.load()
            .runner.cib.push(
                resources=fixture_cib_resources_xml_primitive_simplest
            )
        )

    def test_fail_wait(self):
        self.config.runner.pcmk.wait(stderr=wait_error_message)
        self.env_assist.assert_raise_library_error(
            lambda: create(self.env_assist.get_env(), wait="10"),
            [
                fixture.report_wait_for_idle_timed_out(wait_error_message)
            ],
            expected_in_processor=False
        )

    def test_wait_ok_run_fail(self):
        (self.config
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(failed="true")
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: create(self.env_assist.get_env(), wait="10"),
            [
                fixture.error(
                    report_codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                )
            ]
        )

    def test_wait_ok_run_ok(self):
        (self.config
            .runner.pcmk.wait()
            .runner.pcmk.load_state(resources=fixture_state_resources_xml())
        )
        create(self.env_assist.get_env(), wait="10")
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_RUNNING_ON_NODES,
                roles_with_nodes={"Started": ["node1"]},
                resource_id="A",
            ),
        ])

    def test_wait_ok_disable_fail(self):
        (self.config
            .runner.pcmk.wait()
            .runner.pcmk.load_state(resources=fixture_state_resources_xml())
            .runner.cib.push(
                resources=fixture_cib_resources_xml_simplest_disabled,
                instead="push_cib"
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: create(
                self.env_assist.get_env(),
                wait="10",
                disabled=True
            ),
            [
                fixture.error(
                    report_codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": ["node1"]},
                    resource_id="A",
                ),
            ]
        )

    def test_wait_ok_disable_ok(self):
        (self.config
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
            .runner.cib.push(
                resources=fixture_cib_resources_xml_simplest_disabled,
                instead="push_cib"
            )
        )

        create(self.env_assist.get_env(), wait="10", disabled=True)
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_target_role(self):
        (self.config
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
            .runner.cib.push(
                resources=fixture_cib_resources_xml_simplest_disabled,
                instead="push_cib"
            )
        )
        create(
            self.env_assist.get_env(),
            wait="10",
            meta_attributes={"target-role": "Stopped"}
        )

        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

class CreateAsMaster(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config
            .runner.pcmk.load_agent()
            .runner.pcmk.can_wait()
            .runner.cib.load()
        )

    def test_simplest_resource(self):
        (self.config
            .remove(name="can_wait")
            .runner.cib.push(
                resources=fixture_cib_resources_xml_master_simplest
            )
        )
        create_master(self.env_assist.get_env(), wait=False)

    def test_fail_wait(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_master_simplest
            )
            .runner.pcmk.wait(stderr=wait_error_message)
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_master(self.env_assist.get_env()),
            [
                fixture.report_wait_for_idle_timed_out(wait_error_message)
            ],
            expected_in_processor=False
        )

    def test_wait_ok_run_fail(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_master_simplest
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(failed="true")
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_master(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A"
                )
            ]
        )

    def test_wait_ok_run_ok(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_master_simplest
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml()
            )
        )
        create_master(self.env_assist.get_env())
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_RUNNING_ON_NODES,
                roles_with_nodes={"Started": ["node1"]},
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_fail(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_master_simplest_disabled
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml()
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_master(self.env_assist.get_env(), disabled=True),
            [
                fixture.error(
                    report_codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={'Started': ['node1']},
                    resource_id='A'
                )
            ],
        )

    def test_wait_ok_disable_ok(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_master_simplest_disabled
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_master(self.env_assist.get_env(), disabled=True)
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_target_role(self):
        (self.config
            .runner.cib.push(
                resources="""
                    <resources>
                        <master id="A-master">
                            <primitive class="ocf" id="A" provider="heartbeat"
                                type="Dummy"
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
                        </master>
                    </resources>
                """
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_master(
            self.env_assist.get_env(),
            meta_attributes={"target-role": "Stopped"}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_target_role_in_master(self):
        (self.config
            .runner.cib.push(resources
                =fixture_cib_resources_xml_master_simplest_disabled_meta_after
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_master(
            self.env_assist.get_env(),
            master_meta_options={"target-role": "Stopped"}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_clone_max(self):
        (self.config
            .runner.cib.push(
                resources="""
                    <resources>
                        <master id="A-master">
                            <primitive class="ocf" id="A" provider="heartbeat"
                                type="Dummy"
                            >
                                <operations>
                                    <op id="A-monitor-interval-10" interval="10"
                                        name="monitor"
                                        timeout="20"
                                    />
                                    <op id="A-start-interval-0s" interval="0s"
                                        name="start" timeout="20"
                                    />
                                    <op id="A-stop-interval-0s" interval="0s"
                                        name="stop" timeout="20"
                                    />
                                </operations>
                            </primitive>
                            <meta_attributes id="A-master-meta_attributes">
                                <nvpair id="A-master-meta_attributes-clone-max"
                                    name="clone-max" value="0"
                                />
                            </meta_attributes>
                        </master>
                    </resources>
                """
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_master(
            self.env_assist.get_env(),
            master_meta_options={"clone-max": "0"}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_clone_node_max(self):
        (self.config
            .runner.cib.push(
                resources="""
                    <resources>
                        <master id="A-master">
                            <primitive class="ocf" id="A" provider="heartbeat"
                                type="Dummy"
                            >
                                <operations>
                                    <op id="A-monitor-interval-10" interval="10"
                                        name="monitor"
                                        timeout="20"
                                    />
                                    <op id="A-start-interval-0s" interval="0s"
                                        name="start" timeout="20"
                                    />
                                    <op id="A-stop-interval-0s" interval="0s"
                                        name="stop" timeout="20"
                                    />
                                </operations>
                            </primitive>
                            <meta_attributes id="A-master-meta_attributes">
                                <nvpair
                                    id="A-master-meta_attributes-clone-node-max"
                                    name="clone-node-max" value="0"
                                />
                            </meta_attributes>
                        </master>
                    </resources>
                """
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_master(
            self.env_assist.get_env(),
            master_meta_options={"clone-node-max": "0"}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

class CreateInGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config
            .runner.pcmk.load_agent()
            .runner.pcmk.can_wait()
            .runner.cib.load()
        )

    def test_simplest_resource(self):
        (self.config
            .remove(name="can_wait")
            .runner.cib.push(
                resources="""
                    <resources>
                        <group id="G">
                            <primitive class="ocf" id="A" provider="heartbeat"
                                type="Dummy"
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
                        </group>
                    </resources>
                """
            )
        )

        create_group(self.env_assist.get_env(), wait=False)

    def test_fail_wait(self):
        (self.config
            .runner.cib.push(resources=fixture_cib_resources_xml_group_simplest)
            .runner.pcmk.wait(stderr=wait_error_message)
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_group(self.env_assist.get_env()),
            [
                fixture.report_wait_for_idle_timed_out(wait_error_message)
            ],
            expected_in_processor=False
        )

    def test_wait_ok_run_fail(self):
        (self.config
            .runner.cib.push(resources=fixture_cib_resources_xml_group_simplest)
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(failed="true")
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_group(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A"
                )
            ]
        )

    def test_wait_ok_run_ok(self):
        (self.config
            .runner.cib.push(resources=fixture_cib_resources_xml_group_simplest)
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml()
            )
        )
        create_group(self.env_assist.get_env())
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_RUNNING_ON_NODES,
                roles_with_nodes={"Started": ["node1"]},
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_fail(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_group_simplest_disabled
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml()
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_group(self.env_assist.get_env(), disabled=True),
            [
                fixture.error(
                    report_codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={'Started': ['node1']},
                    resource_id='A'
                )
            ],
        )

    def test_wait_ok_disable_ok(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_group_simplest_disabled
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_group(self.env_assist.get_env(), disabled=True)
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_target_role(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_group_simplest_disabled
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_group(
            self.env_assist.get_env(),
            meta_attributes={"target-role": "Stopped"}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

class CreateAsClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config
            .runner.pcmk.load_agent()
            .runner.pcmk.can_wait()
            .runner.cib.load()
        )

    def test_simplest_resource(self):
        (self.config
            .remove(name="can_wait")
            .runner.cib.push(resources=fixture_cib_resources_xml_clone_simplest)
        )
        create_clone(self.env_assist.get_env(), wait=False)

    def test_fail_wait(self):
        (self.config
            .runner.cib.push(resources=fixture_cib_resources_xml_clone_simplest)
            .runner.pcmk.wait(stderr=wait_error_message)
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_clone(self.env_assist.get_env()),
            [
                fixture.report_wait_for_idle_timed_out(wait_error_message)
            ],
            expected_in_processor=False
        )

    def test_wait_ok_run_fail(self):
        (self.config
            .runner.cib.push(resources=fixture_cib_resources_xml_clone_simplest)
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(failed="true")
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_clone(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A"
                )
            ]
        )

    def test_wait_ok_run_ok(self):
        (self.config
            .runner.cib.push(resources=fixture_cib_resources_xml_clone_simplest)
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml()
            )
        )
        create_clone(self.env_assist.get_env())
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_RUNNING_ON_NODES,
                roles_with_nodes={"Started": ["node1"]},
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_fail(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_clone_simplest_disabled
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml()
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_clone(self.env_assist.get_env(), disabled=True),
            [
                fixture.error(
                    report_codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={'Started': ['node1']},
                    resource_id='A'
                )
            ],
        )

    def test_wait_ok_disable_ok(self):
        (self.config
            .runner.cib.push(
                resources=fixture_cib_resources_xml_clone_simplest_disabled
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_clone(self.env_assist.get_env(), disabled=True)
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_target_role(self):
        (self.config
            .runner.cib.push(
                resources="""
                    <resources>
                        <clone id="A-clone">
                            <primitive class="ocf" id="A" provider="heartbeat"
                                type="Dummy"
                            >
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
                                    <op id="A-start-interval-0s" interval="0s"
                                        name="start" timeout="20"
                                    />
                                    <op id="A-stop-interval-0s" interval="0s"
                                        name="stop" timeout="20"
                                    />
                                </operations>
                            </primitive>
                        </clone>
                    </resources>
                """
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_clone(
            self.env_assist.get_env(),
            meta_attributes={"target-role": "Stopped"}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_target_role_in_clone(self):
        (self.config
            .runner.cib.push(
                resources="""
                    <resources>
                        <clone id="A-clone">
                            <primitive class="ocf" id="A" provider="heartbeat"
                                type="Dummy"
                            >
                                <operations>
                                    <op id="A-monitor-interval-10" interval="10"
                                        name="monitor"
                                        timeout="20"
                                    />
                                    <op id="A-start-interval-0s" interval="0s"
                                        name="start" timeout="20"
                                    />
                                    <op id="A-stop-interval-0s" interval="0s"
                                        name="stop" timeout="20"
                                    />
                                </operations>
                            </primitive>
                            <meta_attributes id="A-clone-meta_attributes">
                                <nvpair id="A-clone-meta_attributes-target-role"
                                    name="target-role" value="Stopped"
                                />
                            </meta_attributes>
                        </clone>
                    </resources>
                """
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_clone(
            self.env_assist.get_env(),
            clone_options={"target-role": "Stopped"}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_clone_max(self):
        (self.config
            .runner.cib.push(
                resources="""
                    <resources>
                        <clone id="A-clone">
                            <primitive class="ocf" id="A" provider="heartbeat"
                                type="Dummy"
                            >
                                <operations>
                                    <op id="A-monitor-interval-10" interval="10"
                                        name="monitor"
                                        timeout="20"
                                    />
                                    <op id="A-start-interval-0s" interval="0s"
                                        name="start" timeout="20"
                                    />
                                    <op id="A-stop-interval-0s" interval="0s"
                                        name="stop" timeout="20"
                                    />
                                </operations>
                            </primitive>
                            <meta_attributes id="A-clone-meta_attributes">
                                <nvpair id="A-clone-meta_attributes-clone-max"
                                    name="clone-max" value="0"
                                />
                            </meta_attributes>
                        </clone>
                    </resources>
                """
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_clone(
            self.env_assist.get_env(),
            clone_options={"clone-max": "0"}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

    def test_wait_ok_disable_ok_by_clone_node_max(self):
        (self.config
            .runner.cib.push(
                resources="""
                    <resources>
                        <clone id="A-clone">
                            <primitive class="ocf" id="A" provider="heartbeat"
                                type="Dummy"
                            >
                                <operations>
                                    <op id="A-monitor-interval-10" interval="10"
                                        name="monitor"
                                        timeout="20"
                                    />
                                    <op id="A-start-interval-0s" interval="0s"
                                        name="start" timeout="20"
                                    />
                                    <op id="A-stop-interval-0s" interval="0s"
                                        name="stop" timeout="20"
                                    />
                                </operations>
                            </primitive>
                            <meta_attributes id="A-clone-meta_attributes">
                                <nvpair
                                    id="A-clone-meta_attributes-clone-node-max"
                                    name="clone-node-max" value="0"
                                />
                            </meta_attributes>
                        </clone>
                    </resources>
                """
            )
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            )
        )
        create_clone(
            self.env_assist.get_env(),
            clone_options={"clone-node-max": "0"}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_DOES_NOT_RUN,
                resource_id="A",
            )
        ])

class CreateInToBundle(TestCase):
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

    def setUp(self):
        self.env_assist, self.config = get_env_tools(
            test_case=self,
            base_cib_filename="cib-empty-2.8.xml",
        )

    def test_upgrade_cib(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.cib.load(
                filename="cib-empty.xml",
                name="load_cib_old_version"
            )
            .runner.cib.upgrade()
            .runner.cib.load(resources=self.fixture_resources_pre)
            .runner.cib.push(resources=self.fixture_resources_post_simple)
        )
        create_bundle(self.env_assist.get_env(), wait=False)
        self.env_assist.assert_reports([
            fixture.info(report_codes.CIB_UPGRADE_SUCCESSFUL)
        ])

    def test_simplest_resource(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.cib.load(resources=self.fixture_resources_pre)
            .runner.cib.push(resources=self.fixture_resources_post_simple)
        )
        create_bundle(self.env_assist.get_env(), wait=False)

    def test_bundle_doesnt_exist(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.cib.load(resources=self.fixture_empty_resources)
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env(), wait=False),
            [
                fixture.error(
                    report_codes.ID_NOT_FOUND,
                    id="B",
                    id_description="bundle",
                    context_type="resources",
                    context_id="",
                )
            ],
            expected_in_processor=False
        )

    def test_id_not_bundle(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.cib.load(
                resources="""
                    <resources>
                        <primitive id="B"/>
                    </resources>
                """
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env(), wait=False),
            [
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="B",
                    expected_types=["bundle"],
                    current_type="primitive",
                )
            ],
            expected_in_processor=False
        )

    def test_bundle_not_empty(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.cib.load(
                resources="""
                    <resources>
                        <bundle id="B">
                            <primitive id="P"/>
                        </bundle>
                    </resources>
                """
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env(), wait=False),
            [
                fixture.error(
                    report_codes.RESOURCE_BUNDLE_ALREADY_CONTAINS_A_RESOURCE,
                    bundle_id="B",
                    resource_id="P",
                )
            ],
            expected_in_processor=False
        )

    def test_wait_fail(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.pcmk.can_wait()
            .runner.cib.load(resources=self.fixture_resources_pre)
            .runner.cib.push(resources=self.fixture_resources_post_simple)
            .runner.pcmk.wait(stderr=self.fixture_wait_timeout_error)
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env()),
            [
                fixture.report_wait_for_idle_timed_out(
                    self.fixture_wait_timeout_error
                ),
            ],
            expected_in_processor=False
        )

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_run_ok(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.pcmk.can_wait()
            .runner.cib.load(resources=self.fixture_resources_pre)
            .runner.cib.push(resources=self.fixture_resources_post_simple)
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=self.fixture_status_running_with_primitive
            )
        )
        create_bundle(self.env_assist.get_env())
        self.env_assist.assert_reports([
            fixture.report_resource_running("A", {"Started": ["node1"]}),
        ])

    @skip_unless_pacemaker_supports_bundle
    def test_wait_ok_run_fail(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.pcmk.can_wait()
            .runner.cib.load(resources=self.fixture_resources_pre)
            .runner.cib.push(resources=self.fixture_resources_post_simple)
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=self.fixture_status_primitive_not_running
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A"
                )
            ]
        )

    @skip_unless_pacemaker_supports_bundle
    def test_disabled_wait_ok_not_running(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.pcmk.can_wait()
            .runner.cib.load(resources=self.fixture_resources_pre)
            .runner.cib.push(resources=self.fixture_resources_post_disabled)
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=self.fixture_status_primitive_not_running
            )
        )
        create_bundle(self.env_assist.get_env(), disabled=True)
        self.env_assist.assert_reports([
            fixture.report_resource_not_running("A")
        ])

    @skip_unless_pacemaker_supports_bundle
    def test_disabled_wait_ok_running(self):
        (self.config
            .runner.pcmk.load_agent()
            .runner.pcmk.can_wait()
            .runner.cib.load(resources=self.fixture_resources_pre)
            .runner.cib.push(resources=self.fixture_resources_post_disabled)
            .runner.pcmk.wait()
            .runner.pcmk.load_state(
                resources=self.fixture_status_running_with_primitive
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env(), disabled=True),
            [
                fixture.error(
                    report_codes.RESOURCE_RUNNING_ON_NODES,
                    resource_id="A",
                    roles_with_nodes={"Started": ["node1"]},
                )
            ]
        )

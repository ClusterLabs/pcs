from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.commands import stonith
from pcs.lib.resource_agent import StonithAgent
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools


class Create(TestCase):
    # TODO fix validation with respect to deprecated parameters
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.agent_name = "test_simple"
        self.instance_name = "stonith-test"
        self.timeout = 10
        self.expected_cib = """
            <resources>
                <primitive class="stonith" id="stonith-test" type="test_simple">
                    <instance_attributes id="stonith-test-instance_attributes">
                        <nvpair id="stonith-test-instance_attributes-must-set"
                            name="must-set" value="value"
                        />
                        <nvpair id="stonith-test-instance_attributes-must-set-new"
                            name="must-set-new" value="B"
                        />
                        <nvpair id="stonith-test-instance_attributes-must-set-old"
                            name="must-set-old" value="A"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="stonith-test-monitor-interval-60s"
                            interval="60s" name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
        """
        self.expected_status = """
            <resources>
                <resource
                    id="{id}"
                    resource_agent="stonith:{agent}"
                    role="Started"
                    active="true"
                    failed="false"
                    nodes_running_on="1"
                >
                    <node name="node1" id="1" cached="false"/>
                </resource>
            </resources>
            """.format(id=self.instance_name, agent=self.agent_name)
        (self.config
            .runner.pcmk.load_agent(
                agent_name="stonith:{0}".format(self.agent_name),
                agent_filename="stonith_agent_fence_simple.xml"
            )
            .runner.cib.load()
            .runner.pcmk.load_fenced_metadata()
        )

    def tearDown(self):
        StonithAgent.clear_fenced_metadata_cache()

    def test_minimal_success(self):
        self.config.env.push_cib(resources=self.expected_cib)
        stonith.create(
            self.env_assist.get_env(),
            self.instance_name,
            self.agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes={
                "must-set": "value",
                "must-set-old": "A",
                "must-set-new": "B",
            }
        )

    def test_minimal_wait_ok_run_ok(self):
        (self.config
            .runner.pcmk.can_wait(before="runner.cib.load")
            .env.push_cib(
                resources=self.expected_cib,
                wait=self.timeout
            )
            .runner.pcmk.load_state(resources=self.expected_status)
        )
        stonith.create(
            self.env_assist.get_env(),
            self.instance_name,
            self.agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes={
                "must-set": "value",
                "must-set-old": "A",
                "must-set-new": "B",
            },
            wait=self.timeout
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_RUNNING_ON_NODES,
                roles_with_nodes={"Started": ["node1"]},
                resource_id=self.instance_name,
            ),
        ])


class CreateInGroup(TestCase):
    # TODO fix validation with respect to deprecated parameters
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.agent_name = "test_simple"
        self.instance_name = "stonith-test"
        self.timeout = 10
        self.expected_cib = """
            <resources>
            <group id="my-group">
                <primitive class="stonith" id="stonith-test" type="test_simple">
                    <instance_attributes id="stonith-test-instance_attributes">
                        <nvpair id="stonith-test-instance_attributes-must-set"
                            name="must-set" value="value"
                        />
                        <nvpair id="stonith-test-instance_attributes-must-set-new"
                            name="must-set-new" value="B"
                        />
                        <nvpair id="stonith-test-instance_attributes-must-set-old"
                            name="must-set-old" value="A"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="stonith-test-monitor-interval-60s"
                            interval="60s" name="monitor"
                        />
                    </operations>
                </primitive>
            </group>
            </resources>
        """
        self.expected_status = """
            <resources>
                <resource
                    id="{id}"
                    resource_agent="stonith:{agent}"
                    role="Started"
                    active="true"
                    failed="false"
                    nodes_running_on="1"
                >
                    <node name="node1" id="1" cached="false"/>
                </resource>
            </resources>
            """.format(id=self.instance_name, agent=self.agent_name)
        (self.config
            .runner.pcmk.load_agent(
                agent_name="stonith:{0}".format(self.agent_name),
                agent_filename="stonith_agent_fence_simple.xml"
            )
            .runner.cib.load()
            .runner.pcmk.load_fenced_metadata()
        )

    def tearDown(self):
        StonithAgent.clear_fenced_metadata_cache()

    def test_minimal_success(self):
        self.config.env.push_cib(resources=self.expected_cib)
        stonith.create_in_group(
            self.env_assist.get_env(),
            self.instance_name,
            self.agent_name,
            "my-group",
            operations=[],
            meta_attributes={},
            instance_attributes={
                "must-set": "value",
                "must-set-old": "A",
                "must-set-new": "B",
            }
        )

    def test_minimal_wait_ok_run_ok(self):
        (self.config
            .runner.pcmk.can_wait(before="runner.cib.load")
            .env.push_cib(
                resources=self.expected_cib,
                wait=self.timeout
            )
            .runner.pcmk.load_state(resources=self.expected_status)
        )
        stonith.create_in_group(
            self.env_assist.get_env(),
            self.instance_name,
            self.agent_name,
            "my-group",
            operations=[],
            meta_attributes={},
            instance_attributes={
                "must-set": "value",
                "must-set-old": "A",
                "must-set-new": "B",
            },
            wait=self.timeout
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_RUNNING_ON_NODES,
                roles_with_nodes={"Started": ["node1"]},
                resource_id=self.instance_name,
            ),
        ])

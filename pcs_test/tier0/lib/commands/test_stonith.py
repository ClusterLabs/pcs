from functools import partial
from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import stonith
from pcs.lib.resource_agent import StonithAgent

expected_cib_simple = """
    <primitive class="stonith" id="stonith-test" type="test_simple">
        <instance_attributes id="stonith-test-instance_attributes">
            <nvpair id="stonith-test-instance_attributes-must-set"
                name="must-set" value="value"
            />
            <nvpair id="stonith-test-instance_attributes-must-set-new"
                name="must-set-new" value="B"
            />
        </instance_attributes>
        <operations>
            <op id="stonith-test-monitor-interval-60s" interval="60s"
                name="monitor"
            />
        </operations>
    </primitive>
"""

expected_cib_simple_forced = """
    <primitive class="stonith" id="stonith-test" type="test_simple">
        <instance_attributes id="stonith-test-instance_attributes">
            <nvpair id="stonith-test-instance_attributes-undefined"
                name="undefined" value="attribute"
            />
        </instance_attributes>
        <meta_attributes id="stonith-test-meta_attributes">
            <nvpair id="stonith-test-meta_attributes-metaname"
                name="metaname" value="metavalue"
            />
        </meta_attributes>
        <operations>
            <op id="stonith-test-bad-action-interval-0s" interval="0s"
                name="bad-action"
            />
            <op id="stonith-test-monitor-interval-60s" interval="60s"
                name="monitor"
            />
        </operations>
    </primitive>
"""

expected_cib_unfencing = """
    <primitive class="stonith" id="stonith-test" type="test_unfencing">
        <meta_attributes id="stonith-test-meta_attributes">
            <nvpair id="stonith-test-meta_attributes-provides"
                name="provides" value="unfencing"
            />
        </meta_attributes>
        <operations>
            <op id="stonith-test-monitor-interval-60s"
                interval="60s" name="monitor"
            />
        </operations>
    </primitive>
"""

expected_cib_operations = """
    <primitive class="stonith" id="stonith-test" type="test_custom_actions">
        <operations>
            <op id="stonith-test-monitor-interval-27s"
                interval="27s" name="monitor" timeout="11s"
            />
        </operations>
    </primitive>
"""

expected_cib_unknown = """
    <primitive class="stonith" id="stonith-test" type="test_unknown">
        <operations>
            <op id="stonith-test-monitor-interval-60s" interval="60s"
                name="monitor"
            />
        </operations>
    </primitive>
"""

class CreateMixin():
    def setUp(self):
        # pylint does not know this method is defined in TestCase
        # pylint: disable=invalid-name
        self.env_assist, self.config = get_env_tools(test_case=self)

    def tearDown(self):
        # pylint does not know this method is defined in TestCase
        # pylint: disable=invalid-name
        # pylint: disable=no-self-use
        StonithAgent.clear_fenced_metadata_cache()

    def test_minimal_success(self):
        agent_name = "test_simple"

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_filename="stonith_agent_fence_simple.xml"
            )
            .runner.cib.load()
            .runner.pcmk.load_fenced_metadata()
            .env.push_cib(resources=self._expected_cib(expected_cib_simple))
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes={
                "must-set": "value",
                "must-set-new": "B",
            }
        )

    def test_unfencing(self):
        agent_name = "test_unfencing"

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_filename="stonith_agent_fence_unfencing.xml"
            )
            .runner.cib.load()
            .runner.pcmk.load_fenced_metadata()
            .env.push_cib(resources=self._expected_cib(expected_cib_unfencing))
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes={}
        )

    def test_disabled(self):
        agent_name = "test_simple"
        expected_cib = expected_cib_simple.replace(
            '<instance_attributes id="stonith-test-instance_attributes">',
            """
                <meta_attributes id="stonith-test-meta_attributes">
                    <nvpair id="stonith-test-meta_attributes-target-role"
                        name="target-role" value="Stopped"
                    />
                </meta_attributes>
                <instance_attributes id="stonith-test-instance_attributes">
            """
        )

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_filename="stonith_agent_fence_simple.xml"
            )
            .runner.cib.load()
            .runner.pcmk.load_fenced_metadata()
            .env.push_cib(resources=self._expected_cib(expected_cib))
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes={
                "must-set": "value",
                "must-set-new": "B",
            },
            ensure_disabled=True
        )

    def _assert_default_operations(self, use_default_operations):
        # use_default_operations currently has no effect because in both cases
        # only the monitor operation is created in cib. That is correct. Still
        # it is worth testing. If it ever changes, the test should fail and be
        # updated to test new behaviour.
        agent_name = "test_custom_actions"

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_filename="stonith_agent_fence_custom_actions.xml"
            )
            .runner.cib.load()
            .runner.pcmk.load_fenced_metadata()
            .env.push_cib(resources=self._expected_cib(expected_cib_operations))
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes={},
            use_default_operations=use_default_operations
        )

    def test_default_operations_yes(self):
        self._assert_default_operations(True)

    def test_default_operations_no(self):
        self._assert_default_operations(False)

    def test_id_already_exists(self):
        agent_name = "test_simple"

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_filename="stonith_agent_fence_simple.xml"
            )
            .runner.cib.load(resources=self._expected_cib(expected_cib_simple))
        )

        self.env_assist.assert_raise_library_error(
            lambda: self._create(
                self.env_assist.get_env(),
                "stonith-test",
                agent_name,
                operations=[],
                meta_attributes={},
                instance_attributes={
                    "must-set": "value",
                    "must-set-new": "B",
                }
            ),
            [
                fixture.error(report_codes.ID_ALREADY_EXISTS, id="stonith-test")
            ],
            expected_in_processor=False
        )

    def test_instance_meta_and_operations(self):
        agent_name = "test_simple"

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_filename="stonith_agent_fence_simple.xml"
            )
            .runner.cib.load()
            .runner.pcmk.load_fenced_metadata()
            .env.push_cib(
                resources=self._expected_cib(expected_cib_simple_forced)
            )
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[
                {"name": "bad-action"},
            ],
            meta_attributes={
                "metaname": "metavalue",
            },
            instance_attributes={
                "undefined": "attribute"
            },
            allow_invalid_operation=True,
            allow_invalid_instance_attributes=True,
        )

        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.INVALID_OPTION_VALUE,
                option_value="bad-action",
                option_name="operation name",
                allowed_values=[
                    "on", "off", "reboot", "status", "list", "list-status",
                    "monitor", "metadata", "validate-all",
                ],
                cannot_be_empty=False,
                forbidden_characters=None,
            ),
            fixture.warn(
                report_codes.INVALID_OPTIONS,
                option_names=["undefined"],
                option_type="stonith",
                allowed=[
                    "may-set", "must-set", "must-set-new", "must-set-old",
                    "pcmk_action_limit", "pcmk_delay_base", "pcmk_delay_max",
                    "pcmk_host_argument", "pcmk_host_check", "pcmk_host_list",
                    "pcmk_host_map", "pcmk_list_action", "pcmk_list_retries",
                    "pcmk_list_timeout", "pcmk_monitor_action",
                    "pcmk_monitor_retries", "pcmk_monitor_timeout",
                    "pcmk_off_action", "pcmk_off_retries", "pcmk_off_timeout",
                    "pcmk_on_action", "pcmk_on_retries", "pcmk_on_timeout",
                    "pcmk_reboot_action", "pcmk_reboot_retries",
                    "pcmk_reboot_timeout", "pcmk_status_action",
                    "pcmk_status_retries", "pcmk_status_timeout", "priority",
                ],
                allowed_patterns=[]
            ),
            fixture.warn(
                report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                option_names=["must-set", "must-set-new"],
                option_type="stonith",
            ),
        ])

    def test_unknown_agent_forced(self):
        agent_name = "test_unknown"

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_is_missing=True,
            )
            .runner.cib.load()
            .env.push_cib(resources=self._expected_cib(expected_cib_unknown))
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes={},
            allow_absent_agent=True,
        )

        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.UNABLE_TO_GET_AGENT_METADATA,
                agent="test_unknown",
                reason=(
                    "Agent stonith:test_unknown not found or does not support "
                        "meta-data: Invalid argument (22)\n"
                    "Metadata query for stonith:test_unknown failed: "
                        "Input/output error"
                )
            ),
        ])

    def test_minimal_wait_ok_run_ok(self):
        agent_name = "test_simple"
        instance_name = "stonith-test"
        timeout = "10"
        expected_status = """
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
            """.format(id=instance_name, agent=agent_name)

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_filename="stonith_agent_fence_simple.xml"
            )
            .runner.cib.load()
            .runner.pcmk.load_fenced_metadata()
            .runner.pcmk.can_wait(before="runner.cib.load")
            .env.push_cib(
                resources=self._expected_cib(expected_cib_simple),
                wait=timeout
            )
            .runner.pcmk.load_state(resources=expected_status)
        )

        self._create(
            self.env_assist.get_env(),
            instance_name,
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes={
                "must-set": "value",
                "must-set-new": "B",
            },
            wait=timeout
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.RESOURCE_RUNNING_ON_NODES,
                roles_with_nodes={"Started": ["node1"]},
                resource_id=instance_name,
            ),
        ])


class Create(CreateMixin, TestCase):
    _create = staticmethod(stonith.create)

    @staticmethod
    def _expected_cib(xml):
        return "<resources>" + xml + "</resources>"


class CreateInGroup(CreateMixin, TestCase):
    _create = staticmethod(
        partial(stonith.create_in_group, group_id="my-group")
    )

    @staticmethod
    def _expected_cib(xml):
        return "<resources><group id='my-group'>" + xml + "</group></resources>"

    @staticmethod
    def _dummy(name):
        return f"""
            <primitive class="ocf" id="{name}" provider="pacemaker" type="Dummy"
            />
        """

    def test_group_not_valid(self):
        agent_name = "test_simple"

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_filename="stonith_agent_fence_simple.xml"
            )
            .runner.cib.load()
            .runner.pcmk.load_fenced_metadata()
        )

        self.env_assist.assert_raise_library_error(
            lambda: stonith.create_in_group(
                self.env_assist.get_env(),
                "stonith-test",
                agent_name,
                "0-group",
                operations=[],
                meta_attributes={},
                instance_attributes={
                    "must-set": "value",
                    "must-set-new": "B",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_ID,
                    id="0-group",
                    id_description="group name",
                    is_first_char=True,
                    invalid_character="0",
                )
            ],
            expected_in_processor=False
        )

    def _assert_adjacent(self, adjacent, after):
        agent_name = "test_simple"
        original_cib = (
            "<resources><group id='my-group'>"
            +
            self._dummy("dummy1")
            +
            self._dummy("dummy2")
            +
            "</group></resources>"
        )
        expected_cib = (
            "<resources><group id='my-group'>"
            +
            self._dummy("dummy1")
            +
            expected_cib_simple
            +
            self._dummy("dummy2")
            +
            "</group></resources>"
        )

        (self.config
            .runner.pcmk.load_agent(
                agent_name=f"stonith:{agent_name}",
                agent_filename="stonith_agent_fence_simple.xml"
            )
            .runner.cib.load(resources=original_cib)
            .runner.pcmk.load_fenced_metadata()
            .env.push_cib(resources=expected_cib)
        )

        stonith.create_in_group(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            "my-group",
            operations=[],
            meta_attributes={},
            instance_attributes={
                "must-set": "value",
                "must-set-new": "B",
            },
            adjacent_resource_id=adjacent,
            put_after_adjacent=after,
        )

    def test_put_after_adjacent(self):
        self._assert_adjacent("dummy1", True)

    def test_put_before_adjacent(self):
        self._assert_adjacent("dummy2", False)

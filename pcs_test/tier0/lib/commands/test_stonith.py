from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import reports
from pcs.lib.commands import stonith
from pcs.lib.resource_agent import const as ra_const

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.metadata_dto import FIXTURE_KNOWN_META_NAMES_STONITH_META
from pcs_test.tools.misc import get_test_resource as rc

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


class Create(TestCase):
    _create = staticmethod(stonith.create)

    @staticmethod
    def _expected_cib(xml):
        return "<resources>" + xml + "</resources>"

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_minimal_success(self):
        agent_name = "test_simple"
        instance_attributes = {
            "must-set": "value",
            "must-set-new": "B",
        }

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes, agent_name
        )
        self.config.env.push_cib(
            resources=self._expected_cib(expected_cib_simple)
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes=instance_attributes,
        )

    def test_agent_self_validation_failure(self):
        agent_name = "test_simple"
        instance_attributes = {
            "must-set": "value",
            "must-set-new": "B",
        }

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes,
            agent_name,
            output="""
            <output source="stderr">not ignored</output>
            <output source="stdout">this is ignored</output>
            <output source="stderr">
            first issue
            another one
            </output>
            """,
            returncode=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: self._create(
                self.env_assist.get_env(),
                "stonith-test",
                agent_name,
                operations=[],
                meta_attributes={},
                instance_attributes=instance_attributes,
                enable_agent_self_validation=True,
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def assert_agent_self_validation_warnings(
        self, user_enabled, extra_reports
    ):
        agent_name = "test_simple"
        instance_attributes = {
            "must-set": "value",
            "must-set-new": "B",
        }

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes,
            agent_name,
            output="""
            <output source="stderr">not ignored</output>
            <output source="stdout">this is ignored</output>
            <output source="stderr">
            first issue
            another one
            </output>
            """,
            returncode=1,
        )
        self.config.env.push_cib(
            resources=self._expected_cib(expected_cib_simple)
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes=instance_attributes,
            allow_invalid_instance_attributes=user_enabled,
            enable_agent_self_validation=user_enabled,
        )
        self.env_assist.assert_reports(
            (extra_reports or [])
            + [
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                )
            ]
        )

    def test_agent_self_validation_failure_forced(self):
        self.assert_agent_self_validation_warnings(True, [])

    def test_agent_self_validation_failure_default(self):
        self.assert_agent_self_validation_warnings(
            False,
            [
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_AUTO_ON_WITH_WARNINGS
                ),
            ],
        )

    def test_agent_self_validation_invalid_output(self):
        agent_name = "test_simple"
        instance_attributes = {
            "must-set": "value",
            "must-set-new": "B",
        }

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes,
            agent_name,
            output="""<not valid> xml""",
            returncode=0,
        )
        self.env_assist.assert_raise_library_error(
            lambda: self._create(
                self.env_assist.get_env(),
                "stonith-test",
                agent_name,
                operations=[],
                meta_attributes={},
                instance_attributes=instance_attributes,
                enable_agent_self_validation=True,
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.AGENT_SELF_VALIDATION_INVALID_DATA,
                    reason="Specification mandates value for attribute valid, line 5, column 29 (<string>, line 5)",
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_agent_self_validation_invalid_output_default(self):
        agent_name = "test_simple"
        instance_attributes = {
            "must-set": "value",
            "must-set-new": "B",
        }

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes,
            agent_name,
            output="""<not valid> xml""",
            returncode=0,
        )
        self.config.env.push_cib(
            resources=self._expected_cib(expected_cib_simple)
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes=instance_attributes,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_AUTO_ON_WITH_WARNINGS
                ),
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_INVALID_DATA,
                    reason="Specification mandates value for attribute valid, line 5, column 29 (<string>, line 5)",
                ),
            ]
        )

    def test_unfencing(self):
        agent_name = "test_unfencing"
        instance_attributes = {}

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_unfencing.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes, agent_name
        )
        self.config.runner.pcmk.load_crm_resource_metadata()
        self.config.env.push_cib(
            resources=self._expected_cib(expected_cib_unfencing)
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes=instance_attributes,
        )

    def test_disabled(self):
        agent_name = "test_simple"
        instance_attributes = {
            "must-set": "value",
            "must-set-new": "B",
        }
        expected_cib = expected_cib_simple.replace(
            '<instance_attributes id="stonith-test-instance_attributes">',
            """
                <meta_attributes id="stonith-test-meta_attributes">
                    <nvpair id="stonith-test-meta_attributes-target-role"
                        name="target-role" value="Stopped"
                    />
                </meta_attributes>
                <instance_attributes id="stonith-test-instance_attributes">
            """,
        )

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes, agent_name
        )
        self.config.env.push_cib(resources=self._expected_cib(expected_cib))

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes=instance_attributes,
            ensure_disabled=True,
        )

    def _assert_default_operations(self, use_default_operations):
        # use_default_operations currently has no effect because in both cases
        # only the monitor operation is created in cib. That is correct. Still
        # it is worth testing. If it ever changes, the test should fail and be
        # updated to test new behaviour.
        agent_name = "test_custom_actions"
        instance_attributes = {}

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_custom_actions.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes, agent_name
        )
        self.config.env.push_cib(
            resources=self._expected_cib(expected_cib_operations)
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes=instance_attributes,
            use_default_operations=use_default_operations,
        )

    def test_default_operations_yes(self):
        self._assert_default_operations(True)

    def test_default_operations_no(self):
        self._assert_default_operations(False)

    def test_id_already_exists(self):
        agent_name = "test_simple"

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load(
            resources=self._expected_cib(expected_cib_simple)
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
                },
            ),
            [fixture.error(reports.codes.ID_ALREADY_EXISTS, id="stonith-test")],
            expected_in_processor=False,
        )

    def test_instance_meta_and_operations(self):
        agent_name = "test_simple"
        instance_attributes = {"undefined": "attribute"}

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes, agent_name
        )
        self.config.runner.pcmk.load_crm_resource_metadata()
        self.config.env.push_cib(
            resources=self._expected_cib(expected_cib_simple_forced)
        )

        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[{"name": "bad-action"}],
            meta_attributes={"metaname": "metavalue"},
            instance_attributes=instance_attributes,
            allow_invalid_operation=True,
            allow_invalid_instance_attributes=True,
        )

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_value="bad-action",
                    option_name="operation name",
                    allowed_values=[
                        "on",
                        "off",
                        "reboot",
                        "status",
                        "list",
                        "list-status",
                        "monitor",
                        "metadata",
                        "validate-all",
                    ],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["undefined"],
                    option_type="stonith",
                    allowed=[
                        "may-set",
                        "must-set",
                        "must-set-new",
                        "must-set-old",
                        "pcmk_action_limit",
                        "pcmk_delay_base",
                        "pcmk_delay_max",
                        "pcmk_host_argument",
                        "pcmk_host_check",
                        "pcmk_host_list",
                        "pcmk_host_map",
                        "pcmk_list_action",
                        "pcmk_list_retries",
                        "pcmk_list_timeout",
                        "pcmk_monitor_action",
                        "pcmk_monitor_retries",
                        "pcmk_monitor_timeout",
                        "pcmk_off_action",
                        "pcmk_off_retries",
                        "pcmk_off_timeout",
                        "pcmk_on_action",
                        "pcmk_on_retries",
                        "pcmk_on_timeout",
                        "pcmk_reboot_action",
                        "pcmk_reboot_retries",
                        "pcmk_reboot_timeout",
                        "pcmk_status_action",
                        "pcmk_status_retries",
                        "pcmk_status_timeout",
                    ],
                    allowed_patterns=[],
                ),
                fixture.warn(
                    reports.codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["must-set"],
                    option_type="stonith",
                ),
                fixture.warn(
                    reports.codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    option_names=["must-set-new", "must-set-old"],
                    deprecated_names=["must-set-old"],
                    option_type="stonith",
                ),
                fixture.warn(
                    reports.codes.META_ATTRS_UNKNOWN_TO_PCMK,
                    unknown_meta=["metaname"],
                    known_meta=FIXTURE_KNOWN_META_NAMES_STONITH_META,
                    meta_types=["stonith-meta"],
                ),
            ]
        )

    def test_invalid_agent_name(self):
        self.env_assist.assert_raise_library_error(
            lambda: self._create(
                self.env_assist.get_env(),
                "stonith-test",
                "stonith:fence_xvm",
                operations=[],
                meta_attributes={},
                instance_attributes={},
                allow_absent_agent=True,
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_STONITH_AGENT_NAME,
                    name="stonith:fence_xvm",
                ),
            ]
        )

    def test_agent_load_failure(self):
        agent_name = "test_unknown"
        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}", agent_is_missing=True
        )

        self.env_assist.assert_raise_library_error(
            lambda: self._create(
                self.env_assist.get_env(),
                "stonith-test",
                agent_name,
                operations=[],
                meta_attributes={},
                instance_attributes={},
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    force_code=reports.codes.FORCE,
                    agent="stonith:test_unknown",
                    reason=(
                        "Agent stonith:test_unknown not found or does not "
                        "support meta-data: Invalid argument (22)\n"
                        "Metadata query for stonith:test_unknown failed: "
                        "Input/output error"
                    ),
                ),
            ]
        )

    def test_agent_load_failure_forced(self):
        agent_name = "test_unknown"
        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}", agent_is_missing=True
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.env.push_cib(
            resources=self._expected_cib(expected_cib_unknown)
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

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="stonith:test_unknown",
                    reason=(
                        "Agent stonith:test_unknown not found or does not "
                        "support meta-data: Invalid argument (22)\n"
                        "Metadata query for stonith:test_unknown failed: "
                        "Input/output error"
                    ),
                ),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_rng/api/api-result.rng"),
    )
    def test_minimal_wait_ok_run_ok(self):
        agent_name = "test_simple"
        instance_name = "stonith-test"
        instance_attributes = {
            "must-set": "value",
            "must-set-new": "B",
        }
        timeout = 10
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

        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes, agent_name
        )
        self.config.env.push_cib(
            resources=self._expected_cib(expected_cib_simple), wait=timeout
        )
        self.config.runner.pcmk.load_state(resources=expected_status)

        self._create(
            self.env_assist.get_env(),
            instance_name,
            agent_name,
            operations=[],
            meta_attributes={},
            instance_attributes=instance_attributes,
            wait=str(timeout),
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": ["node1"]},
                    resource_id=instance_name,
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_known_meta_attributes(self):
        agent_name = "test_simple"
        instance_attributes = {
            "must-set": "value",
            "must-set-new": "B",
        }
        meta_attributes = {"target-role": "Stopped"}
        expected_cib = expected_cib_simple.replace(
            "<operations>",
            """
            <meta_attributes id="stonith-test-meta_attributes">
                <nvpair id="stonith-test-meta_attributes-target-role"
                    name="target-role" value="Stopped"></nvpair>
            </meta_attributes>
            <operations>
            """,
        )
        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes, agent_name
        )
        self.config.runner.pcmk.load_crm_resource_metadata()
        self.config.env.push_cib(resources=self._expected_cib(expected_cib))
        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes=meta_attributes,
            instance_attributes=instance_attributes,
        )

    def test_unknown_meta_attributes(self):
        agent_name = "test_simple"
        instance_attributes = {
            "must-set": "value",
            "must-set-new": "B",
        }
        meta_attributes = {"unknown_meta": "unknown_value"}
        expected_cib = expected_cib_simple.replace(
            "<operations>",
            """
            <meta_attributes id="stonith-test-meta_attributes">
                <nvpair id="stonith-test-meta_attributes-unknown_meta"
                    name="unknown_meta" value="unknown_value"></nvpair>
            </meta_attributes>
            <operations>
            """,
        )
        self.config.runner.pcmk.load_agent(
            agent_name=f"stonith:{agent_name}",
            agent_filename="stonith_agent_fence_simple.xml",
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.config.runner.cib.load()
        self.config.runner.pcmk.stonith_agent_self_validation(
            instance_attributes, agent_name
        )
        self.config.runner.pcmk.load_crm_resource_metadata()
        self.config.env.push_cib(resources=self._expected_cib(expected_cib))
        self._create(
            self.env_assist.get_env(),
            "stonith-test",
            agent_name,
            operations=[],
            meta_attributes=meta_attributes,
            instance_attributes=instance_attributes,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.META_ATTRS_UNKNOWN_TO_PCMK,
                    unknown_meta=["unknown_meta"],
                    known_meta=FIXTURE_KNOWN_META_NAMES_STONITH_META,
                    meta_types=[ra_const.STONITH_META],
                )
            ]
        )

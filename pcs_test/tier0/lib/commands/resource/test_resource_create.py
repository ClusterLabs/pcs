# pylint: disable=too-many-lines
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import (
    const,
    reports,
)
from pcs.lib.commands import resource
from pcs.lib.errors import LibraryError
from pcs.lib.resource_agent import ResourceAgentName

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_raise_library_error
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import outdent

TIMEOUT = 10


def create(
    env,
    *,
    wait=False,
    disabled=False,
    meta_attributes=None,
    operation_list=None,
    allow_invalid_operation=False,
    agent_name="ocf:heartbeat:Dummy",
    allow_invalid_instance_attributes=False,
    enable_agent_self_validation=False,
    instance_attributes=None,
):
    # pylint: disable=too-many-arguments
    return resource.create(
        env,
        "A",
        agent_name,
        operation_list=operation_list if operation_list else [],
        meta_attributes=meta_attributes if meta_attributes else {},
        instance_attributes=instance_attributes if instance_attributes else {},
        wait=wait,
        ensure_disabled=disabled,
        allow_invalid_operation=allow_invalid_operation,
        allow_invalid_instance_attributes=allow_invalid_instance_attributes,
        enable_agent_self_validation=enable_agent_self_validation,
    )


def create_group(
    env,
    wait=TIMEOUT,
    disabled=False,
    meta_attributes=None,
    operation_list=None,
    enable_agent_self_validation=False,
    instance_attributes=None,
    agent="ocf:heartbeat:Dummy",
):
    return resource.create_in_group(
        env,
        "A",
        agent,
        "G",
        operation_list=operation_list if operation_list else [],
        meta_attributes=meta_attributes if meta_attributes else {},
        instance_attributes=instance_attributes if instance_attributes else {},
        wait=wait,
        ensure_disabled=disabled,
        enable_agent_self_validation=enable_agent_self_validation,
    )


def create_clone(
    env,
    *,
    wait=TIMEOUT,
    disabled=False,
    meta_attributes=None,
    clone_options=None,
    operation_list=None,
    clone_id=None,
    agent="ocf:heartbeat:Dummy",
    allow_incompatible_clone_meta_attributes=False,
    enable_agent_self_validation=False,
    instance_attributes=None,
):
    # pylint: disable=too-many-arguments
    return resource.create_as_clone(
        env,
        "A",
        agent,
        operation_list=operation_list if operation_list else [],
        meta_attributes=meta_attributes if meta_attributes else {},
        instance_attributes=instance_attributes if instance_attributes else {},
        clone_meta_options=clone_options if clone_options else {},
        clone_id=clone_id,
        wait=wait,
        ensure_disabled=disabled,
        allow_incompatible_clone_meta_attributes=allow_incompatible_clone_meta_attributes,
        enable_agent_self_validation=enable_agent_self_validation,
    )


def create_bundle(
    env,
    agent="ocf:heartbeat:Dummy",
    wait=TIMEOUT,
    disabled=False,
    meta_attributes=None,
    allow_not_accessible_resource=False,
    operation_list=None,
    enable_agent_self_validation=False,
):
    return resource.create_into_bundle(
        env,
        "A",
        agent,
        operation_list=operation_list if operation_list else [],
        meta_attributes=meta_attributes if meta_attributes else {},
        instance_attributes={},
        bundle_id="B",
        wait=wait,
        ensure_disabled=disabled,
        allow_not_accessible_resource=allow_not_accessible_resource,
        enable_agent_self_validation=enable_agent_self_validation,
    )


wait_error_message = outdent(
    """\
    Pending actions:
            Action 39: stonith-vm-rhel72-1-reboot  on vm-rhel72-1
    Error performing operation: Timer expired
    """
).strip()


def fixture_cib_primitive_stateful(
    use_legacy_roles=False, include_reload=True, res_id="S1"
):
    promoted_role = const.PCMK_ROLE_PROMOTED
    unpromoted_role = const.PCMK_ROLE_UNPROMOTED
    if use_legacy_roles:
        promoted_role = const.PCMK_ROLE_PROMOTED_LEGACY
        unpromoted_role = const.PCMK_ROLE_UNPROMOTED_LEGACY
    agent_reload = ""
    if include_reload:
        agent_reload = """
                    <op id="S1-reload-agent-interval-0s" interval="0s"
                        name="reload-agent" timeout="10s"/>
        """
    return f"""
            <primitive class="ocf" id="{res_id}" provider="pacemaker" type="Stateful">
                <operations>
                    <op id="S1-demote-interval-0s" interval="0s" name="demote"
                        timeout="10s"/>
                    <op id="S1-monitor-interval-10s" interval="10s"
                        name="monitor" role="{promoted_role}" timeout="20s"/>
                    <op id="S1-monitor-interval-11s" interval="11s"
                        name="monitor" role="{unpromoted_role}" timeout="20s"/>
                    <op id="S1-notify-interval-0s" interval="0s" name="notify"
                        timeout="5s"/>
                    <op id="S1-promote-interval-0s" interval="0s"
                        name="promote" timeout="10s"/>
                    {agent_reload}
                    <op id="S1-start-interval-0s" interval="0s" name="start"
                        role="{promoted_role}"/>
                    <op id="S1-stop-interval-0s" interval="0s" name="stop"
                        role="{unpromoted_role}"/>
                  </operations>
            </primitive>
        """


def fixture_cib_resources_xml(resources):
    return f"""
        <resources>
            {resources}
        </resources>
    """


fixture_cib_resources_xml_primitive_simplest = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <operations>
                <op id="A-migrate_from-interval-0s" interval="0s"
                    name="migrate_from" timeout="20"
                />
                <op id="A-migrate_to-interval-0s" interval="0s"
                    name="migrate_to" timeout="20"
                />
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-reload-interval-0s" interval="0s" name="reload"
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
            <op id="A-migrate_from-interval-0s" interval="0s"
                name="migrate_from" timeout="20"
            />
            <op id="A-migrate_to-interval-0s" interval="0s" name="migrate_to"
                timeout="20"
            />
            <op id="A-monitor-interval-10" interval="10" name="monitor"
                timeout="20"
            />
            <op id="A-reload-interval-0s" interval="0s" name="reload"
                timeout="20"
            />
            <op id="A-start-interval-0s" interval="0s" name="start"
                timeout="20"
            />
            <op id="A-stop-interval-0s" interval="0s" name="stop" timeout="20"/>
        </operations>
    </primitive>
</resources>"""

fixture_cib_resources_xml_group_simplest = """<resources>
    <group id="G">
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <operations>
                <op id="A-migrate_from-interval-0s" interval="0s"
                    name="migrate_from" timeout="20"
                />
                <op id="A-migrate_to-interval-0s" interval="0s"
                    name="migrate_to" timeout="20"
                />
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-reload-interval-0s" interval="0s" name="reload"
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
                <op id="A-migrate_from-interval-0s" interval="0s"
                    name="migrate_from" timeout="20"
                />
                <op id="A-migrate_to-interval-0s" interval="0s"
                    name="migrate_to" timeout="20"
                />
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-reload-interval-0s" interval="0s" name="reload"
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


fixture_cib_resources_xml_clone_simplest_template = """<resources>
    <clone id="{clone_id}">
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <operations>
                <op id="A-migrate_from-interval-0s" interval="0s"
                    name="migrate_from" timeout="20"
                />
                <op id="A-migrate_to-interval-0s" interval="0s"
                    name="migrate_to" timeout="20"
                />
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-reload-interval-0s" interval="0s" name="reload"
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


fixture_cib_resources_xml_clone_simplest = (
    fixture_cib_resources_xml_clone_simplest_template.format(clone_id="A-clone")
)


fixture_cib_resources_xml_clone_custom_id = (
    fixture_cib_resources_xml_clone_simplest_template.format(
        clone_id="CustomCloneId"
    )
)


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
                <op id="A-migrate_from-interval-0s" interval="0s"
                    name="migrate_from" timeout="20"
                />
                <op id="A-migrate_to-interval-0s" interval="0s"
                    name="migrate_to" timeout="20"
                />
                <op id="A-monitor-interval-10" interval="10" name="monitor"
                    timeout="20"
                />
                <op id="A-reload-interval-0s" interval="0s" name="reload"
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


def fixture_state_resources_xml(
    role="Started", failed="false", node_name="node1"
):
    return """
        <resources>
            <resource
                id="A" resource_agent="ocf::heartbeat:Dummy"
                role="{role}" failed="{failed}"
            >
                <node name="{node_name}" id="1" cached="false"/>
            </resource>
        </resources>
        """.format(
        role=role,
        failed=failed,
        node_name=node_name,
    )


class CreateRolesNormalization(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def prepare(self, ocf_1_0=True, cib_support=True):
        agent_file_name = None
        if ocf_1_0:
            agent_file_name = (
                "resource_agent_ocf_pacemaker_stateful_ocf_1.0.xml"
            )
        cib_file = "cib-empty-3.5.xml"
        if cib_support:
            cib_file = "cib-empty-3.7.xml"
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:Stateful",
            agent_filename=agent_file_name,
        )
        self.config.runner.cib.load(filename=cib_file)

    def create(self, operation_list=None):
        resource.create(
            self.env_assist.get_env(),
            "S1",
            "ocf:pacemaker:Stateful",
            operation_list=operation_list if operation_list else [],
            meta_attributes={},
            instance_attributes={},
        )

    def assert_deprecated_reports(
        self,
        promoted_deprecated=const.PCMK_ROLE_PROMOTED_LEGACY,
        unpromoted_deprecated=const.PCMK_ROLE_UNPROMOTED_LEGACY,
    ):
        self.env_assist.assert_reports(
            [
                fixture.deprecation(
                    reports.codes.DEPRECATED_OPTION_VALUE,
                    option_name="role",
                    deprecated_value=promoted_deprecated,
                    replaced_by=const.PCMK_ROLE_PROMOTED,
                ),
                fixture.deprecation(
                    reports.codes.DEPRECATED_OPTION_VALUE,
                    option_name="role",
                    deprecated_value=unpromoted_deprecated,
                    replaced_by=const.PCMK_ROLE_UNPROMOTED,
                ),
            ]
        )

    def assert_old_roles_refused(self):
        assert_raise_library_error(
            lambda: self.create(
                [
                    dict(name="start", role=const.PCMK_ROLE_PROMOTED_LEGACY),
                    dict(name="stop", role=const.PCMK_ROLE_UNPROMOTED_LEGACY),
                ]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    option_value=role,
                    allowed_values=const.PCMK_ROLES,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
                for role in (
                    const.PCMK_ROLE_PROMOTED_LEGACY,
                    const.PCMK_ROLE_UNPROMOTED_LEGACY,
                )
            ]
        )

    def test_roles_normalization_user_defined(self):
        self.prepare(True, False)
        self.assert_old_roles_refused()

    def test_roles_normalization_user_defined_new_roles(self):
        self.prepare(True, False)
        self.config.runner.pcmk.resource_agent_self_validation(
            {}, "ocf", "pacemaker", "Stateful"
        )
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml(
                fixture_cib_primitive_stateful(
                    use_legacy_roles=True, include_reload=False
                )
            )
        )
        self.create(
            [
                dict(name="start", role=const.PCMK_ROLE_PROMOTED),
                dict(name="stop", role=str(const.PCMK_ROLE_UNPROMOTED).lower()),
            ]
        )

    def test_roles_normalization_user_defined_with_cib_support(self):
        self.prepare(True, True)
        self.assert_old_roles_refused()

    def test_roles_normalization_user_defined_new_roles_with_cib_support(self):
        self.prepare(True, True)
        self.config.runner.pcmk.resource_agent_self_validation(
            {}, "ocf", "pacemaker", "Stateful"
        )
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml(
                fixture_cib_primitive_stateful(include_reload=False)
            )
        )
        self.create(
            [
                dict(name="start", role=str(const.PCMK_ROLE_PROMOTED).lower()),
                dict(name="stop", role=const.PCMK_ROLE_UNPROMOTED),
            ]
        )

    def test_roles_normalization_agent(self):
        self.prepare(False, False)
        self.assert_old_roles_refused()

    def test_roles_normalization_agent_new_roles(self):
        self.prepare(False, False)
        self.config.runner.pcmk.resource_agent_self_validation(
            {}, "ocf", "pacemaker", "Stateful"
        )
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml(
                fixture_cib_primitive_stateful(use_legacy_roles=True)
            )
        )
        self.create(
            [
                dict(name="start", role=const.PCMK_ROLE_PROMOTED),
                dict(name="stop", role=const.PCMK_ROLE_UNPROMOTED),
            ]
        )

    def test_roles_normalization_agent_with_cib_support(self):
        self.prepare(False, True)
        self.assert_old_roles_refused()

    def test_roles_normalization_agent_new_roles_with_cib_support(self):
        self.prepare(False, True)
        self.config.runner.pcmk.resource_agent_self_validation(
            {}, "ocf", "pacemaker", "Stateful"
        )
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml(
                fixture_cib_primitive_stateful()
            )
        )
        self.create(
            [
                dict(name="start", role=const.PCMK_ROLE_PROMOTED),
                dict(name="stop", role=const.PCMK_ROLE_UNPROMOTED),
            ]
        )


class Create(TestCase):
    fixture_sanitized_operation = """
        <resources>
            <primitive class="ocf" id="A" provider="heartbeat"
                type="Dummy"
            >
                <operations>
                    <op id="A-migrate_from-interval-0s" interval="0s"
                        name="migrate_from" timeout="20"
                    />
                    <op id="A-migrate_to-interval-0s" interval="0s"
                        name="migrate_to" timeout="20"
                    />
                    <op id="A-monitor-interval-20" interval="20"
                        name="moni*tor" timeout="20"
                    />
                    <op id="A-monitor-interval-10" interval="10"
                        name="monitor" timeout="20"
                    />
                    <op id="A-reload-interval-0s" interval="0s"
                        name="reload" timeout="20"
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

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_simplest_resource(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_primitive_simplest
        )
        create(self.env_assist.get_env())

    def test_resource_self_validation_failure_default(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
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
            resources=fixture_cib_resources_xml_primitive_simplest
        )
        create(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_AUTO_ON_WITH_WARNINGS
                ),
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                ),
            ]
        )

    def test_resource_self_validation_failure(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
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
            lambda: create(
                self.env_assist.get_env(), enable_agent_self_validation=True
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

    def test_resource_self_validation_failure_forced(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
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
            resources=fixture_cib_resources_xml_primitive_simplest
        )
        create(
            self.env_assist.get_env(),
            allow_invalid_instance_attributes=True,
            enable_agent_self_validation=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                )
            ]
        )

    def test_resource_self_validation_default_invalid_output(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
            output="""<not valid> xml""",
            returncode=0,
        )
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_primitive_simplest
        )
        create(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_AUTO_ON_WITH_WARNINGS
                ),
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_INVALID_DATA,
                    reason="Specification mandates value for attribute valid, line 7, column 29 (<string>, line 7)",
                ),
            ]
        )

    def test_resource_self_validation_invalid_output(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
            output="""<not valid> xml""",
            returncode=0,
        )
        self.env_assist.assert_raise_library_error(
            lambda: create(
                self.env_assist.get_env(),
                enable_agent_self_validation=True,
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.AGENT_SELF_VALIDATION_INVALID_DATA,
                    reason="Specification mandates value for attribute valid, line 7, column 29 (<string>, line 7)",
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_invalid_agent_name(self):
        self.env_assist.assert_raise_library_error(
            lambda: create(
                self.env_assist.get_env(),
                agent_name="ocf:heartbeat:something:else",
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_RESOURCE_AGENT_NAME,
                    name="ocf:heartbeat:something:else",
                )
            ]
        )

    def test_agent_guess_success(self):
        self.config.runner.pcmk.list_agents_standards("\n".join(["ocf"]))
        self.config.runner.pcmk.list_agents_ocf_providers(
            "\n".join(["heartbeat", "pacemaker"])
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:heartbeat",
            "\n".join(["agent1", "Dummy", "agent2"]),
            name="runner.pcmk.list_agents_ocf_providers_heartbeat",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:pacemaker",
            "\n".join(["agent1", "agent2"]),
            name="runner.pcmk.list_agents_ocf_providers_pacemaker",
        )
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_primitive_simplest
        )
        create(self.env_assist.get_env(), agent_name="dummy")
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.AGENT_NAME_GUESSED,
                    entered_name="dummy",
                    guessed_name="ocf:heartbeat:Dummy",
                ),
            ]
        )

    def test_agent_guess_ambiguous(self):
        self.config.runner.pcmk.list_agents_standards("\n".join(["ocf"]))
        self.config.runner.pcmk.list_agents_ocf_providers(
            "\n".join(["heartbeat", "pacemaker"])
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:heartbeat",
            "\n".join(["agent1", "Dummy", "agent2"]),
            name="runner.pcmk.list_agents_ocf_providers_heartbeat",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:pacemaker",
            "\n".join(["agent1", "Dummy", "agent2"]),
            name="runner.pcmk.list_agents_ocf_providers_pacemaker",
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.create(
                self.env_assist.get_env(),
                "A",
                "dummy",
                [],
                {},
                {},
                allow_absent_agent=True,
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.AGENT_NAME_GUESS_FOUND_MORE_THAN_ONE,
                    agent="dummy",
                    possible_agents=[
                        "ocf:heartbeat:Dummy",
                        "ocf:pacemaker:Dummy",
                    ],
                )
            ],
        )

    def test_agent_guess_not_found(self):
        self.config.runner.pcmk.list_agents_standards("\n".join(["ocf"]))
        self.config.runner.pcmk.list_agents_ocf_providers(
            "\n".join(["heartbeat", "pacemaker"])
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:heartbeat",
            "\n".join(["agent1", "agent2"]),
            name="runner.pcmk.list_agents_ocf_providers_heartbeat",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:pacemaker",
            "\n".join(["agent1", "agent2"]),
            name="runner.pcmk.list_agents_ocf_providers_pacemaker",
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.create(
                self.env_assist.get_env(),
                "A",
                "dummy",
                [],
                {},
                {},
                allow_absent_agent=True,
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.AGENT_NAME_GUESS_FOUND_NONE,
                    agent="dummy",
                )
            ],
        )

    def test_agent_load_failure(self):
        self.config.runner.pcmk.load_agent(
            agent_is_missing=True,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.env_assist.assert_raise_library_error(
            lambda: create(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    force_code=reports.codes.FORCE,
                    agent="ocf:heartbeat:Dummy",
                    reason=(
                        "Agent ocf:heartbeat:Dummy not found or does not support "
                        "meta-data: Invalid argument (22)\nMetadata query for "
                        "ocf:heartbeat:Dummy failed: Input/output error"
                    ),
                )
            ]
        )

    def test_agent_load_failure_forced(self):
        instance_attributes = {"parameters": "can", "be": "anything"}
        self.config.runner.pcmk.load_agent(
            agent_is_missing=True,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.config.runner.cib.load()
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                        <instance_attributes id="C-instance_attributes">
                            <nvpair id="C-instance_attributes-be"
                                name="be" value="anything"/>
                            <nvpair id="C-instance_attributes-parameters"
                                name="parameters" value="can"/>
                        </instance_attributes>
                        <operations>
                            <op id="C-monitor-interval-60s"
                                interval="60s" name="monitor"/>
                        </operations>
                    </primitive>
                </resources>
            """
        )
        resource.create(
            self.env_assist.get_env(),
            "C",
            "ocf:heartbeat:Dummy",
            operation_list=[],
            meta_attributes={},
            instance_attributes=instance_attributes,
            allow_absent_agent=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="ocf:heartbeat:Dummy",
                    reason=(
                        "Agent ocf:heartbeat:Dummy not found or does not support "
                        "meta-data: Invalid argument (22)\nMetadata query for "
                        "ocf:heartbeat:Dummy failed: Input/output error"
                    ),
                )
            ]
        )

    def test_resource_with_operation(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive class="ocf" id="A" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="A-migrate_from-interval-0s" interval="0s"
                                name="migrate_from" timeout="20"
                            />
                            <op id="A-migrate_to-interval-0s" interval="0s"
                                name="migrate_to" timeout="20"
                            />
                            <op id="A-monitor-interval-10" interval="10"
                                name="monitor" timeout="10s"
                            />
                            <op id="A-reload-interval-0s" interval="0s"
                                name="reload" timeout="20"
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
            operation_list=[
                {"name": "monitor", "timeout": "10s", "interval": "10"}
            ],
        )

    def test_sanitize_operation_id_from_agent(self):
        self.config.runner.pcmk.load_agent(
            agent_filename=(
                "resource_agent_ocf_heartbeat_dummy_insane_action.xml"
            ),
        )
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(resources=self.fixture_sanitized_operation)
        create(self.env_assist.get_env())

    def test_sanitize_operation_id_from_user(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(resources=self.fixture_sanitized_operation)
        create(
            self.env_assist.get_env(),
            operation_list=[
                {"name": "moni*tor", "timeout": "20", "interval": "20"}
            ],
            allow_invalid_operation=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="operation name",
                    option_value="moni*tor",
                    allowed_values=[
                        "start",
                        "stop",
                        "monitor",
                        "reload",
                        "migrate_to",
                        "migrate_from",
                        "meta-data",
                        "validate-all",
                    ],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_resource_with_operation_depth(self):
        self.config.runner.pcmk.load_agent(
            stdout="""
                <resource-agent name="Dummy">
                    <version>1.0</version>
                    <shortdesc>Example stateless resource agent</shortdesc>
                    <parameters/>
                    <actions>
                        <action
                            name="monitor" timeout="20" interval="10" depth="0"
                        />
                        <action
                            name="monitor" timeout="20" interval="30" depth="10"
                        />
                    </actions>
                </resource-agent>
            """
        )
        self.config.runner.cib.load()
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                        <operations>
                            <op id="A-monitor-interval-10"
                                interval="10" name="monitor" timeout="20"
                            />
                            <op id="A-monitor-interval-30"
                                interval="30" name="monitor" timeout="20"
                            >
                                <instance_attributes
                                    id="A-monitor-interval-30-instance_attributes"
                                >
                                    <nvpair
                                        id="A-monitor-interval-30-instance_attributes-OCF_CHECK_LEVEL"
                                        name="OCF_CHECK_LEVEL" value="10"
                                    />
                                </instance_attributes>
                            </op>
                        </operations>
                    </primitive>
                </resources>
            """
        )
        create(self.env_assist.get_env())

    def test_unique_option(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive class="ocf" id="X" provider="heartbeat"
                        type="Dummy"
                    >
                        <instance_attributes id="X-instance_attributes">
                            <nvpair
                                id="X-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="A" provider="pacemaker"
                        type="Dummy"
                    >
                        <instance_attributes id="A-instance_attributes">
                            <nvpair
                                id="A-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="B" provider="heartbeat"
                        type="Dummy"
                    >
                        <instance_attributes id="B-instance_attributes">
                            <nvpair
                                id="B-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                    </primitive>
                </resources>
            """,
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.create(
                self.env_assist.get_env(),
                "C",
                "ocf:heartbeat:Dummy",
                operation_list=[],
                meta_attributes={},
                instance_attributes={"state": "1"},
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_INSTANCE_ATTR_VALUE_NOT_UNIQUE,
                    instance_attr_name="state",
                    instance_attr_value="1",
                    agent_name="ocf:heartbeat:Dummy",
                    resource_id_list=["B", "X"],
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_unique_option_forced(self):
        instance_attributes = {"state": "1"}
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive class="ocf" id="X" provider="heartbeat"
                        type="Dummy"
                    >
                        <instance_attributes id="X-instance_attributes">
                            <nvpair
                                id="X-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="A" provider="pacemaker"
                        type="Dummy"
                    >
                        <instance_attributes id="A-instance_attributes">
                            <nvpair
                                id="A-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="B" provider="heartbeat"
                        type="Dummy"
                    >
                        <instance_attributes id="B-instance_attributes">
                            <nvpair
                                id="B-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                    </primitive>
                </resources>
            """,
        )
        self.config.runner.pcmk.resource_agent_self_validation(
            instance_attributes
        )
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive class="ocf" id="X" provider="heartbeat"
                        type="Dummy"
                    >
                        <instance_attributes id="X-instance_attributes">
                            <nvpair
                                id="X-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="A" provider="pacemaker"
                        type="Dummy"
                    >
                        <instance_attributes id="A-instance_attributes">
                            <nvpair
                                id="A-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="B" provider="heartbeat"
                        type="Dummy"
                    >
                        <instance_attributes id="B-instance_attributes">
                            <nvpair
                                id="B-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="C" provider="heartbeat"
                        type="Dummy"
                    >
                        <instance_attributes id="C-instance_attributes">
                            <nvpair
                                id="C-instance_attributes-state"
                                name="state"
                                value="1"
                            />
                        </instance_attributes>
                        <operations>
                            <op id="C-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                </resources>
            """
        )
        resource.create(
            self.env_assist.get_env(),
            "C",
            "ocf:heartbeat:Dummy",
            operation_list=[],
            meta_attributes={},
            instance_attributes=instance_attributes,
            use_default_operations=False,
            allow_invalid_instance_attributes=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_INSTANCE_ATTR_VALUE_NOT_UNIQUE,
                    instance_attr_name="state",
                    instance_attr_value="1",
                    agent_name="ocf:heartbeat:Dummy",
                    resource_id_list=["B", "X"],
                )
            ]
        )

    def test_cib_upgrade_on_onfail_demote(self):
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load(
            filename="cib-empty-3.3.xml",
            name="load_cib_old_version",
        )
        self.config.runner.cib.upgrade()
        self.config.runner.cib.load(filename="cib-empty-3.4.xml")
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive class="ocf" id="A" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="A-migrate_from-interval-0s" interval="0s"
                                name="migrate_from" timeout="20"
                            />
                            <op id="A-migrate_to-interval-0s" interval="0s"
                                name="migrate_to" timeout="20"
                            />
                            <op id="A-monitor-interval-10" interval="10"
                                name="monitor" timeout="10" on-fail="demote"
                            />
                            <op id="A-reload-interval-0s" interval="0s"
                                name="reload" timeout="20"
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
            operation_list=[
                {
                    "name": "monitor",
                    "timeout": "10",
                    "interval": "10",
                    "on-fail": "demote",
                }
            ],
        )
        self.env_assist.assert_reports(
            [fixture.info(reports.codes.CIB_UPGRADE_SUCCESSFUL)]
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class CreateWait(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_primitive_simplest,
            wait=TIMEOUT,
        )

    def test_fail_wait(self):
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_primitive_simplest,
            wait=TIMEOUT,
            exception=LibraryError(
                reports.item.ReportItem.error(
                    reports.messages.WaitForIdleTimedOut(wait_error_message)
                )
            ),
            instead="env.push_cib",
        )
        self.env_assist.assert_raise_library_error(
            lambda: create(self.env_assist.get_env(), wait=TIMEOUT),
            [fixture.report_wait_for_idle_timed_out(wait_error_message)],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED)]
        )

    def test_wait_ok_run_fail(self):
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(failed="true")
        )

        self.env_assist.assert_raise_library_error(
            lambda: create(self.env_assist.get_env(), wait=TIMEOUT)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_wait_ok_run_ok(self):
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml()
        )
        create(self.env_assist.get_env(), wait=TIMEOUT)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": ["node1"]},
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_wait_ok_disable_fail(self):
        (
            self.config.runner.pcmk.load_state(
                resources=fixture_state_resources_xml()
            ).env.push_cib(
                resources=fixture_cib_resources_xml_simplest_disabled,
                wait=TIMEOUT,
                instead="env.push_cib",
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: create(
                self.env_assist.get_env(), wait=TIMEOUT, disabled=True
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": ["node1"]},
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_wait_ok_disable_ok(self):
        (
            self.config.runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            ).env.push_cib(
                resources=fixture_cib_resources_xml_simplest_disabled,
                wait=TIMEOUT,
                instead="env.push_cib",
            )
        )

        create(self.env_assist.get_env(), wait=TIMEOUT, disabled=True)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_wait_ok_disable_ok_by_target_role(self):
        (
            self.config.runner.pcmk.load_state(
                resources=fixture_state_resources_xml(role="Stopped")
            ).env.push_cib(
                resources=fixture_cib_resources_xml_simplest_disabled,
                wait=TIMEOUT,
                instead="env.push_cib",
            )
        )
        create(
            self.env_assist.get_env(),
            wait=TIMEOUT,
            meta_attributes={"target-role": "Stopped"},
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )


class CreateInGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()

    def test_simplest_resource(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_group_simplest
        )
        create_group(self.env_assist.get_env(), wait=False)

    def test_cib_upgrade_on_onfail_demote(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.3.xml",
            instead="runner.cib.load",
            name="load_cib_old_version",
        )
        self.config.runner.cib.upgrade()
        self.config.runner.cib.load(filename="cib-empty-3.4.xml")
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources="""
                <resources>
                    <group id="G">
                        <primitive class="ocf" id="A" provider="heartbeat"
                            type="Dummy"
                        >
                            <operations>
                                <op id="A-migrate_from-interval-0s"
                                    interval="0s" name="migrate_from"
                                    timeout="20"
                                />
                                <op id="A-migrate_to-interval-0s"
                                    interval="0s" name="migrate_to"
                                    timeout="20"
                                />
                                <op id="A-monitor-interval-10" interval="10"
                                    name="monitor" timeout="10" on-fail="demote"
                                />
                                <op id="A-reload-interval-0s" interval="0s"
                                    name="reload" timeout="20"
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

        create_group(
            self.env_assist.get_env(),
            operation_list=[
                {
                    "name": "monitor",
                    "timeout": "10",
                    "interval": "10",
                    "on-fail": "demote",
                }
            ],
            wait=False,
        )
        self.env_assist.assert_reports(
            [fixture.info(reports.codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_resource_self_validation_failure_default(self):
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
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
            resources=fixture_cib_resources_xml_group_simplest
        )

        create_group(self.env_assist.get_env(), wait=False)
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_AUTO_ON_WITH_WARNINGS
                ),
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                ),
            ]
        )

    def test_resource_self_validation_failure(self):
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
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
            lambda: create_group(
                self.env_assist.get_env(),
                enable_agent_self_validation=True,
                wait=False,
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                    force_code=reports.codes.FORCE,
                ),
            ]
        )

    def test_fail_wait(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_group_simplest,
            wait=TIMEOUT,
            exception=LibraryError(
                reports.item.ReportItem.error(
                    reports.messages.WaitForIdleTimedOut(wait_error_message)
                )
            ),
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_group(self.env_assist.get_env()),
            [fixture.report_wait_for_idle_timed_out(wait_error_message)],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED)]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_run_fail(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_group_simplest, wait=TIMEOUT
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(failed="true")
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_group(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_DOES_NOT_RUN, resource_id="A"
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_run_ok(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_group_simplest, wait=TIMEOUT
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml()
        )
        create_group(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": ["node1"]},
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_disable_fail(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_group_simplest_disabled,
            wait=TIMEOUT,
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml()
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_group(self.env_assist.get_env(), disabled=True)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": ["node1"]},
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_disable_ok(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_group_simplest_disabled,
            wait=TIMEOUT,
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(role="Stopped")
        )
        create_group(self.env_assist.get_env(), disabled=True)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_disable_ok_by_target_role(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_group_simplest_disabled,
            wait=TIMEOUT,
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(role="Stopped")
        )
        create_group(
            self.env_assist.get_env(),
            meta_attributes={"target-role": "Stopped"},
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )


class CreateAsClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.load_agent()
        self.config.runner.cib.load()

    def test_simplest_resource(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_clone_simplest
        )
        create_clone(self.env_assist.get_env(), wait=False)

    def test_resource_self_validation_failure_default(self):
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
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
            resources=fixture_cib_resources_xml_clone_simplest
        )
        create_clone(self.env_assist.get_env(), wait=False)
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_AUTO_ON_WITH_WARNINGS
                ),
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                ),
            ]
        )

    def test_resource_self_validation_failure(self):
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
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
            lambda: create_clone(
                self.env_assist.get_env(), enable_agent_self_validation=True
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                    force_code=reports.codes.FORCE,
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_custom_clone_id(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_clone_custom_id
        )
        create_clone(
            self.env_assist.get_env(), wait=False, clone_id="CustomCloneId"
        )

    def test_custom_clone_id_error_invalid_id(self):
        self.env_assist.assert_raise_library_error(
            lambda: create_clone(
                self.env_assist.get_env(), wait=False, clone_id="1invalid"
            ),
        )
        self.env_assist.assert_reports(
            [fixture.report_invalid_id("1invalid", "1")],
        )

    def test_custom_clone_id_error_id_already_exist(self):
        self.config.remove(name="runner.cib.load")
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive class="ocf" id="C" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="C-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"/>
                        </operations>
                    </primitive>
                </resources>
            """,
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_clone(
                self.env_assist.get_env(), wait=False, clone_id="C"
            ),
        )
        self.env_assist.assert_reports([fixture.report_id_already_exist("C")])

    def test_cib_upgrade_on_onfail_demote(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.3.xml",
            instead="runner.cib.load",
            name="load_cib_old_version",
        )
        self.config.runner.cib.upgrade()
        self.config.runner.cib.load(filename="cib-empty-3.4.xml")
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources="""<resources>
                <clone id="A-clone">
                    <primitive class="ocf" id="A" provider="heartbeat"
                        type="Dummy"
                    >
                        <operations>
                            <op id="A-migrate_from-interval-0s" interval="0s"
                                name="migrate_from" timeout="20"
                            />
                            <op id="A-migrate_to-interval-0s" interval="0s"
                                name="migrate_to" timeout="20"
                            />
                            <op id="A-monitor-interval-10" interval="10"
                                name="monitor" timeout="10" on-fail="demote"
                            />
                            <op id="A-reload-interval-0s" interval="0s"
                                name="reload" timeout="20"
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
            </resources>"""
        )

        create_clone(
            self.env_assist.get_env(),
            operation_list=[
                {
                    "name": "monitor",
                    "timeout": "10",
                    "interval": "10",
                    "on-fail": "demote",
                }
            ],
            wait=False,
        )
        self.env_assist.assert_reports(
            [fixture.info(reports.codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_fail_wait(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_clone_simplest,
            wait=TIMEOUT,
            exception=LibraryError(
                reports.item.ReportItem.error(
                    reports.messages.WaitForIdleTimedOut(wait_error_message)
                )
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_clone(self.env_assist.get_env()),
            [fixture.report_wait_for_idle_timed_out(wait_error_message)],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED)]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_run_fail(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_clone_simplest, wait=TIMEOUT
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(failed="true")
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_clone(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_DOES_NOT_RUN, resource_id="A"
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_run_ok(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_clone_simplest, wait=TIMEOUT
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml()
        )
        create_clone(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": ["node1"]},
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_disable_fail(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_clone_simplest_disabled,
            wait=TIMEOUT,
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml()
        )

        self.env_assist.assert_raise_library_error(
            lambda: create_clone(self.env_assist.get_env(), disabled=True)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": ["node1"]},
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_disable_ok(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=fixture_cib_resources_xml_clone_simplest_disabled,
            wait=TIMEOUT,
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(role="Stopped")
        )
        create_clone(self.env_assist.get_env(), disabled=True)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_disable_ok_by_target_role(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
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
                                <op id="A-migrate_from-interval-0s"
                                    interval="0s" name="migrate_from"
                                    timeout="20"
                                />
                                <op id="A-migrate_to-interval-0s"
                                    interval="0s" name="migrate_to"
                                    timeout="20"
                                />
                                <op id="A-monitor-interval-10" interval="10"
                                    name="monitor" timeout="20"
                                />
                                <op id="A-reload-interval-0s" interval="0s"
                                    name="reload" timeout="20"
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
            """,
            wait=TIMEOUT,
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(role="Stopped")
        )
        create_clone(
            self.env_assist.get_env(),
            meta_attributes={"target-role": "Stopped"},
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_disable_ok_by_target_role_in_clone(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources="""
                <resources>
                    <clone id="A-clone">
                        <primitive class="ocf" id="A" provider="heartbeat"
                            type="Dummy"
                        >
                            <operations>
                                <op id="A-migrate_from-interval-0s"
                                    interval="0s" name="migrate_from"
                                    timeout="20"
                                />
                                <op id="A-migrate_to-interval-0s"
                                    interval="0s" name="migrate_to"
                                    timeout="20"
                                />
                                <op id="A-monitor-interval-10" interval="10"
                                    name="monitor" timeout="20"
                                />
                                <op id="A-reload-interval-0s" interval="0s"
                                    name="reload" timeout="20"
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
            """,
            wait=TIMEOUT,
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(role="Stopped")
        )
        create_clone(
            self.env_assist.get_env(), clone_options={"target-role": "Stopped"}
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_disable_ok_by_clone_max(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources="""
                <resources>
                    <clone id="A-clone">
                        <primitive class="ocf" id="A" provider="heartbeat"
                            type="Dummy"
                        >
                            <operations>
                                <op id="A-migrate_from-interval-0s"
                                    interval="0s" name="migrate_from"
                                    timeout="20"
                                />
                                <op id="A-migrate_to-interval-0s"
                                    interval="0s" name="migrate_to"
                                    timeout="20"
                                />
                                <op id="A-monitor-interval-10" interval="10"
                                    name="monitor" timeout="20"
                                />
                                <op id="A-reload-interval-0s" interval="0s"
                                    name="reload" timeout="20"
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
            """,
            wait=TIMEOUT,
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(role="Stopped")
        )
        create_clone(
            self.env_assist.get_env(), clone_options={"clone-max": "0"}
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_disable_ok_by_clone_node_max(self):
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources="""
                <resources>
                    <clone id="A-clone">
                        <primitive class="ocf" id="A" provider="heartbeat"
                            type="Dummy"
                        >
                            <operations>
                                <op id="A-migrate_from-interval-0s"
                                    interval="0s" name="migrate_from"
                                    timeout="20"
                                />
                                <op id="A-migrate_to-interval-0s"
                                    interval="0s" name="migrate_to"
                                    timeout="20"
                                />
                                <op id="A-monitor-interval-10" interval="10"
                                    name="monitor" timeout="20"
                                />
                                <op id="A-reload-interval-0s" interval="0s"
                                    name="reload" timeout="20"
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
            """,
            wait=TIMEOUT,
        )
        self.config.runner.pcmk.load_state(
            resources=fixture_state_resources_xml(role="Stopped")
        )
        create_clone(
            self.env_assist.get_env(), clone_options={"clone-node-max": "0"}
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id="A",
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )


class CreateAsCloneFailures(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def _test_non_ocf_param(self, attr):
        agent = ResourceAgentName("systemd", None, "chronyd")
        self.config.runner.pcmk.load_agent(agent_name=agent.full_name)
        self.env_assist.assert_raise_library_error(
            lambda: create_clone(
                self.env_assist.get_env(),
                agent=agent.full_name,
                clone_options={attr: "1"},
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_CLONE_INCOMPATIBLE_META_ATTRIBUTES,
                    attribute=attr,
                    resource_agent=agent.to_dto(),
                    resource_id=None,
                    group_id=None,
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_non_ocf_globally_unique(self):
        self._test_non_ocf_param("globally-unique")

    def test_non_ocf_promotable(self):
        self._test_non_ocf_param("promotable")

    def test_promotable_not_supported(self):
        agent = ResourceAgentName("ocf", "pacemaker", "Dummy")
        self.config.runner.pcmk.load_agent(agent_name=agent.full_name)
        self.env_assist.assert_raise_library_error(
            lambda: create_clone(
                self.env_assist.get_env(),
                agent=agent.full_name,
                clone_options={"promotable": "1"},
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_CLONE_INCOMPATIBLE_META_ATTRIBUTES,
                    attribute="promotable",
                    resource_agent=agent.to_dto(),
                    resource_id=None,
                    group_id=None,
                    force_code=reports.codes.FORCE,
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_promotable_not_supported_forced(self):
        agent = ResourceAgentName("ocf", "pacemaker", "Dummy")
        self.config.runner.pcmk.load_agent(agent_name=agent.full_name)
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
            standard=agent.standard,
            provider=agent.provider,
            agent_type=agent.type,
            output="""<output source="stderr">error</output>""",
            returncode=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_clone(
                self.env_assist.get_env(),
                agent=agent.full_name,
                clone_options={"promotable": "1"},
                allow_incompatible_clone_meta_attributes=True,
                enable_agent_self_validation=True,
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_CLONE_INCOMPATIBLE_META_ATTRIBUTES,
                    attribute="promotable",
                    resource_agent=agent.to_dto(),
                    resource_id=None,
                    group_id=None,
                ),
                fixture.error(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="error",
                    force_code=reports.codes.FORCE,
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )


class CreateInToBundle(TestCase):
    fixture_empty_resources = "<resources />"

    fixture_resources_pre = """
        <resources>
            <bundle id="B">
                <network control-port="12345" ip-range-start="192.168.100.200"/>
            </bundle>
        </resources>
    """

    fixture_resource_post_simple_without_network = """
        <resources>
            <bundle id="B">
                {network}
                <primitive
                    class="ocf" id="A" provider="heartbeat" type="Dummy"
                >
                    <operations>
                        <op id="A-migrate_from-interval-0s" interval="0s"
                            name="migrate_from" timeout="20"
                        />
                        <op id="A-migrate_to-interval-0s" interval="0s"
                            name="migrate_to" timeout="20"
                        />
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor" timeout="20" {onfail}
                        />
                        <op id="A-reload-interval-0s" interval="0s" name="reload"
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
            </bundle>
        </resources>
    """

    # fmt: off
    fixture_resources_post_simple = (
        fixture_resource_post_simple_without_network.format(
            network="""
                <network control-port="12345" ip-range-start="192.168.100.200"/>
            """,
            onfail=""
        )
    )
    # fmt: on

    fixture_resources_post_disabled = """
        <resources>
            <bundle id="B">
                <network control-port="12345" ip-range-start="192.168.100.200"/>
                <primitive
                    class="ocf" id="A" provider="heartbeat" type="Dummy"
                >
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="A-migrate_from-interval-0s" interval="0s"
                            name="migrate_from" timeout="20"
                        />
                        <op id="A-migrate_to-interval-0s" interval="0s"
                            name="migrate_to" timeout="20"
                        />
                        <op id="A-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="A-reload-interval-0s" interval="0s" name="reload"
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

    def setUp(self):
        self.env_assist, self.config = get_env_tools(
            test_case=self,
            base_cib_filename="cib-empty.xml",
        )
        self.config.runner.pcmk.load_agent()

    def test_cib_upgrade_on_onfail_demote(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.3.xml",
            name="load_cib_old_version",
        )
        self.config.runner.cib.upgrade()
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", resources=self.fixture_resources_pre
        )
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=self.fixture_resource_post_simple_without_network.format(
                network="""
                    <network
                        control-port="12345" ip-range-start="192.168.100.200"
                    />
                """,
                onfail='on-fail="demote"',
            )
        )

        create_bundle(
            self.env_assist.get_env(),
            operation_list=[
                {
                    "name": "monitor",
                    "timeout": "20",
                    "interval": "10",
                    "on-fail": "demote",
                }
            ],
            wait=False,
        )
        self.env_assist.assert_reports(
            [fixture.info(reports.codes.CIB_UPGRADE_SUCCESSFUL)]
        )

    def test_simplest_resource(self):
        self.config.runner.cib.load(resources=self.fixture_resources_pre)
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(resources=self.fixture_resources_post_simple)
        create_bundle(self.env_assist.get_env(), wait=False)

    def test_bundle_doesnt_exist(self):
        self.config.runner.cib.load(resources=self.fixture_empty_resources)
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env(), wait=False),
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="B",
                    expected_types=["bundle"],
                    context_type="resources",
                    context_id="",
                )
            ],
            expected_in_processor=False,
        )

    def test_id_not_bundle(self):
        self.config.runner.cib.load(
            resources="""
                    <resources>
                        <primitive id="B"/>
                    </resources>
                """
        )
        self.config.runner.pcmk.resource_agent_self_validation({})

        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env(), wait=False),
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="B",
                    expected_types=["bundle"],
                    current_type="primitive",
                )
            ],
            expected_in_processor=False,
        )

    def test_bundle_not_empty(self):
        self.config.runner.cib.load(
            resources="""
                    <resources>
                        <bundle id="B">
                            <network control-port="12345"/>
                            <primitive id="P"/>
                        </bundle>
                    </resources>
                """
        )
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env(), wait=False),
            [
                fixture.error(
                    reports.codes.RESOURCE_BUNDLE_ALREADY_CONTAINS_A_RESOURCE,
                    bundle_id="B",
                    resource_id="P",
                )
            ],
            expected_in_processor=False,
        )

    def test_wait_fail(self):
        self.config.runner.cib.load(resources=self.fixture_resources_pre)
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=self.fixture_resources_post_simple,
            wait=TIMEOUT,
            exception=LibraryError(
                reports.item.ReportItem.error(
                    reports.messages.WaitForIdleTimedOut(wait_error_message)
                )
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env()),
            [
                fixture.report_wait_for_idle_timed_out(wait_error_message),
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED)]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_run_ok(self):
        self.config.runner.cib.load(resources=self.fixture_resources_pre)
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=self.fixture_resources_post_simple, wait=TIMEOUT
        )
        self.config.runner.pcmk.load_state(
            resources=self.fixture_status_running_with_primitive
        )
        create_bundle(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.report_resource_running("A", {"Started": ["node1"]}),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_ok_run_fail(self):
        self.config.runner.cib.load(resources=self.fixture_resources_pre)
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=self.fixture_resources_post_simple, wait=TIMEOUT
        )
        self.config.runner.pcmk.load_state(
            resources=self.fixture_status_primitive_not_running
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_DOES_NOT_RUN, resource_id="A"
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_disabled_wait_ok_not_running(self):
        self.config.runner.cib.load(resources=self.fixture_resources_pre)
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=self.fixture_resources_post_disabled, wait=TIMEOUT
        )
        self.config.runner.pcmk.load_state(
            resources=self.fixture_status_primitive_not_running
        )
        create_bundle(self.env_assist.get_env(), disabled=True)
        self.env_assist.assert_reports(
            [
                fixture.report_resource_not_running("A"),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_disabled_wait_ok_running(self):
        self.config.runner.cib.load(resources=self.fixture_resources_pre)
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=self.fixture_resources_post_disabled, wait=TIMEOUT
        )
        self.config.runner.pcmk.load_state(
            resources=self.fixture_status_running_with_primitive
        )
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env(), disabled=True)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    resource_id="A",
                    roles_with_nodes={"Started": ["node1"]},
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_no_port_no_ip(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <bundle id="B"/>
                </resources>
            """
        )
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.env_assist.assert_raise_library_error(
            lambda: create_bundle(self.env_assist.get_env(), wait=False)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B",
                    inner_resource_id="A",
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_no_port_no_ip_forced(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <bundle id="B"/>
                </resources>
            """
        )
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=(
                self.fixture_resource_post_simple_without_network.format(
                    network="", onfail=""
                )
            )
        )
        create_bundle(
            self.env_assist.get_env(),
            wait=False,
            allow_not_accessible_resource=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    bundle_id="B",
                    inner_resource_id="A",
                )
            ]
        )

    def _test_with_network_defined(self, network):
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    <bundle id="B">
                        {network}
                    </bundle>
                </resources>
            """
        )
        self.config.runner.pcmk.resource_agent_self_validation({})
        self.config.env.push_cib(
            resources=(
                self.fixture_resource_post_simple_without_network.format(
                    network=network, onfail=""
                )
            )
        )
        create_bundle(self.env_assist.get_env(), wait=False)

    def test_port_defined(self):
        self._test_with_network_defined('<network control-port="12345"/>')

    def test_ip_range_defined(self):
        self._test_with_network_defined(
            '<network ip-range-start="192.168.100.200"/>'
        )

    def test_resource_self_validation_failure_default(self):
        self.config.runner.cib.load(resources=self.fixture_resources_pre)
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
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
        self.config.env.push_cib(resources=self.fixture_resources_post_simple)

        create_bundle(self.env_assist.get_env(), wait=False)
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_AUTO_ON_WITH_WARNINGS
                ),
                fixture.warn(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                ),
            ]
        )

    def test_resource_self_validation_failure(self):
        self.config.runner.cib.load()
        self.config.runner.pcmk.resource_agent_self_validation(
            {},
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
            lambda: create_bundle(
                self.env_assist.get_env(), enable_agent_self_validation=True
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.AGENT_SELF_VALIDATION_RESULT,
                    result="not ignored\nfirst issue\nanother one",
                    force_code=reports.codes.FORCE,
                ),
                fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )


class StonithIsForbiddenMixin:
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def _command(self):
        raise NotImplementedError

    def test_stonith_is_forbidden(self):
        self.env_assist.assert_raise_library_error(self._command)
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COMMAND_ARGUMENT_TYPE_MISMATCH,
                    not_accepted_type="stonith resource",
                    command_to_use_instead="stonith create",
                ),
            ]
        )


class StonithIsForbiddenInCreate(StonithIsForbiddenMixin, TestCase):
    def _command(self):
        return create(
            self.env_assist.get_env(),
            wait=False,
            agent_name="stonith:fence_simple",
        )


class StonithIsForbiddenInBundle(StonithIsForbiddenMixin, TestCase):
    def _command(self):
        return create_bundle(
            self.env_assist.get_env(), wait=False, agent="stonith:fence_simple"
        )


class StonithIsForbiddenInClone(StonithIsForbiddenMixin, TestCase):
    def _command(self):
        return create_clone(
            self.env_assist.get_env(), wait=False, agent="stonith:fence_simple"
        )


class StonithIsForbiddenInGroup(StonithIsForbiddenMixin, TestCase):
    def _command(self):
        return create_group(
            self.env_assist.get_env(), wait=False, agent="stonith:fence_simple"
        )

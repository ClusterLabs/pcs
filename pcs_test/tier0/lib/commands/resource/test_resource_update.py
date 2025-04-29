from unittest import (
    TestCase,
)

from pcs.common import (
    reports,
)
from pcs.lib.commands import resource
from pcs.lib.resource_agent.types import ResourceAgentName

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_raise_library_error
from pcs_test.tools.command_env import get_env_tools

_AGENT_NAME_PCMK_DUMMY = ResourceAgentName("ocf", "pacemaker", "Dummy")
_AGENT_NAME_PCMK_STATEFUL = ResourceAgentName("ocf", "pacemaker", "Stateful")


def fixture_primitive(
    resource_agent=_AGENT_NAME_PCMK_DUMMY,
    is_cloned=False,
    is_grouped=False,
    meta_nvpairs_xml="",
    primitive_inner="",
):
    meta_attributes_xml = meta_attributes_xml_clone = ""
    if meta_nvpairs_xml:
        if is_cloned:
            meta_attributes_xml_clone = f"""
                <meta_attributes id="A-clone-meta_attributes">
                    {meta_nvpairs_xml}
                </meta_attributes>
            """
        else:
            meta_attributes_xml = f"""
                <meta_attributes id="A-meta_attributes">
                    {meta_nvpairs_xml}
                </meta_attributes>
            """

    clone_start = clone_end = ""
    if is_cloned:
        clone_start = """<clone id="A-clone">"""
        clone_end = "</clone>"

    group_start = group_end = ""
    if is_grouped:
        group_start = """<group id="G">"""
        group_end = "</group>"

    return f"""
        <resources>
            {clone_start}
                {group_start}
                    <primitive class="{resource_agent.standard}" id="A" 
                        provider="{resource_agent.provider}"
                        type="{resource_agent.type}"
                    >
                        {meta_attributes_xml}
                        {primitive_inner}
                    </primitive>
                {group_end}
                {meta_attributes_xml_clone}
            {clone_end}
        </resources>
    """


def fixture_resource_meta_stateful(
    use_legacy_roles=False,
    meta_nvpairs="",
    clone_inner="",
    is_grouped=False,
    is_promotable=True,
):
    clone_el_tag = "clone"
    role_promoted = "Promoted"
    role_unpromoted = "Unpromoted"

    if use_legacy_roles:
        clone_el_tag = "master" if is_promotable else "clone"
        role_promoted = "Master"
        role_unpromoted = "Slave"
    elif is_promotable:
        meta_nvpairs += """
            <nvpair id="A-clone-meta_attributes-promotable" name="promotable"
                value="true"
            />
        """

    meta_attributes_xml = ""
    if meta_nvpairs:
        meta_attributes_xml = f"""
            <meta_attributes id="A-clone-meta_attributes">
                {meta_nvpairs}
            </meta_attributes>
        """

    group_start = group_end = ""
    if is_grouped:
        group_start = """<group id="G">"""
        group_end = "</group>"

    return f"""
        <resources>
            <{clone_el_tag} id="A-clone">
                {group_start}
                    <primitive id="A" class="ocf" type="Stateful"
                        provider="pacemaker"
                    >
                        <operations>
                            <op name="demote" interval="0s" timeout="10s"
                                id="A-demote-interval-0s"
                            />
                            <op name="monitor" interval="10s" timeout="20s"
                                role="{role_promoted}" id="A-monitor-interval-10s"
                            />
                            <op name="monitor" interval="11s" timeout="20s"
                                role="{role_unpromoted}" id="A-monitor-interval-11s"
                            />
                            <op name="notify" interval="0s" timeout="5s"
                                id="A-notify-interval-0s"
                            />
                            <op name="promote" interval="0s" timeout="10s"
                                id="A-promote-interval-0s"
                            />
                            <op name="reload-agent" interval="0s" timeout="10s"
                                id="A-reload-agent-interval-0s"
                            />
                            <op name="start" interval="0s" timeout="20s"
                                id="A-start-interval-0s"
                            />
                            <op name="stop" interval="0s" timeout="20s"
                                id="A-stop-interval-0s"
                            />
                        </operations>
                    </primitive>
                {group_end}
                {meta_attributes_xml}
                {clone_inner}
            </{clone_el_tag}>
        </resources>
    """


class UpdateMeta(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_update_nonexistent_resource(self):
        self.config.runner.cib.load(filename="cib-resources.xml")
        self.env_assist.assert_raise_library_error(
            lambda: resource.update_meta(
                self.env_assist.get_env(), "Rx", {"priority": "1"}, []
            ),
            reports=[
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="Rx",
                    expected_types=["resource"],
                    context_type="",
                    context_id="",
                ),
            ],
            expected_in_processor=False,
        )

    def test_wrong_id_type_found(self):
        self.config.runner.cib.load(
            tags="""
            <tags>
              <tag id="all-vms">
                <obj_ref id="vm1"/>
                <obj_ref id="vm2"/>
              </tag>
            </tags>
                """
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.update_meta(
                self.env_assist.get_env(), "all-vms", {"priority": "1"}, []
            ),
            reports=[
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="all-vms",
                    expected_types=["resource"],
                    current_type="tag",
                ),
            ],
            expected_in_processor=False,
        )

    def test_meta_attr_elem_missing(self):
        self.config.runner.cib.load(resources=fixture_primitive())
        self.config.corosync_conf.load()
        self.config.env.push_cib(
            resources=fixture_primitive(
                meta_nvpairs_xml="""
                    <nvpair id="A-meta_attributes-priority" name="priority"
                        value="1"
                    />
                """
            )
        )
        resource.update_meta(
            self.env_assist.get_env(), "A", {"priority": "1"}, []
        )

    def test_no_new_attrs_element_not_added(self):
        self.config.runner.cib.load(resources=fixture_primitive())
        self.config.corosync_conf.load()
        self.config.env.push_cib(resources=fixture_primitive())
        resource.update_meta(
            self.env_assist.get_env(), "A", {"priority": ""}, []
        )

    def test_existing_meta_attr_elem_add_remove(self):
        self.config.runner.cib.load(
            resources=fixture_primitive(
                meta_nvpairs_xml="""
                    <nvpair id="A-meta_attributes-resource-stickiness"
                        name="resource-stickiness" value="0"
                    />
                    <nvpair id="A-meta_attributes-failure-timeout"
                    name="failure-timeout" value="10s"
                    />
                """,
            )
        )
        self.config.corosync_conf.load()
        self.config.env.push_cib(
            resources=fixture_primitive(
                meta_nvpairs_xml="""
                    <nvpair id="A-meta_attributes-resource-stickiness"
                        name="resource-stickiness" value="0"
                    />
                    <nvpair id="A-meta_attributes-priority" name="priority"
                        value="1"
                    />
                """,
            )
        )
        resource.update_meta(
            self.env_assist.get_env(),
            "A",
            {"priority": "1", "failure-timeout": ""},
            [],
        )

    def test_conflict_existing_node_name(self):
        self.config.runner.cib.load(
            resources=fixture_primitive(),
        )
        self.config.corosync_conf.load(node_name_list=["node1"])
        self.env_assist.assert_raise_library_error(
            lambda: resource.update_meta(
                self.env_assist.get_env(),
                "A",
                {"remote-node": "node1"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.GUEST_NODE_NAME_ALREADY_EXISTS,
                    node_name="node1",
                ),
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_ADD_GUEST,
                    reports.codes.FORCE,
                ),
            ]
        )

    def test_update_guest_attr_protected_force(self):
        self.config.runner.cib.load(
            resources=fixture_primitive(),
        )
        self.config.corosync_conf.load()
        self.config.env.push_cib(
            resources=fixture_primitive(
                meta_nvpairs_xml="""
                    <nvpair id="A-meta_attributes-remote-node"
                        name="remote-node" value="node1"
                    />
                """
            )
        )
        resource.update_meta(
            self.env_assist.get_env(),
            "A",
            {"remote-node": "node1"},
            [reports.codes.FORCE],
        )

        self.env_assist.assert_reports(
            [
                fixture.warn(reports.codes.USE_COMMAND_NODE_ADD_GUEST),
            ]
        )

    def test_update_legacy_clone_element_tag_and_reset_promotable(self):
        self.config.runner.cib.load(
            resources=fixture_resource_meta_stateful(
                use_legacy_roles=True,
            )
        )
        self.config.corosync_conf.load()
        agent = ResourceAgentName("ocf", "pacemaker", "Stateful")
        self.config.runner.pcmk.load_agent(agent_name=agent.full_name)
        self.config.env.push_cib(
            resources=fixture_resource_meta_stateful(
                meta_nvpairs="""
                    <nvpair id="A-clone-meta_attributes-priority"
                        name="priority" value="1"
                    />
                """,
                is_promotable=False,
            )
        )
        resource.update_meta(
            self.env_assist.get_env(),
            "A-clone",
            {"priority": "1", "promotable": ""},
            [],
        )


class UpdateMetaCheckCloneIncompatibleMetaAttrs(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success_cloned_primitive_priority(self):
        self.config.runner.cib.load(resources=fixture_primitive(is_cloned=True))
        self.config.corosync_conf.load()
        self.config.runner.pcmk.load_agent(
            agent_name=_AGENT_NAME_PCMK_DUMMY.full_name
        )
        self.config.env.push_cib(
            resources=fixture_primitive(
                is_cloned=True,
                meta_nvpairs_xml="""
                    <nvpair id="A-clone-meta_attributes-priority"
                        name="priority" value="1"
                    />
                """,
            )
        )
        resource.update_meta(
            self.env_assist.get_env(), "A-clone", {"priority": "1"}, []
        )

    def test_success_cloned_primitive_promotable(self):
        self.config.runner.cib.load(
            resources=fixture_primitive(
                resource_agent=_AGENT_NAME_PCMK_STATEFUL,
                is_cloned=True,
            )
        )
        self.config.corosync_conf.load()
        self.config.runner.pcmk.load_agent(
            agent_name=_AGENT_NAME_PCMK_STATEFUL.full_name
        )
        self.config.env.push_cib(
            resources=fixture_primitive(
                resource_agent=_AGENT_NAME_PCMK_STATEFUL,
                is_cloned=True,
                meta_nvpairs_xml="""
                    <nvpair id="A-clone-meta_attributes-promotable" 
                        name="promotable" value="true"
                    />
                """,
            )
        )
        resource.update_meta(
            self.env_assist.get_env(), "A-clone", {"promotable": "true"}, []
        )

    def test_success_cloned_primitive_promotable_ocf_old(self):
        # Despite the test name, agent older than OCF 1.1 can be promoted
        # because the old standard doesn't allow for promotability checks
        agent_name = ResourceAgentName("ocf", "heartbeat", "Dummy")
        self.config.runner.cib.load(
            resources=fixture_primitive(
                resource_agent=agent_name,
                is_cloned=True,
            )
        )
        self.config.corosync_conf.load()
        self.config.runner.pcmk.load_agent(agent_name=agent_name.full_name)
        self.config.env.push_cib(
            resources=fixture_primitive(
                resource_agent=agent_name,
                is_cloned=True,
                meta_nvpairs_xml="""
                    <nvpair id="A-clone-meta_attributes-promotable" 
                        name="promotable" value="true"
                    />
                """,
            )
        )
        resource.update_meta(
            self.env_assist.get_env(), "A-clone", {"promotable": "true"}, []
        )

    def test_fail_cloned_primitive_promotable_incompatible(self):
        self.config.runner.cib.load(
            resources=fixture_primitive(is_cloned=True),
        )
        self.config.corosync_conf.load()
        self.config.runner.pcmk.load_agent(
            agent_name=_AGENT_NAME_PCMK_DUMMY.full_name
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.update_meta(
                self.env_assist.get_env(),
                "A-clone",
                {"promotable": "true"},
                [],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_CLONE_INCOMPATIBLE_META_ATTRIBUTES,
                    attribute="promotable",
                    resource_agent=_AGENT_NAME_PCMK_DUMMY.to_dto(),
                    resource_id="A",
                    group_id=None,
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_fail_cloned_primitive_promotable_incompatible_force(self):
        self.config.runner.cib.load(
            resources=fixture_primitive(is_cloned=True),
        )
        self.config.corosync_conf.load()
        self.config.runner.pcmk.load_agent(
            agent_name=_AGENT_NAME_PCMK_DUMMY.full_name
        )
        self.config.env.push_cib(
            resources=fixture_primitive(
                is_cloned=True,
                meta_nvpairs_xml="""
                    <nvpair id="A-clone-meta_attributes-promotable"
                        name="promotable" value="true"
                    />
                """,
            )
        )
        resource.update_meta(
            self.env_assist.get_env(),
            "A-clone",
            {"promotable": "true"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_CLONE_INCOMPATIBLE_META_ATTRIBUTES,
                    attribute="promotable",
                    resource_agent=_AGENT_NAME_PCMK_DUMMY.to_dto(),
                    resource_id="A",
                    group_id=None,
                )
            ]
        )

    def _subtest_fail_cloned_primitive_non_ocf_incompatible_attrs(self, attr):
        # Cannot use real subtest because of env_assist call stack, it needs
        # initialization and teardown between test runs
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <clone id="non-ocf-clone">
                        <primitive id="non-ocf" class="systemd"
                          type="pcsmock" />
                    </clone>
                </resources>
            """,
        )
        self.config.corosync_conf.load()
        agent = ResourceAgentName("systemd", None, "pcsmock")
        self.env_assist.assert_raise_library_error(
            lambda: resource.update_meta(
                self.env_assist.get_env(),
                "non-ocf-clone",
                {attr: "true"},  # noqa: B023
                [],
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_CLONE_INCOMPATIBLE_META_ATTRIBUTES,
                    attribute=attr,
                    resource_agent=agent.to_dto(),
                    resource_id="non-ocf",
                    group_id=None,
                )
            ]
        )

    def test_fail_cloned_primitive_non_ocf_promotable(self):
        self._subtest_fail_cloned_primitive_non_ocf_incompatible_attrs(
            "promotable"
        )

    def test_fail_cloned_primitive_non_ocf_globally_unique(self):
        self._subtest_fail_cloned_primitive_non_ocf_incompatible_attrs(
            "globally-unique"
        )

    def test_fail_cloned_group_promotable(self):
        self.config.runner.cib.load(
            resources=fixture_primitive(is_cloned=True, is_grouped=True),
        )
        self.config.corosync_conf.load()
        self.config.runner.pcmk.load_agent(
            agent_name=_AGENT_NAME_PCMK_DUMMY.full_name
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.update_meta(
                self.env_assist.get_env(),
                "A-clone",
                {"promotable": "true"},
                [],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_CLONE_INCOMPATIBLE_META_ATTRIBUTES,
                    attribute="promotable",
                    resource_agent=_AGENT_NAME_PCMK_DUMMY.to_dto(),
                    resource_id="A",
                    group_id="G",
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_fail_cloned_group_promotable_force(self):
        self.config.runner.cib.load(
            resources=fixture_primitive(is_cloned=True, is_grouped=True),
        )
        self.config.corosync_conf.load()
        self.config.runner.pcmk.load_agent(
            agent_name=_AGENT_NAME_PCMK_DUMMY.full_name
        )
        self.config.env.push_cib(
            resources=fixture_primitive(
                is_cloned=True,
                is_grouped=True,
                meta_nvpairs_xml="""
                    <nvpair id="A-clone-meta_attributes-promotable"
                        name="promotable" value="true"
                    />
                """,
            )
        )
        resource.update_meta(
            self.env_assist.get_env(),
            "A-clone",
            {"promotable": "true"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_CLONE_INCOMPATIBLE_META_ATTRIBUTES,
                    attribute="promotable",
                    resource_agent=_AGENT_NAME_PCMK_DUMMY.to_dto(),
                    resource_id="A",
                    group_id="G",
                )
            ]
        )


class UpdateMetaRemoveUpdatedGuestNode(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def _update_guest_attr_success(
        self,
        old_node_addr="",
        new_node_addr="",
        is_nvset_empty=False,
        is_node_removed=False,
        is_forced=False,
        report_list=None,
    ):
        self.config.runner.cib.load(
            resources=fixture_primitive(
                meta_nvpairs_xml=f"""
                    <nvpair id="A-meta_attributes-remote-node"
                        name="remote-node" value="{old_node_addr}"
                    />
                """
                if old_node_addr
                else "",
            )
        )
        self.config.corosync_conf.load()
        self.config.env.push_cib(
            resources=fixture_primitive(
                # For removeal, we want to hack the fixture to get the meta
                # attributes element without nvpairs
                meta_nvpairs_xml=" "
                if is_nvset_empty
                else f"""
                    <nvpair id="A-meta_attributes-remote-node"
                        name="remote-node" value="{new_node_addr}"
                    />
                """
            )
        )
        if is_node_removed:
            self.config.runner.pcmk.remove_node(old_node_addr)
        env = self.env_assist.get_env()
        resource.update_meta(
            env,
            "A",
            {"remote-node": new_node_addr},
            [reports.codes.FORCE] if is_forced else [],
        )
        self.env_assist.assert_reports(report_list if report_list else [])

    def _update_guest_attr_fail(
        self, report_list, old_node_addr="", new_node_addr="", is_forced=False
    ):
        self.config.runner.cib.load(
            resources=fixture_primitive(
                meta_nvpairs_xml=f"""
                    <nvpair id="A-meta_attributes-remote-node"
                        name="remote-node" value="{old_node_addr}"
                    />
                """
                if old_node_addr
                else "",
            )
        )
        self.config.corosync_conf.load()
        env = self.env_assist.get_env()
        assert_raise_library_error(
            lambda: resource.update_meta(
                env,
                "A",
                {"remote-node": new_node_addr},
                [reports.codes.FORCE] if is_forced else [],
            )
        )
        self.env_assist.assert_reports(report_list)

    def test_not_called_add_remote_node(self):
        self._update_guest_attr_fail(
            new_node_addr="rnode",
            report_list=[
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_ADD_GUEST,
                    reports.codes.FORCE,
                ),
            ],
        )

    def test_not_called_add_remote_node_force(self):
        self._update_guest_attr_success(
            new_node_addr="rnode",
            is_forced=True,
            report_list=[
                fixture.warn(reports.codes.USE_COMMAND_NODE_ADD_GUEST),
            ],
        )

    def test_not_called_change_remote_node(self):
        self._update_guest_attr_fail(
            old_node_addr="rnode2",
            new_node_addr="rnode",
            report_list=[
                fixture.error(
                    reports.codes.USE_COMMAND_REMOVE_AND_ADD_GUEST_NODE,
                    reports.codes.FORCE,
                ),
            ],
        )

    def test_called_change_remote_node_force(self):
        self._update_guest_attr_success(
            old_node_addr="rnode2",
            new_node_addr="rnode",
            is_forced=True,
            is_node_removed=True,
            report_list=[
                fixture.warn(
                    reports.codes.USE_COMMAND_REMOVE_AND_ADD_GUEST_NODE
                ),
            ],
        )

    def test_not_called_fake_change_remote_node(self):
        self._update_guest_attr_fail(
            old_node_addr="rnode",
            new_node_addr="rnode",
            report_list=[
                fixture.error(
                    reports.codes.GUEST_NODE_NAME_ALREADY_EXISTS,
                    node_name="rnode",
                )
            ],
        )

    def test_not_called_fake_change_remote_node_force(self):
        self._update_guest_attr_fail(
            old_node_addr="rnode",
            new_node_addr="rnode",
            is_forced=True,
            report_list=[
                fixture.error(
                    reports.codes.GUEST_NODE_NAME_ALREADY_EXISTS,
                    node_name="rnode",
                )
            ],
        )

    def test_not_called_remove_remote_node(self):
        self._update_guest_attr_fail(
            old_node_addr="rnode2",
            new_node_addr="",
            report_list=[
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id=None,
                    force_code=reports.codes.FORCE,
                ),
            ],
        )

    def test_called_remove_remote_node_force(self):
        self._update_guest_attr_success(
            old_node_addr="rnode2",
            new_node_addr="",
            is_nvset_empty=True,
            is_node_removed=True,
            is_forced=True,
            report_list=[
                fixture.warn(
                    reports.codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id=None,
                ),
            ],
        )

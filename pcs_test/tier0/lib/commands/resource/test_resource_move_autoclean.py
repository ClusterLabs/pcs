# pylint: disable=too-many-lines
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.tools import xml_fromstring
from pcs.lib.commands.resource import move_autoclean
from pcs.lib.xml_tools import etree_to_str

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import (
    TmpFileCall,
    TmpFileMock,
)
from pcs_test.tools.misc import get_test_resource as rc


def _node_fixture(name, node_id):
    return f'<node id="{node_id}" uname="{name}"/>'


def _node_list_fixture(nodes):
    return "\n".join(
        _node_fixture(node_name, node_id)
        for node_id, node_name in enumerate(nodes)
    )


def _nodes_section_fixture(content):
    return f"""
    <nodes>
    {content}
    </nodes>
    """


def _rsc_primitive_fixture(res_id):
    return f'<primitive id="{res_id}"/>'


def _rsc_clone_fixture(clone_id, primitive=None, is_promotable=False):
    if not primitive:
        primitive = _rsc_primitive_fixture(f"{clone_id}-primitive")
    meta_attrs = ""
    if is_promotable:
        meta_attrs = '<nvpair name="promotable" value="true" />'
    return f"""
        <clone id="{clone_id}">
            <meta_attributes id="{clone_id}-meta_attributes">
                {meta_attrs}
            </meta_attributes>
            {primitive}
        </clone>
    """


_resource_primitive = _rsc_primitive_fixture("A")

_resource_promotable_clone = _rsc_clone_fixture(
    "clone-A", primitive=_resource_primitive, is_promotable=True
)


def _resources_tag(content):
    return f"""
    <resources>
{content}
    </resources>
"""


def _state_resource_fixture(resource_id, role, node=None):
    node_list = []
    if node:
        node_list = [(node, 1)]

    return _resources_tag(
        """
        <resource id="{resource_id}" role="{role}" nodes_running_on="{nodes_count}">
            {nodes}
        </resource>
        """.format(
            resource_id=resource_id,
            role=role,
            nodes_count=len(node_list),
            nodes="\n".join(
                f"""<node name="{node_name}" id="{node_id}" cached="false" />"""
                for node_name, node_id in node_list
            ),
        )
    )


def _simulation_transition_fixture(synapses=""):
    return f"""
<transition_graph cluster-delay="60s" stonith-timeout="60s" failed-stop-offset="INFINITY" failed-start-offset="INFINITY" batch-limit="0" transition_id="0">
  {synapses}
</transition_graph>
"""


def _simulation_synapses_fixture(resource_id, start_id=0):
    return f"""
  <synapse id="{start_id}">
    <action_set>
      <rsc_op id="{start_id * 10}" operation="stop" operation_key="{resource_id}_stop_0" on_node="node1" on_node_uuid="1">
        <primitive id="{resource_id}" class="ocf" provider="heartbeat" type="Dummy"/>
        <attributes CRM_meta_name="stop" CRM_meta_timeout="20000" crm_feature_set="3.0.9"/>
      </rsc_op>
    </action_set>
    <inputs/>
  </synapse>
  <synapse id="{start_id + 1}">
    <action_set>
      <rsc_op id="{start_id * 10 + 1}" operation="start" operation_key="{resource_id}_start_0" on_node="node2" on_node_uuid="2">
        <primitive id="{resource_id}" class="ocf" provider="heartbeat" type="Dummy"/>
        <attributes CRM_meta_name="start" CRM_meta_timeout="20000" crm_feature_set="3.0.9"/>
      </rsc_op>
    </action_set>
    <inputs>
      <trigger>
        <rsc_op id="{start_id * 10}" operation="stop" operation_key="{resource_id}_stop_0" on_node="node1" on_node_uuid="1"/>
      </trigger>
    </inputs>
  </synapse>
"""


class MoveAutocleanCommonSetup(TestCase):
    def setUp(self):
        self.tmp_file_mock_obj = TmpFileMock(
            file_content_checker=assert_xml_equal,
        )
        self.addCleanup(self.tmp_file_mock_obj.assert_all_done)
        tmp_file_patcher = mock.patch("pcs.lib.tools.get_tmp_file")
        self.addCleanup(tmp_file_patcher.stop)
        tmp_file_mock = tmp_file_patcher.start()
        tmp_file_mock.side_effect = (
            self.tmp_file_mock_obj.get_mock_side_effect()
        )
        self.env_assist, self.config = get_env_tools(self)


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_api_rng/api-result.rng"),
)
class MoveAutocleanSuccess(MoveAutocleanCommonSetup):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        super().setUp()

        self.orig_node = "node1"
        self.new_node = "node2"
        config_load_cib_name = "load_cib"
        self.config.runner.cib.load(
            name=config_load_cib_name,
            resources=_resources_tag(
                _resource_primitive + _resource_promotable_clone
            ),
            nodes=_nodes_section_fixture(
                _node_list_fixture([self.orig_node, self.new_node])
            ),
        )
        self.orig_cib = etree_to_str(
            xml_fromstring(self.config.calls.get(config_load_cib_name).stdout)
        )
        self.cib_with_constraint = '<updated_cib with_constraint="True"/>'
        self.cib_without_constraint = (
            '<cib with_constraint="False" updated="True"/>'
        )
        self.cib_simulate_constraint = (
            '<cib simulate="True" with_constraint="True"/>'
        )
        self.cib_rsc_move_tmp_file_name = "file_to_call_crm_resource_move"
        self.cib_diff_add_constraint_orig_tmp_file_name = (
            "cib_diff_add_constraint_orig"
        )
        self.cib_diff_add_constraint_updated_tmp_file_name = (
            "cib_diff_add_constraint_updated"
        )
        self.cib_constraint_removed_by_unmove_file_name = (
            "cib_constraint_removed_by_unmove"
        )
        self.cib_diff_remove_constraint_orig_tmp_file_name = (
            "cib_diff_remove_constraint_orig"
        )
        self.cib_diff_remove_constraint_updated_tmp_file_name = (
            "cib_diff_remove_constraint_updated"
        )
        self.simulated_cib_add_constraint_tmp_file_name = (
            "pcmk_simulate_move_new_cib"
        )
        self.simulated_transitions_add_constraint_tmp_file_name = (
            "pcmk_simulate_move_transitions"
        )
        self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name = "simulated_cib_remove_constraint"
        self.cib_simulated_apply_diff_removing_constraint = (
            '<cib simulate="True" with_constraint="False" diff_applied="True"/>'
        )
        self.pcmk_simulate_remove_constraint_orig_cib_tmp_file_name = (
            "pcmk_simulate_input_unmove_cib"
        )
        self.simulated_cib_remove_constraint_tmp_file_name = (
            "pcmk_simulate_unmove_new_cib"
        )
        self.simulated_transitions_remove_constraint_tmp_file_name = (
            "pcmk_simulate_unmove_transitions"
        )
        self.cib_apply_diff_remove_constraint_after_push_tmp_file_name = (
            "apply_cib_diff_remove_constraint"
        )
        self.cib_remove_constraint_diff_applied = (
            '<cib with_constraint="False" diff_applied="True"/>'
        )
        self.pcmk_simulate_remove_constraint_after_push_orig_cib_tmp_file_name = "pcmk_simulate_after_push_input_unmove_cib_after"
        self.simulated_cib_remove_constraint_after_push_tmp_file_name = (
            "pcmk_simulate_after_push_unmove_new_cib"
        )
        self.simulated_transitions_remove_constraint_after_push_tmp_file_name = "pcmk_simulate_after_push_unmove_transitions"
        self.cib_diff_add_constraint = "diff_add_constraint"
        self.cib_diff_remove_constraint = "diff_remove_constraint"

    def get_tmp_files(self, transitions):
        return [
            TmpFileCall(
                self.cib_rsc_move_tmp_file_name,
                orig_content=self.orig_cib,
                new_content=self.cib_with_constraint,
            ),
            TmpFileCall(
                self.cib_diff_add_constraint_orig_tmp_file_name,
                orig_content=self.orig_cib,
            ),
            TmpFileCall(
                self.cib_diff_add_constraint_updated_tmp_file_name,
                orig_content=self.cib_with_constraint,
            ),
            TmpFileCall(
                self.cib_constraint_removed_by_unmove_file_name,
                orig_content=self.cib_with_constraint,
                new_content=self.cib_without_constraint,
            ),
            TmpFileCall(
                self.cib_diff_remove_constraint_orig_tmp_file_name,
                orig_content=self.cib_with_constraint,
            ),
            TmpFileCall(
                self.cib_diff_remove_constraint_updated_tmp_file_name,
                orig_content=self.cib_without_constraint,
            ),
            TmpFileCall(
                self.simulated_cib_add_constraint_tmp_file_name,
                new_content=self.cib_simulate_constraint,
            ),
            TmpFileCall(
                self.simulated_transitions_add_constraint_tmp_file_name,
                new_content=transitions,
            ),
            TmpFileCall(
                self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name,
                orig_content=self.cib_simulate_constraint,
                new_content=self.cib_simulated_apply_diff_removing_constraint,
            ),
            TmpFileCall(
                self.pcmk_simulate_remove_constraint_orig_cib_tmp_file_name,
                orig_content=self.cib_simulate_constraint,
            ),
            TmpFileCall(
                self.simulated_cib_remove_constraint_tmp_file_name,
                new_content='<cib simulate="True" with_constraint="False"/>',
            ),
            TmpFileCall(
                self.simulated_transitions_remove_constraint_tmp_file_name,
                new_content=transitions,
            ),
            TmpFileCall(
                self.cib_apply_diff_remove_constraint_after_push_tmp_file_name,
                orig_content=self.cib_with_constraint,
                new_content=self.cib_remove_constraint_diff_applied,
            ),
            TmpFileCall(
                self.pcmk_simulate_remove_constraint_after_push_orig_cib_tmp_file_name,
                orig_content=self.cib_with_constraint,
            ),
            TmpFileCall(
                self.simulated_cib_remove_constraint_after_push_tmp_file_name,
                new_content='<cib simulate="True" after_push="True" with_constraint="False"/>',
            ),
            TmpFileCall(
                self.simulated_transitions_remove_constraint_after_push_tmp_file_name,
                new_content=transitions,
            ),
        ]

    def set_up_testing_env(
        self,
        resource_id,
        status_before,
        status_after,
        with_node=False,
        is_promotable=False,
    ):
        self.config.runner.pcmk.load_state(
            resources=status_before,
            name="runner.pcmk.load_state.start",
        )
        self.config.runner.pcmk.resource_move(
            resource=resource_id,
            master=is_promotable,
            node=self.new_node if with_node else None,
            env=dict(CIB_file=self.cib_rsc_move_tmp_file_name),
        )
        self.config.runner.cib.diff(
            self.cib_diff_add_constraint_orig_tmp_file_name,
            self.cib_diff_add_constraint_updated_tmp_file_name,
            stdout=self.cib_diff_add_constraint,
            name="runner.cib.diff.add_constraint",
        )
        self.config.runner.pcmk.resource_clear(
            resource=resource_id,
            master=is_promotable,
            node=self.new_node if with_node else None,
            env=dict(CIB_file=self.cib_constraint_removed_by_unmove_file_name),
        )
        self.config.runner.cib.diff(
            self.cib_diff_remove_constraint_orig_tmp_file_name,
            self.cib_diff_remove_constraint_updated_tmp_file_name,
            stdout="diff_remove_constraint",
            name="runner.cib.diff.remove_constraint",
        )
        self.config.runner.pcmk.simulate_cib(
            self.simulated_cib_add_constraint_tmp_file_name,
            self.simulated_transitions_add_constraint_tmp_file_name,
            cib_xml=self.cib_with_constraint,
            name="pcmk.simulate.rsc.move",
        )
        self.config.runner.pcmk.load_state(
            resources=status_after,
            name="runner.pcmk.load_state.mid_simulation",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name
            ),
        )
        self.config.runner.cib.push_diff(
            cib_diff=self.cib_diff_remove_constraint,
            name="pcmk.push_cib_diff.simulation.remove_constraint",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name
            ),
        )
        self.config.runner.pcmk.simulate_cib(
            self.simulated_cib_remove_constraint_tmp_file_name,
            self.simulated_transitions_remove_constraint_tmp_file_name,
            cib_xml=self.cib_simulated_apply_diff_removing_constraint,
            env=dict(
                CIB_file=self.pcmk_simulate_remove_constraint_orig_cib_tmp_file_name
            ),
            name="pcmk.simulate.rsc.unmove.on_simulated",
        )
        self.config.runner.cib.push_diff(
            cib_diff=self.cib_diff_add_constraint,
            name="pcmk.push_cib_diff.live_cluster.add_constraint",
        )
        self.config.runner.pcmk.wait(
            timeout=0, name="runner.pcmk.wait.after_move"
        )
        self.config.runner.cib.load_content(
            self.cib_with_constraint,
            name="load_cib_after_move",
        )
        self.config.runner.pcmk.load_state(
            resources=status_after,
            name="runner.pcmk.load_state.after_push",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_after_push_tmp_file_name
            ),
        )
        self.config.runner.cib.push_diff(
            cib_diff=self.cib_diff_remove_constraint,
            name="pcmk.push_cib_diff.simulation.remove_constraint_after_move",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_after_push_tmp_file_name
            ),
        )
        self.config.runner.pcmk.simulate_cib(
            self.simulated_cib_remove_constraint_after_push_tmp_file_name,
            self.simulated_transitions_remove_constraint_after_push_tmp_file_name,
            cib_xml=self.cib_remove_constraint_diff_applied,
            env=dict(
                CIB_file=self.pcmk_simulate_remove_constraint_after_push_orig_cib_tmp_file_name
            ),
            name="pcmk.simulate.rsc.unmove.after_push",
        )
        self.config.runner.cib.push_diff(
            cib_diff=self.cib_diff_remove_constraint,
            name="pcmk.push_cib_diff.remove_constraint_after_move",
        )
        self.config.runner.pcmk.wait(
            timeout=0, name="runner.pcmk.wait.after_cleanup"
        )
        self.config.runner.pcmk.load_state(
            resources=status_after,
            name="runner.pcmk.load_state.final",
        )

    def get_reports(self, resource_id):
        return [
            fixture.info(
                reports.codes.RESOURCE_MOVE_CONSTRAINT_CREATED,
                resource_id=resource_id,
            ),
            fixture.info(
                reports.codes.WAIT_FOR_IDLE_STARTED,
                timeout=0,
            ),
            fixture.info(
                reports.codes.RESOURCE_MOVE_CONSTRAINT_REMOVED,
                resource_id=resource_id,
            ),
            fixture.info(
                reports.codes.WAIT_FOR_IDLE_STARTED,
                timeout=0,
            ),
            fixture.info(
                reports.codes.RESOURCE_RUNNING_ON_NODES,
                resource_id=resource_id,
                roles_with_nodes=dict(Started=[self.new_node]),
            ),
        ]

    def test_with_node(self):
        resource_id = "A"
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(f"other_than_{resource_id}")
                )
            )
        )
        self.set_up_testing_env(
            resource_id,
            status_before=_state_resource_fixture(
                resource_id, "Started", self.orig_node
            ),
            status_after=_state_resource_fixture(
                resource_id, "Started", self.new_node
            ),
            with_node=True,
        )
        move_autoclean(
            self.env_assist.get_env(), resource_id, node=self.new_node
        )
        self.env_assist.assert_reports(self.get_reports(resource_id))

    def test_no_strict(self):
        resource_id = "A"
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(f"other_than_{resource_id}")
                )
            )
        )
        self.set_up_testing_env(
            resource_id,
            status_before=_state_resource_fixture(
                resource_id, "Started", self.orig_node
            ),
            status_after=_state_resource_fixture(
                resource_id, "Started", self.new_node
            ),
        )
        move_autoclean(self.env_assist.get_env(), resource_id)
        self.env_assist.assert_reports(self.get_reports(resource_id))

    def test_strict(self):
        resource_id = "A"
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files(_simulation_transition_fixture())
        )
        self.set_up_testing_env(
            resource_id,
            status_before=_state_resource_fixture(
                resource_id, "Started", self.orig_node
            ),
            status_after=_state_resource_fixture(
                resource_id, "Started", self.new_node
            ),
        )
        move_autoclean(self.env_assist.get_env(), resource_id, strict=True)
        self.env_assist.assert_reports(self.get_reports(resource_id))

    def test_master(self):
        resource_id = "clone-A"
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files(_simulation_transition_fixture())
        )
        self.set_up_testing_env(
            resource_id,
            status_before=_state_resource_fixture(
                resource_id, "Promoted", self.orig_node
            ),
            status_after=_state_resource_fixture(
                resource_id, "Promoted", self.new_node
            ),
            is_promotable=True,
        )
        move_autoclean(self.env_assist.get_env(), resource_id, master=True)
        self.env_assist.assert_reports(
            self.get_reports(resource_id)[:-1]
            + [
                fixture.info(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    resource_id=resource_id,
                    roles_with_nodes=dict(Promoted=[self.new_node]),
                ),
            ]
        )

    def test_master_with_node(self):
        resource_id = "clone-A"
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(f"other_than_{resource_id}")
                )
            )
        )
        self.set_up_testing_env(
            resource_id,
            status_before=_state_resource_fixture(
                resource_id, "Promoted", self.orig_node
            ),
            status_after=_state_resource_fixture(
                resource_id, "Promoted", self.new_node
            ),
            with_node=True,
            is_promotable=True,
        )
        move_autoclean(
            self.env_assist.get_env(),
            resource_id,
            master=True,
            node=self.new_node,
        )
        self.env_assist.assert_reports(
            self.get_reports(resource_id)[:-1]
            + [
                fixture.info(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    resource_id=resource_id,
                    roles_with_nodes=dict(Promoted=[self.new_node]),
                ),
            ]
        )

    def test_master_with_node_strict(self):
        resource_id = "clone-A"
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files(_simulation_transition_fixture())
        )
        self.set_up_testing_env(
            resource_id,
            status_before=_state_resource_fixture(
                resource_id, "Promoted", self.orig_node
            ),
            status_after=_state_resource_fixture(
                resource_id, "Promoted", self.new_node
            ),
            with_node=True,
            is_promotable=True,
        )
        move_autoclean(
            self.env_assist.get_env(),
            resource_id,
            master=True,
            node=self.new_node,
            strict=True,
        )
        self.env_assist.assert_reports(
            self.get_reports(resource_id)[:-1]
            + [
                fixture.info(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    resource_id=resource_id,
                    roles_with_nodes=dict(Promoted=[self.new_node]),
                ),
            ]
        )


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_api_rng/api-result.rng"),
)
class MoveAutocleanValidations(MoveAutocleanCommonSetup):
    def test_cib_not_live(self):
        self.config.env.set_cib_data("<cib />")
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), "resource_id"),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.CIB],
                )
            ],
            expected_in_processor=False,
        )

    def test_resource_not_found(self):
        resource_id = "resource_id"
        self.config.runner.cib.load()
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), resource_id),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id=resource_id,
                    expected_types=[
                        "bundle",
                        "clone",
                        "group",
                        "master",
                        "primitive",
                    ],
                    context_type="resources",
                    context_id="",
                )
            ]
        )

    def test_resource_wrong_type_bundle_inner(self):
        bundle_id = "bundle_rsc"
        resource_id = "bundle_rsc-primitive"
        self.config.runner.cib.load(
            resources=_resources_tag(
                '<bundle id="{bundle_id}">{primitive}</bundle>'.format(
                    bundle_id=bundle_id,
                    primitive=_rsc_primitive_fixture(resource_id),
                )
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), resource_id),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_BUNDLE_INNER,
                    resource_id=resource_id,
                    bundle_id=bundle_id,
                )
            ]
        )

    def test_resource_wrong_type_clone_inner(self):
        clone_id = "clone_rsc"
        resource_id = "clone_rsc-primitive"
        self.config.runner.cib.load(
            resources=_resources_tag(_rsc_clone_fixture(clone_id))
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), resource_id),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_CLONE_INNER,
                    resource_id=resource_id,
                    clone_id=clone_id,
                )
            ]
        )

    def test_resource_wrong_type_inner_promotable_clone(self):
        resource_id = "A"
        promotable_id = f"{resource_id}-clone"
        self.config.runner.cib.load(
            resources=_resources_tag(
                _rsc_clone_fixture(
                    promotable_id,
                    primitive=_rsc_primitive_fixture(resource_id),
                    is_promotable=True,
                )
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), resource_id),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_PROMOTABLE_INNER,
                    resource_id=resource_id,
                    promotable_id=promotable_id,
                )
            ]
        )

    def test_resource_wrong_type_promoted_on_non_promotable_resource(self):
        resource_id = "A"
        promotable_id = f"{resource_id}-clone"
        self.config.runner.cib.load(
            resources=_resources_tag(
                _rsc_clone_fixture(
                    promotable_id,
                    primitive=_rsc_primitive_fixture(resource_id),
                    is_promotable=True,
                )
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(), resource_id, master=True
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE,
                    resource_id=resource_id,
                    promotable_id=promotable_id,
                )
            ]
        )

    def test_stopped_resource_node_not_specified(self):
        resource_id = "A"
        self.config.runner.cib.load(
            resources=_resources_tag(_rsc_primitive_fixture(resource_id)),
        )
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(resource_id, "Stopped"),
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), resource_id),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_NOT_RUNNING,
                    resource_id=resource_id,
                )
            ],
            expected_in_processor=False,
        )

    def test_stopped_resource_node_specified(self):
        resource_id = "A"
        self.config.runner.cib.load(
            resources=_resources_tag(_rsc_primitive_fixture(resource_id)),
        )
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(resource_id, "Stopped"),
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), resource_id),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_NOT_RUNNING,
                    resource_id=resource_id,
                )
            ],
            expected_in_processor=False,
        )

    def test_node_not_found(self):
        resource_id = "A"
        node = "non_existing_node"
        self.config.runner.cib.load(
            resources=_resources_tag(_rsc_primitive_fixture(resource_id)),
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(), resource_id, node
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_NOT_FOUND,
                    node=node,
                    searched_types=[],
                )
            ],
        )

    def test_constraint_already_exist(self):
        resource_id = "A"
        config_load_cib_name = "load_cib"
        node = "node1"
        cib_with_constraint = '<cib with_constraint="True"/>'
        cib_without_constraint = '<cib with_constraint="False" updated="True"/>'
        cib_rsc_move_tmp_file_name = "cib_rsc_move_tmp_file"
        cib_diff_add_constraint_orig_tmp_file_name = (
            "cib_diff_add_constraint_orig"
        )
        cib_diff_add_constraint_updated_tmp_file_name = (
            "cib_diff_add_constraint_updated"
        )
        cib_diff_remove_constraint_orig_tmp_file_name = (
            "cib_diff_remove_constraint_orig"
        )
        cib_diff_remove_constraint_updated_tmp_file_name = (
            "cib_diff_remove_constraint_updated"
        )
        cib_constraint_removed_by_unmove_file_name = (
            "cib_constraint_removed_by_unmove"
        )
        self.config.runner.cib.load(
            resources=_resources_tag(_rsc_primitive_fixture(resource_id)),
            constraints=f"""
              <constraints>
                  <rsc_location id="prefer-{resource_id}" rsc="{resource_id}" role="Started" node="{node}" score="INFINITY"/>
              </constraints>
            """,
            nodes=_nodes_section_fixture(_node_list_fixture([node])),
            name=config_load_cib_name,
        )
        orig_cib = etree_to_str(
            xml_fromstring(self.config.calls.get(config_load_cib_name).stdout)
        )
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall(
                    cib_rsc_move_tmp_file_name,
                    orig_content=orig_cib,
                    new_content=cib_with_constraint,
                ),
                TmpFileCall(
                    cib_diff_add_constraint_orig_tmp_file_name,
                    orig_content=orig_cib,
                ),
                TmpFileCall(
                    cib_diff_add_constraint_updated_tmp_file_name,
                    orig_content=cib_with_constraint,
                ),
                TmpFileCall(
                    cib_constraint_removed_by_unmove_file_name,
                    orig_content=cib_with_constraint,
                    new_content=cib_without_constraint,
                ),
                TmpFileCall(
                    cib_diff_remove_constraint_orig_tmp_file_name,
                    orig_content=cib_with_constraint,
                ),
                TmpFileCall(
                    cib_diff_remove_constraint_updated_tmp_file_name,
                    orig_content=cib_without_constraint,
                ),
            ]
        )
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(resource_id, "Started", node),
        )
        self.config.runner.pcmk.resource_move(
            resource=resource_id,
            node=node,
            env=dict(CIB_file=cib_rsc_move_tmp_file_name),
        )
        self.config.runner.cib.diff(
            cib_diff_add_constraint_orig_tmp_file_name,
            cib_diff_add_constraint_updated_tmp_file_name,
            stdout="",
            name="runner.cib.diff.add_constraint",
        )
        self.config.runner.pcmk.resource_clear(
            resource=resource_id,
            node=node,
            env=dict(CIB_file=cib_constraint_removed_by_unmove_file_name),
        )
        self.config.runner.cib.diff(
            cib_diff_remove_constraint_orig_tmp_file_name,
            cib_diff_remove_constraint_updated_tmp_file_name,
            stdout="",
            name="runner.cib.diff.remove_constraint",
        )
        move_autoclean(self.env_assist.get_env(), resource_id, node=node)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.NO_ACTION_NECESSARY,
                ),
            ]
        )

    def test_unmanaged_resource(self):
        resource_id = "A"
        self.config.runner.cib.load(
            resources=_resources_tag(_rsc_primitive_fixture(resource_id))
        )
        self.config.runner.pcmk.load_state(
            resources=_resources_tag(
                '<resource id="{resource_id}" managed="{managed}" />'.format(
                    resource_id=resource_id, managed="false"
                )
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), resource_id),
            [
                fixture.error(
                    reports.codes.RESOURCE_IS_UNMANAGED,
                    resource_id=resource_id,
                )
            ],
            expected_in_processor=False,
        )


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_api_rng/api-result.rng"),
)
class MoveAutocleanFailures(MoveAutocleanCommonSetup):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        super().setUp()

        self.resource_id = "A"
        self.affected_resource = f"other_than_{self.resource_id}"
        self.config_load_cib_name = "load_cib"
        self.cib_diff_add_constraint = "diff_add_constraint"
        self.cib_diff_remove_constraint = "diff_remove_constraint"
        self.cib_with_constraint = '<cib with_constraint="True"/>'
        self.cib_without_constraint = (
            '<cib with_constraint="False" updated="True"/>'
        )
        self.cib_rsc_move_tmp_file_name = "cib_rsc_move_tmp_file"
        self.cib_diff_add_constraint_orig_tmp_file_name = (
            "cib_diff_add_constraint_orig"
        )
        self.cib_diff_add_constraint_updated_tmp_file_name = (
            "cib_diff_add_constraint_updated"
        )
        self.cib_constraint_removed_by_unmove_file_name = (
            "cib_constraint_removed_by_unmove"
        )
        self.cib_diff_remove_constraint_orig_tmp_file_name = (
            "cib_diff_remove_constraint_orig"
        )
        self.cib_diff_remove_constraint_updated_tmp_file_name = (
            "cib_diff_remove_constraint_updated"
        )
        self.simulated_cib_add_constraint_tmp_file_name = (
            "pcmk_simulate_move_new_cib"
        )
        self.simulated_transitions_add_constraint_tmp_file_name = (
            "pcmk_simulate_move_transitions"
        )
        self.cib_simulate_constraint = (
            '<cib simulate="True" with_constraint="True"/>'
        )
        self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name = "simulated_cib_remove_constraint"
        self.cib_simulated_apply_diff_removing_constraint = (
            '<cib simulate="True" with_constraint="False" diff_applied="True"/>'
        )
        self.pcmk_simulate_remove_constraint_orig_cib_tmp_file_name = (
            "pcmk_simulate_input_unmove_cib"
        )
        self.simulated_cib_remove_constraint_tmp_file_name = (
            "pcmk_simulate_unmove_new_cib"
        )
        self.simulated_transitions_remove_constraint_tmp_file_name = (
            "pcmk_simulate_unmove_transitions"
        )
        self.cib_apply_diff_remove_constraint_after_push_tmp_file_name = (
            "apply_cib_diff_remove_constraint"
        )
        self.cib_remove_constraint_diff_applied = (
            '<cib with_constraint="False" diff_applied="True"/>'
        )
        self.pcmk_simulate_remove_constraint_after_push_orig_cib_tmp_file_name = "pcmk_simulate_after_push_input_unmove_cib_after"
        self.simulated_cib_remove_constraint_after_push_tmp_file_name = (
            "pcmk_simulate_after_push_unmove_new_cib"
        )
        self.simulated_transitions_remove_constraint_after_push_tmp_file_name = "pcmk_simulate_after_push_unmove_transitions"

        self.config.runner.cib.load(
            resources=_resources_tag(_rsc_primitive_fixture(self.resource_id)),
            nodes=_nodes_section_fixture(
                _node_list_fixture(["node1", "node2"])
            ),
            name=self.config_load_cib_name,
        )
        self.orig_cib = etree_to_str(
            xml_fromstring(
                self.config.calls.get(self.config_load_cib_name).stdout
            )
        )

    def get_tmp_files_mocks(
        self,
        simulation_transitions_move,
        simulation_transitions_unmove=None,
        simulation_transitions_unmove_after_push=None,
    ):
        file_list = [
            TmpFileCall(
                self.cib_rsc_move_tmp_file_name,
                orig_content=self.orig_cib,
                new_content=self.cib_with_constraint,
            ),
            TmpFileCall(
                self.cib_diff_add_constraint_orig_tmp_file_name,
                orig_content=self.orig_cib,
            ),
            TmpFileCall(
                self.cib_diff_add_constraint_updated_tmp_file_name,
                orig_content=self.cib_with_constraint,
            ),
            TmpFileCall(
                self.cib_constraint_removed_by_unmove_file_name,
                orig_content=self.cib_with_constraint,
                new_content=self.cib_without_constraint,
            ),
            TmpFileCall(
                self.cib_diff_remove_constraint_orig_tmp_file_name,
                orig_content=self.cib_with_constraint,
            ),
            TmpFileCall(
                self.cib_diff_remove_constraint_updated_tmp_file_name,
                orig_content=self.cib_without_constraint,
            ),
            TmpFileCall(
                self.simulated_cib_add_constraint_tmp_file_name,
                new_content=self.cib_simulate_constraint,
            ),
            TmpFileCall(
                self.simulated_transitions_add_constraint_tmp_file_name,
                new_content=simulation_transitions_move,
            ),
        ]

        if not simulation_transitions_unmove:
            return file_list

        file_list.extend(
            [
                TmpFileCall(
                    self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name,
                    orig_content=self.cib_simulate_constraint,
                    new_content=self.cib_simulated_apply_diff_removing_constraint,
                ),
                TmpFileCall(
                    self.pcmk_simulate_remove_constraint_orig_cib_tmp_file_name,
                    orig_content=self.cib_simulate_constraint,
                ),
                TmpFileCall(
                    self.simulated_cib_remove_constraint_tmp_file_name,
                    new_content='<cib simulate="True" with_constraint="False"/>',
                ),
                TmpFileCall(
                    self.simulated_transitions_remove_constraint_tmp_file_name,
                    new_content=simulation_transitions_unmove,
                ),
            ]
        )

        if not simulation_transitions_unmove_after_push:
            return file_list

        file_list.extend(
            [
                TmpFileCall(
                    self.cib_apply_diff_remove_constraint_after_push_tmp_file_name,
                    orig_content=self.cib_with_constraint,
                    new_content=self.cib_remove_constraint_diff_applied,
                ),
                TmpFileCall(
                    self.pcmk_simulate_remove_constraint_after_push_orig_cib_tmp_file_name,
                    orig_content=self.cib_with_constraint,
                ),
                TmpFileCall(
                    self.simulated_cib_remove_constraint_after_push_tmp_file_name,
                    new_content='<cib simulate="True" after_push="True" with_constraint="False"/>',
                ),
                TmpFileCall(
                    self.simulated_transitions_remove_constraint_after_push_tmp_file_name,
                    new_content=simulation_transitions_unmove_after_push,
                ),
            ]
        )

        return file_list

    def set_up_testing_env(self, node=None, stage=9):
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(
                self.resource_id, "Started", "node1"
            ),
            name="runner.pcmk.load_state.before",
        )
        self.config.runner.pcmk.resource_move(
            resource=self.resource_id,
            node=node,
            env=dict(CIB_file=self.cib_rsc_move_tmp_file_name),
        )
        self.config.runner.cib.diff(
            self.cib_diff_add_constraint_orig_tmp_file_name,
            self.cib_diff_add_constraint_updated_tmp_file_name,
            stdout=self.cib_diff_add_constraint,
            name="runner.cib.diff.add_constraint",
        )
        self.config.runner.pcmk.resource_clear(
            resource=self.resource_id,
            node=node,
            env=dict(CIB_file=self.cib_constraint_removed_by_unmove_file_name),
        )
        self.config.runner.cib.diff(
            self.cib_diff_remove_constraint_orig_tmp_file_name,
            self.cib_diff_remove_constraint_updated_tmp_file_name,
            stdout=self.cib_diff_remove_constraint,
            name="runner.cib.diff.remove_constraint",
        )
        self.config.runner.pcmk.simulate_cib(
            self.simulated_cib_add_constraint_tmp_file_name,
            self.simulated_transitions_add_constraint_tmp_file_name,
            cib_xml=self.cib_with_constraint,
            name="pcmk.simulate.rsc.move",
        )
        if stage <= 1:
            return
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(
                self.resource_id, "Started", node if node else "node2"
            ),
            name="runner.pcmk.load_state.mid_simulation",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name
            ),
        )
        self.config.runner.cib.push_diff(
            cib_diff=self.cib_diff_remove_constraint,
            name="pcmk.push_cib_diff.simulation.remove_constraint",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name
            ),
        )
        self.config.runner.pcmk.simulate_cib(
            self.simulated_cib_remove_constraint_tmp_file_name,
            self.simulated_transitions_remove_constraint_tmp_file_name,
            cib_xml=self.cib_simulated_apply_diff_removing_constraint,
            env=dict(
                CIB_file=self.pcmk_simulate_remove_constraint_orig_cib_tmp_file_name
            ),
            name="pcmk.simulate.rsc.unmove.on_simulated",
        )
        if stage <= 2:
            return
        self.config.runner.cib.push_diff(
            cib_diff=self.cib_diff_add_constraint,
            name="pcmk.push_cib_diff.live_cluster.add_constraint",
        )
        self.config.runner.pcmk.wait(
            timeout=0, name="runner.pcmk.wait.after_move"
        )
        self.config.runner.cib.load_content(
            self.cib_with_constraint,
            name="load_cib_after_move",
        )
        if stage <= 3:
            return
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(
                self.resource_id, "Started", node if node else "node2"
            ),
            name="runner.pcmk.load_state.after_push",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_after_push_tmp_file_name
            ),
        )
        self.config.runner.cib.push_diff(
            cib_diff=self.cib_diff_remove_constraint,
            name="pcmk.push_cib_diff.simulation.remove_constraint_after_move",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_after_push_tmp_file_name
            ),
        )
        self.config.runner.pcmk.simulate_cib(
            self.simulated_cib_remove_constraint_after_push_tmp_file_name,
            self.simulated_transitions_remove_constraint_after_push_tmp_file_name,
            cib_xml=self.cib_remove_constraint_diff_applied,
            env=dict(
                CIB_file=self.pcmk_simulate_remove_constraint_after_push_orig_cib_tmp_file_name
            ),
            name="pcmk.simulate.rsc.unmove.after_push",
        )
        if stage <= 4:
            return
        self.config.runner.cib.push_diff(
            cib_diff=self.cib_diff_remove_constraint,
            name="pcmk.push_cib_diff.remove_constraint_after_move",
        )
        self.config.runner.pcmk.wait(
            timeout=0, name="runner.pcmk.wait.after_cleanup"
        )

    def get_reports(self, stage=None):
        return [
            fixture.info(
                reports.codes.RESOURCE_MOVE_CONSTRAINT_CREATED,
                resource_id=self.resource_id,
            ),
            fixture.info(
                reports.codes.WAIT_FOR_IDLE_STARTED,
                timeout=0,
            ),
            fixture.info(
                reports.codes.RESOURCE_MOVE_CONSTRAINT_REMOVED,
                resource_id=self.resource_id,
            ),
            fixture.info(
                reports.codes.WAIT_FOR_IDLE_STARTED,
                timeout=0,
            ),
        ][: {None: None, 4: -2, 3: 2, 2: 0, 1: 0}[stage]]

    def test_move_affects_other_resources_strict(self):
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(
                        self.affected_resource, start_id=1
                    )
                    + _simulation_synapses_fixture(self.resource_id)
                ),
            )
        )
        self.set_up_testing_env(stage=1)
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(), self.resource_id, strict=True
            ),
            [
                fixture.error(
                    reports.codes.RESOURCE_MOVE_AFFECTS_OTRHER_RESOURCES,
                    resource_id=self.resource_id,
                    affected_resources=[self.affected_resource],
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.get_reports(stage=1))

    def test_unmove_affects_the_resource(self):
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(
                        self.affected_resource, start_id=1
                    )
                    + _simulation_synapses_fixture(self.resource_id)
                ),
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.resource_id)
                ),
            )
        )
        self.set_up_testing_env(stage=2)
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), self.resource_id),
            [
                fixture.error(
                    reports.codes.RESOURCE_MOVE_AUTOCLEAN_SIMULATION_FAILURE,
                    resource_id=self.resource_id,
                    others_affected=False,
                    node=None,
                    move_constraint_left_in_cib=False,
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.get_reports(stage=2))

    def test_unmove_affects_other_resources_strict(self):
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.resource_id)
                ),
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(
                        self.affected_resource, start_id=1
                    )
                ),
            )
        )
        self.set_up_testing_env(stage=2)
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(),
                self.resource_id,
                strict=True,
            ),
            [
                fixture.error(
                    reports.codes.RESOURCE_MOVE_AUTOCLEAN_SIMULATION_FAILURE,
                    resource_id=self.resource_id,
                    others_affected=True,
                    node=None,
                    move_constraint_left_in_cib=False,
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.get_reports(stage=2))

    def test_unmove_after_push_affects_the_resource(self):
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(
                        self.affected_resource, start_id=1
                    )
                    + _simulation_synapses_fixture(self.resource_id)
                ),
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.affected_resource)
                ),
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.resource_id)
                ),
            )
        )
        setup_stage = 4
        self.set_up_testing_env(stage=setup_stage)
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(self.env_assist.get_env(), self.resource_id),
            [
                fixture.error(
                    reports.codes.RESOURCE_MOVE_AUTOCLEAN_SIMULATION_FAILURE,
                    resource_id=self.resource_id,
                    others_affected=False,
                    node=None,
                    move_constraint_left_in_cib=True,
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.get_reports(stage=setup_stage))

    def test_unmove_after_push_affects_other_resources_strict(self):
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.resource_id)
                ),
                _simulation_transition_fixture(),
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.affected_resource)
                ),
            )
        )
        setup_stage = 4
        self.set_up_testing_env(stage=setup_stage)
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(),
                self.resource_id,
                strict=True,
            ),
            [
                fixture.error(
                    reports.codes.RESOURCE_MOVE_AUTOCLEAN_SIMULATION_FAILURE,
                    resource_id=self.resource_id,
                    others_affected=True,
                    node=None,
                    move_constraint_left_in_cib=True,
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.get_reports(stage=setup_stage))

    def test_resource_not_running_after_move(self):
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.resource_id)
                ),
                _simulation_transition_fixture(),
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.affected_resource)
                ),
            )
        )
        self.set_up_testing_env()
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(self.resource_id, "Stopped"),
            name="runner.pcmk.load_state.final",
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(),
                self.resource_id,
            ),
        )
        self.env_assist.assert_reports(
            self.get_reports()
            + [
                fixture.error(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id=self.resource_id,
                )
            ]
        )

    def test_simulation_resource_not_moved(self):
        node = "node2"
        different_node = f"different-{node}"
        setup_stage = 1
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.resource_id)
                ),
            )
            + [
                TmpFileCall(
                    self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name,
                    orig_content=self.cib_simulate_constraint,
                ),
            ]
        )
        self.set_up_testing_env(node=node, stage=setup_stage)
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(
                self.resource_id, "Started", different_node
            ),
            name="runner.pcmk.load_state.final",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(),
                self.resource_id,
                node=node,
            ),
            [
                fixture.error(
                    reports.codes.RESOURCE_MOVE_NOT_AFFECTING_RESOURCE,
                    resource_id=self.resource_id,
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            self.get_reports(stage=setup_stage)
            + [
                fixture.debug(
                    reports.codes.TMP_FILE_WRITE,
                    file_path=self.cib_apply_diff_remove_constraint_from_simulated_cib_tmp_file_name,
                    content=self.cib_simulate_constraint,
                ),
            ]
        )

    def test_after_push_resource_not_moved(self):
        node = "node2"
        different_node = f"different-{node}"
        setup_stage = 3
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.resource_id)
                ),
                _simulation_transition_fixture(),
            )
            + [
                TmpFileCall(
                    self.cib_apply_diff_remove_constraint_after_push_tmp_file_name,
                    orig_content=self.cib_with_constraint,
                ),
            ]
        )
        self.set_up_testing_env(node=node, stage=setup_stage)
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(
                self.resource_id, "Started", different_node
            ),
            name="runner.pcmk.load_state.final",
            env=dict(
                CIB_file=self.cib_apply_diff_remove_constraint_after_push_tmp_file_name,
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(),
                self.resource_id,
                node=node,
            ),
            [
                fixture.error(
                    reports.codes.RESOURCE_MOVE_NOT_AFFECTING_RESOURCE,
                    resource_id=self.resource_id,
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            self.get_reports(stage=setup_stage)
            + [
                fixture.debug(
                    reports.codes.TMP_FILE_WRITE,
                    file_path=self.cib_apply_diff_remove_constraint_after_push_tmp_file_name,
                    content=self.cib_with_constraint,
                ),
            ]
        )

    def test_resource_running_on_a_different_node(self):
        node = "node2"
        different_node = f"different-{node}"
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.resource_id)
                ),
                _simulation_transition_fixture(),
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.affected_resource)
                ),
            )
        )
        self.set_up_testing_env(node=node)
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(
                self.resource_id, "Started", different_node
            ),
            name="runner.pcmk.load_state.final",
        )
        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(),
                self.resource_id,
                node=node,
            ),
        )
        self.env_assist.assert_reports(
            self.get_reports()
            + [
                fixture.error(
                    reports.codes.RESOURCE_RUNNING_ON_NODES,
                    resource_id=self.resource_id,
                    roles_with_nodes=dict(Started=[different_node]),
                )
            ]
        )

    def assert_moving_clone_bundle_with_more_instances(
        self, stderr, report_code
    ):
        # This tests that error messages from crm_resources are translated to
        # report messages correctly. For the purpose of the test, no clone or
        # bundle is needed. The only thing that matters is the error message
        # from crm_resource. So we don't bother creating a CIB with a clone or
        # bundle in it.
        self.tmp_file_mock_obj.set_calls(
            self.get_tmp_files_mocks(
                _simulation_transition_fixture(
                    _simulation_synapses_fixture(self.resource_id)
                )
            )[:1]
        )
        self.config.runner.pcmk.load_state(
            resources=_state_resource_fixture(
                self.resource_id, "Started", "node1"
            ),
        )
        self.config.runner.pcmk.resource_move(
            resource=self.resource_id,
            env=dict(CIB_file=self.cib_rsc_move_tmp_file_name),
            returncode=1,
            stderr=stderr,
        )

        self.env_assist.assert_raise_library_error(
            lambda: move_autoclean(
                self.env_assist.get_env(),
                self.resource_id,
            ),
            [
                fixture.error(report_code, resource_id=self.resource_id),
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.get_reports(stage=1))

    def test_moving_clone_bundle_with_more_instances_1(self):
        self.assert_moving_clone_bundle_with_more_instances(
            "Error performing operation: Multiple items match request",
            reports.codes.CANNOT_MOVE_RESOURCE_MULTIPLE_INSTANCES,
        )

    def test_moving_clone_bundle_with_more_instances_2(self):
        self.assert_moving_clone_bundle_with_more_instances(
            "Resource 'A' not moved: active in 2 locations.",
            reports.codes.CANNOT_MOVE_RESOURCE_MULTIPLE_INSTANCES_NO_NODE_SPECIFIED,
        )

from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import resource

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
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


nodes_section = _nodes_section_fixture(
    _node_list_fixture(["node", "node1", "node2"])
)
resources_primitive = """
    <resources>
        <primitive id="A" />
    </resources>
"""
resources_promotable = """
    <resources>
        <clone id="A-clone">
            <primitive id="A" />
            <meta_attributes>
                <nvpair name="promotable" value="true" />
            </meta_attributes>
        </clone>
    </resources>
"""


def _action_kwargs(kwargs):
    defaulted = dict(
        resource="A",
        stdout="pcmk std out",
        stderr="pcmk std err",
        returncode=0,
    )
    defaulted.update(kwargs)
    return defaulted


class MoveBanClearBaseMixin:
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_resource_not_found(self):
        self.config.runner.cib.load(resources=resources_primitive)
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(self.env_assist.get_env(), "B")
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found("B", context_type="resources"),
            ]
        )

    def test_master_of_nonpromotable_resource(self):
        # This is a basic test which checks validation is being done. It
        # utilizes the fact all three commands (move, ban, unmove_unban) share
        # a common situation to check. Detailed validation tests are in
        # pcs_test.tier0.lib.cib.test_resource_common
        self.config.runner.cib.load(resources=resources_primitive)
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(self.env_assist.get_env(), "A", master=True)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    self.report_code_bad_master,
                    resource_id="A",
                    promotable_id=None,
                ),
            ]
        )

    def test_pcmk_error(self):
        self.config.runner.cib.load(resources=resources_primitive)
        self.config_pcmk_action(returncode=1)
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(self.env_assist.get_env(), "A"),
            [
                fixture.error(
                    self.report_code_pcmk_error,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
            ],
            expected_in_processor=False,
        )

    def test_success(self):
        self.config.runner.cib.load(resources=resources_primitive)
        self.config_pcmk_action()
        self.lib_action(self.env_assist.get_env(), "A")
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
            ]
        )


class MoveBanBaseMixin(MoveBanClearBaseMixin):
    def test_resource_stopped(self):
        stderr = dedent(
            """\
            Resource 'A' not moved: active in 0 locations.
            To prevent 'A' from running on a specific location, specify a node.
            Error performing operation: Invalid argument
            """
        )
        self.config.runner.cib.load(resources=resources_primitive)
        self.config_pcmk_action(stderr=stderr, returncode=1)
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(self.env_assist.get_env(), "A"),
            [
                fixture.error(
                    self.report_code_resource_stopped,
                    resource_id="A",
                ),
            ],
            expected_in_processor=False,
        )

    def test_node_not_found(self):
        self.config.runner.cib.load(resources=resources_primitive)
        node = "node"
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(self.env_assist.get_env(), "A", node)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND, node=node, searched_types=[]
                )
            ]
        )

    def test_all_options(self):
        self.config.runner.cib.load(
            resources=resources_promotable, nodes=nodes_section
        )
        self.config_pcmk_action(
            resource="A-clone",
            master=True,
            node="node",
            lifetime="1h",
        )
        self.lib_action(
            self.env_assist.get_env(),
            "A-clone",
            master=True,
            node="node",
            lifetime="1h",
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A-clone",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
            ]
        )


class MoveMixin:
    lib_action = staticmethod(resource.move)
    report_code_bad_master = (
        report_codes.CANNOT_MOVE_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
    )
    report_code_pcmk_error = report_codes.RESOURCE_MOVE_PCMK_ERROR
    report_code_pcmk_success = report_codes.RESOURCE_MOVE_PCMK_SUCCESS
    report_code_resource_stopped = (
        report_codes.CANNOT_MOVE_RESOURCE_STOPPED_NO_NODE_SPECIFIED
    )

    def config_pcmk_action(self, *args, **kwargs):
        self.config.runner.pcmk.resource_move(*args, **_action_kwargs(kwargs))


class Move(MoveMixin, MoveBanBaseMixin, TestCase):
    def test_resource_may_or_may_not_move(self):
        self.config.runner.cib.load(
            resources=resources_primitive, nodes=nodes_section
        )
        self.config_pcmk_action(
            resource="A", node="node1", stdout="", stderr=""
        )
        self.lib_action(self.env_assist.get_env(), "A", node="node1")
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.RESOURCE_MAY_OR_MAY_NOT_MOVE,
                    resource_id="A",
                ),
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="",
                    stderr="",
                ),
            ]
        )


class BanMixin:
    lib_action = staticmethod(resource.ban)
    report_code_bad_master = (
        report_codes.CANNOT_BAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
    )
    report_code_pcmk_error = report_codes.RESOURCE_BAN_PCMK_ERROR
    report_code_pcmk_success = report_codes.RESOURCE_BAN_PCMK_SUCCESS
    report_code_resource_stopped = (
        report_codes.CANNOT_BAN_RESOURCE_STOPPED_NO_NODE_SPECIFIED
    )

    def config_pcmk_action(self, *args, **kwargs):
        self.config.runner.pcmk.resource_ban(*args, **_action_kwargs(kwargs))


class Ban(BanMixin, MoveBanBaseMixin, TestCase):
    pass


class UnmoveUnbanMixin:
    lib_action = staticmethod(resource.unmove_unban)
    report_code_bad_master = (
        report_codes.CANNOT_UNMOVE_UNBAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
    )
    report_code_pcmk_error = report_codes.RESOURCE_UNMOVE_UNBAN_PCMK_ERROR
    report_code_pcmk_success = report_codes.RESOURCE_UNMOVE_UNBAN_PCMK_SUCCESS

    def config_pcmk_action(self, *args, **kwargs):
        self.config.runner.pcmk.resource_clear(*args, **_action_kwargs(kwargs))


class UnmoveUnban(UnmoveUnbanMixin, MoveBanClearBaseMixin, TestCase):
    def test_all_options(self):
        self.config.runner.cib.load(resources=resources_promotable)
        self.config.runner.pcmk.can_clear_expired()
        self.config_pcmk_action(
            resource="A-clone", master=True, node="node", expired=True
        )
        self.lib_action(
            self.env_assist.get_env(),
            "A-clone",
            master=True,
            node="node",
            expired=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A-clone",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
            ]
        )

    def test_expired_not_supported(self):
        self.config.runner.cib.load(resources=resources_promotable)
        self.config.runner.pcmk.can_clear_expired(stderr="not supported")
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", expired=True
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.RESOURCE_UNMOVE_UNBAN_PCMK_EXPIRED_NOT_SUPPORTED
                ),
            ]
        )


class MoveBanWaitMixin:
    state_running_node1 = """
        <resources>
            <resource id="A" role="Started" nodes_running_on="1">
                 <node name="node1" id="1" cached="false" />
             </resource>
        </resources>
    """
    state_running_node2 = """
        <resources>
            <resource id="A" role="Started" nodes_running_on="1">
                 <node name="node2" id="2" cached="false" />
             </resource>
        </resources>
    """
    state_not_running = """
        <resources>
            <resource id="A" role="Stopped" nodes_running_on="0">
             </resource>
        </resources>
    """

    def setUp(self):
        self.timeout = 10
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            resources=resources_primitive, nodes=nodes_section
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_state_before_action_fail(self):
        self.config.runner.pcmk.load_state(
            stdout="state stdout", stderr="state stderr", returncode=1
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(self.env_assist.get_env(), "A", wait="10"),
            [
                fixture.error(
                    report_codes.CRM_MON_ERROR,
                    reason="state stderr\nstate stdout",
                ),
            ],
            expected_in_processor=False,
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_state_before_action_not_xml(self):
        self.config.runner.pcmk.load_state(stdout="state stdout")
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=str(self.timeout)
            ),
            [
                fixture.error(
                    report_codes.BAD_CLUSTER_STATE_FORMAT,
                ),
            ],
            expected_in_processor=False,
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_pcmk_fail(self):
        self.config.runner.pcmk.load_state()
        self.config_pcmk_action(returncode=1)
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=str(self.timeout)
            ),
            [
                fixture.error(
                    self.report_code_pcmk_error,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
            ],
            expected_in_processor=False,
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_wait_fail(self):
        self.config.runner.pcmk.load_state()
        self.config_pcmk_action()
        self.config.runner.pcmk.wait(
            timeout=self.timeout, stderr="wait error", returncode=1
        )

        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=str(self.timeout)
            ),
            [
                fixture.error(
                    report_codes.WAIT_FOR_IDLE_ERROR,
                    reason="wait error",
                ),
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_state_after_action_fail(self):
        self.config.runner.pcmk.load_state()
        self.config_pcmk_action()
        self.config.runner.pcmk.wait(timeout=self.timeout)
        self.config.runner.pcmk.load_state(
            name="runner.pcmk.load_state.after",
            stdout="state stdout",
            stderr="state stderr",
            returncode=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=self.timeout
            ),
            [
                fixture.error(
                    report_codes.CRM_MON_ERROR,
                    reason="state stderr\nstate stdout",
                ),
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
            ]
        )

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_state_after_action_not_xml(self):
        self.config.runner.pcmk.load_state()
        self.config_pcmk_action()
        self.config.runner.pcmk.wait(timeout=self.timeout)
        self.config.runner.pcmk.load_state(
            name="runner.pcmk.load_state.after", stdout="state stdout"
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=self.timeout
            ),
            [
                fixture.error(
                    report_codes.BAD_CLUSTER_STATE_FORMAT,
                ),
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
            ]
        )

    def test_was_running_now_stopped(self):
        self.success_config(self.state_running_node1, self.state_not_running)
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=self.timeout
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
                fixture.report_resource_not_running(
                    "A", severity=severities.ERROR
                ),
            ]
        )

    def test_was_stopped_now_stopped(self):
        self.success_config(self.state_not_running, self.state_not_running)
        self.lib_action(self.env_assist.get_env(), "A", wait=self.timeout)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
                fixture.report_resource_not_running(
                    "A",
                ),
            ]
        )

    def test_running_on_same_node_no_node_specified(self):
        self.success_config(self.state_running_node1, self.state_running_node1)
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=self.timeout
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
                fixture.report_resource_running(
                    "A", {"Started": ["node1"]}, severity=severities.ERROR
                ),
            ]
        )

    def test_running_on_onther_node_no_node_specified(self):
        self.success_config(self.state_running_node1, self.state_running_node2)
        self.lib_action(self.env_assist.get_env(), "A", wait=self.timeout)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
                fixture.report_resource_running(
                    "A",
                    {"Started": ["node2"]},
                ),
            ]
        )

    def success_config(self, state_before, state_after, action_node=None):
        self.config.runner.pcmk.load_state(resources=state_before)
        self.config_pcmk_action(node=action_node)
        self.config.runner.pcmk.wait(timeout=self.timeout)
        self.config.runner.pcmk.load_state(
            name="runner.pcmk.load_state.after",
            resources=state_after,
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class MoveWait(MoveMixin, MoveBanWaitMixin, TestCase):
    def test_running_on_specified_node(self):
        self.success_config(
            self.state_running_node1,
            self.state_running_node2,
            action_node="node2",
        )
        self.lib_action(
            self.env_assist.get_env(), "A", node="node2", wait=self.timeout
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
                fixture.report_resource_running(
                    "A",
                    {"Started": ["node2"]},
                ),
            ]
        )

    def test_running_on_not_specified_node(self):
        self.success_config(
            self.state_running_node1,
            self.state_running_node1,
            action_node="node2",
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", node="node2", wait=self.timeout
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
                fixture.report_resource_running(
                    "A", {"Started": ["node1"]}, severity=severities.ERROR
                ),
            ]
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class BanWait(BanMixin, MoveBanWaitMixin, TestCase):
    def test_running_on_specified_node(self):
        self.success_config(
            self.state_running_node1,
            self.state_running_node1,
            action_node="node1",
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", node="node1", wait=self.timeout
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
                fixture.report_resource_running(
                    "A", {"Started": ["node1"]}, severity=severities.ERROR
                ),
            ]
        )

    def test_running_on_not_specified_node(self):
        self.success_config(
            self.state_running_node1,
            self.state_running_node2,
            action_node="node1",
        )
        self.lib_action(
            self.env_assist.get_env(), "A", node="node1", wait=self.timeout
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
                fixture.report_resource_running(
                    "A",
                    {"Started": ["node2"]},
                ),
            ]
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class UnmoveUnbanWait(UnmoveUnbanMixin, TestCase):
    def setUp(self):
        self.timeout = 10
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(resources=resources_primitive)
        self.config_pcmk_action()

    def test_success(self):
        resources_state = """
            <resources>
                <resource id="A" role="Started" nodes_running_on="1">
                     <node name="node1" id="1" cached="false" />
                 </resource>
            </resources>
        """
        self.config.runner.pcmk.wait(timeout=self.timeout)
        self.config.runner.pcmk.load_state(resources=resources_state)

        self.lib_action(self.env_assist.get_env(), "A", wait=self.timeout)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
                fixture.report_resource_running("A", {"Started": ["node1"]}),
            ]
        )

    def test_get_state_fail(self):
        self.config.runner.pcmk.wait(timeout=self.timeout)
        self.config.runner.pcmk.load_state(
            stdout="state stdout", stderr="state stderr", returncode=1
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=self.timeout
            ),
            [
                fixture.error(
                    report_codes.CRM_MON_ERROR,
                    reason="state stderr\nstate stdout",
                ),
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
            ]
        )

    def test_get_state_not_xml(self):
        self.config.runner.pcmk.wait(timeout=self.timeout)
        self.config.runner.pcmk.load_state(stdout="state stdout")
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=self.timeout
            ),
            [
                fixture.error(
                    report_codes.BAD_CLUSTER_STATE_FORMAT,
                ),
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
            ]
        )

    def test_wait_fail(self):
        self.config.runner.pcmk.wait(
            timeout=self.timeout, stderr="wait error", returncode=1
        )

        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(
                self.env_assist.get_env(), "A", wait=self.timeout
            ),
            [
                fixture.error(
                    report_codes.WAIT_FOR_IDLE_ERROR,
                    reason="wait error",
                ),
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    self.report_code_pcmk_success,
                    resource_id="A",
                    stdout="pcmk std out",
                    stderr="pcmk std err",
                ),
                fixture.info(
                    report_codes.WAIT_FOR_IDLE_STARTED,
                    timeout=self.timeout,
                ),
            ]
        )

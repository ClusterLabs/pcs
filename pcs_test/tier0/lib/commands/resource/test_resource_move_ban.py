from textwrap import dedent
from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import resource

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


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
resources_stonith = """
    <resources>
        <primitive id="S" class="stonith" />
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

    def test_resource_is_stonith(self):
        self.config.runner.cib.load(resources=resources_stonith)
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(self.env_assist.get_env(), "S")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COMMAND_ARGUMENT_TYPE_MISMATCH,
                    not_accepted_type="stonith resource",
                    command_to_use_instead=None,
                ),
            ]
        )

    def test_promoted_of_nonpromotable_resource(self):
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
                    self.report_code_bad_promoted,
                    resource_id="A",
                    promotable_id="",
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
            promoted=True,
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

    def assert_multiple_instance(self, stderr, report_code):
        self.config.runner.cib.load(
            resources=resources_primitive, nodes=nodes_section
        )
        self.config_pcmk_action(resource="A", stderr=stderr, returncode=1)
        self.env_assist.assert_raise_library_error(
            lambda: self.lib_action(self.env_assist.get_env(), "A"),
            [
                fixture.error(report_code, resource_id="A"),
            ],
            expected_in_processor=False,
        )

    def test_multiple_instance_1(self):
        self.assert_multiple_instance(
            "Resource 'A' not moved: active in 2 locations.",
            self.report_code_multiple_instances,
        )


class Move(MoveBanBaseMixin, TestCase):
    lib_action = staticmethod(resource.move)
    report_code_bad_promoted = (
        report_codes.CANNOT_MOVE_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
    )
    report_code_pcmk_error = report_codes.RESOURCE_MOVE_PCMK_ERROR
    report_code_pcmk_success = report_codes.RESOURCE_MOVE_PCMK_SUCCESS
    report_code_resource_stopped = (
        report_codes.CANNOT_MOVE_RESOURCE_STOPPED_NO_NODE_SPECIFIED
    )
    report_code_multiple_instances = (
        report_codes.CANNOT_MOVE_RESOURCE_MULTIPLE_INSTANCES_NO_NODE_SPECIFIED
    )

    def config_pcmk_action(self, *args, **kwargs):
        self.config.runner.pcmk.resource_move(*args, **_action_kwargs(kwargs))

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

    def test_multiple_instance_2(self):
        self.assert_multiple_instance(
            "Error performing operation: Multiple items match request",
            report_codes.CANNOT_MOVE_RESOURCE_MULTIPLE_INSTANCES,
        )


class Ban(MoveBanBaseMixin, TestCase):
    lib_action = staticmethod(resource.ban)
    report_code_bad_promoted = (
        report_codes.CANNOT_BAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
    )
    report_code_pcmk_error = report_codes.RESOURCE_BAN_PCMK_ERROR
    report_code_pcmk_success = report_codes.RESOURCE_BAN_PCMK_SUCCESS
    report_code_resource_stopped = (
        report_codes.CANNOT_BAN_RESOURCE_STOPPED_NO_NODE_SPECIFIED
    )
    report_code_multiple_instances = (
        report_codes.CANNOT_BAN_RESOURCE_MULTIPLE_INSTANCES_NO_NODE_SPECIFIED
    )

    def config_pcmk_action(self, *args, **kwargs):
        self.config.runner.pcmk.resource_ban(*args, **_action_kwargs(kwargs))


class UnmoveUnban(MoveBanClearBaseMixin, TestCase):
    lib_action = staticmethod(resource.unmove_unban)
    report_code_bad_promoted = (
        report_codes.CANNOT_UNMOVE_UNBAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
    )
    report_code_pcmk_error = report_codes.RESOURCE_UNMOVE_UNBAN_PCMK_ERROR
    report_code_pcmk_success = report_codes.RESOURCE_UNMOVE_UNBAN_PCMK_SUCCESS

    def config_pcmk_action(self, *args, **kwargs):
        self.config.runner.pcmk.resource_clear(*args, **_action_kwargs(kwargs))

    def test_all_options(self):
        self.config.runner.cib.load(resources=resources_promotable)
        self.config.runner.pcmk.can_clear_expired()
        self.config_pcmk_action(
            resource="A-clone", promoted=True, node="node", expired=True
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

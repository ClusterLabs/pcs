from unittest import TestCase

from pcs.common import reports
from pcs.lib.commands import resource

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class ResourceRestart(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        resources_xml = """
            <resources>
                <primitive id="S1" class="stonith" />
                <primitive id="R1" class="ocf">
                    <meta_attributes id="R1-meta" />
                </primitive>
                <bundle id="B1">
                    <primitive id="B1R1" />
                </bundle>
                <clone id="C1">
                    <primitive id="C1R1" />
                </clone>
                <clone id="C2">
                    <group id="C2G1">
                        <primitive id="C2R1" />
                    </group>
                </clone>
            </resources>
        """
        self.config.runner.cib.load(resources=resources_xml)

    def test_success(self):
        self.config.runner.pcmk.resource_restart("R1")
        resource.restart(self.env_assist.get_env(), "R1")

    def test_success_bundle_member(self):
        self.config.runner.pcmk.resource_restart("B1")
        resource.restart(self.env_assist.get_env(), "B1R1")
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_RESTART_USING_PARENT_RESOURCE,
                    resource="B1R1",
                    parent="B1",
                )
            ]
        )

    def test_success_clone_member(self):
        self.config.runner.pcmk.resource_restart("C1")
        resource.restart(self.env_assist.get_env(), "C1R1")
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_RESTART_USING_PARENT_RESOURCE,
                    resource="C1R1",
                    parent="C1",
                )
            ]
        )

    def test_success_clone_group_member(self):
        self.config.runner.pcmk.resource_restart("C2")
        resource.restart(self.env_assist.get_env(), "C2R1")
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_RESTART_USING_PARENT_RESOURCE,
                    resource="C2R1",
                    parent="C2",
                )
            ]
        )

    def test_success_timeout(self):
        self.config.runner.pcmk.resource_restart("R1", timeout="10")
        resource.restart(self.env_assist.get_env(), "R1", timeout="10")

    def test_success_all_options(self):
        self.config.runner.pcmk.resource_restart(
            "C1", node="node1", timeout="10"
        )
        resource.restart(self.env_assist.get_env(), "C1", "node1", "10")

    def test_bad_timeout(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.restart(
                self.env_assist.get_env(), "R1", timeout="a while"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="a while",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ]
        )

    def test_resource_not_found(self):
        self.config.runner.pcmk.resource_restart("RX")
        resource.restart(self.env_assist.get_env(), "RX")

    def test_not_a_resource(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.restart(self.env_assist.get_env(), "R1-meta")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R1-meta",
                    expected_types=["resource"],
                    current_type="meta_attributes",
                )
            ]
        )

    def test_stonith(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.restart(self.env_assist.get_env(), "S1")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COMMAND_ARGUMENT_TYPE_MISMATCH,
                    not_accepted_type="stonith resource",
                    command_to_use_instead=None,
                )
            ]
        )

    def test_node_not_multitinstance(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.restart(
                self.env_assist.get_env(), "R1", node="node1"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_RESTART_NODE_IS_FOR_MULTIINSTANCE_ONLY,
                    resource="R1",
                    resource_type="primitive",
                    node="node1",
                )
            ]
        )

    def test_node_multitinstance(self):
        self.config.runner.pcmk.resource_restart("C1", node="node1")
        resource.restart(self.env_assist.get_env(), "C1", "node1")

    def test_restart_error(self):
        self.config.runner.pcmk.resource_restart(
            "R1", stdout="some output", stderr="some error", returncode=1
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.restart(self.env_assist.get_env(), "R1"),
            [
                fixture.error(
                    reports.codes.RESOURCE_RESTART_ERROR,
                    reason="some error\nsome output",
                    resource="R1",
                    node=None,
                )
            ],
            expected_in_processor=False,
        )

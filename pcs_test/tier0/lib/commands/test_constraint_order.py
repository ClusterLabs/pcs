from unittest import TestCase

from pcs.common import reports
from pcs.lib.commands import constraint

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class SetCreate(TestCase):
    def setUp(self):
        resources_xml = """
            <resources>
                <group id="grAB">
                    <primitive class="ocf" id="A" provider="pacemaker" type="Dummy"/>
                    <primitive class="ocf" id="B" provider="pacemaker" type="Dummy"/>
                </group>
                <group id="grC">
                    <primitive class="ocf" id="C" provider="pacemaker" type="Dummy"/>
                </group>
                <primitive class="ocf" id="D" provider="pacemaker" type="Dummy"/>
            </resources>
        """
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(resources=resources_xml)

    def test_deny_resources_from_one_group_in_one_set(self):
        self.env_assist.assert_raise_library_error(
            lambda: constraint.order.create_with_set(
                self.env_assist.get_env(),
                [{"ids": ["A", "B"], "options": {}}],
                {},
            ),
            [
                fixture.error(
                    reports.codes.CANNOT_SET_ORDER_CONSTRAINTS_FOR_RESOURCES_IN_THE_SAME_GROUP,
                )
            ],
            expected_in_processor=False,
        )

    def test_deny_resources_from_one_group_in_different_sets(self):
        self.env_assist.assert_raise_library_error(
            lambda: constraint.order.create_with_set(
                self.env_assist.get_env(),
                [{"ids": ["A"], "options": {}}, {"ids": ["B"], "options": {}}],
                {},
            ),
            [
                fixture.error(
                    reports.codes.CANNOT_SET_ORDER_CONSTRAINTS_FOR_RESOURCES_IN_THE_SAME_GROUP,
                )
            ],
            expected_in_processor=False,
        )

    def test_allow_resources_from_different_groups(self):
        constraints_xml = """
            <constraints>
                <rsc_order id="order_set_AACCAA">
                    <resource_set id="order_set_AACCAA_set">
                        <resource_ref id="A"/>
                        <resource_ref id="C"/>
                    </resource_set>
                    <resource_set id="order_set_AACCAA_set-1">
                        <resource_ref id="A"/>
                        <resource_ref id="D"/>
                    </resource_set>
                </rsc_order>
            </constraints>
        """
        self.config.env.push_cib(constraints=constraints_xml)

        constraint.order.create_with_set(
            self.env_assist.get_env(),
            [
                {"ids": ["A", "C"], "options": {}},
                {"ids": ["A", "D"], "options": {}},
            ],
            {},
        )

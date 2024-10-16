from unittest import TestCase

from pcs.common import (
    const,
    reports,
)
from pcs.common.pacemaker.types import CibResourceDiscovery
from pcs.lib.cib import const as cib_const
from pcs.lib.commands.constraint import location

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class CreatePlainWithRule(TestCase):
    # pylint: disable=too-many-public-methods
    resources_xml = """
        <resources>
          <primitive id="R1" class="ocf" provider="pacemaker" type="Dummy">
            <operations>
              <op id="R1-monitor" name="monitor" interval="60s" />
            </operations>
          </primitive>
          <group id="G1">
            <primitive id="G1R1" class="ocf" provider="pacemaker" type="Dummy" />
            <primitive id="G1R2" class="ocf" provider="pacemaker" type="Dummy" />
          </group>
          <clone id="C1">
            <primitive id="C1R1" class="ocf" provider="pacemaker" type="Dummy" />
          </clone>
          <bundle id="B1">
            <docker image="pcs:test"/>
            <primitive id="B1R1" class="ocf" provider="pacemaker" type="Dummy" />
          </bundle>
        </resources>
    """
    constraints_xml_minimal = """
        <constraints>
          <rsc_location id="location-{resource_id}" rsc="{resource_id}">
            <rule id="location-{resource_id}-rule" boolean-op="and"
                score="INFINITY"
            >
              <expression id="location-{resource_id}-rule-expr"
                  attribute="#uname" operation="eq" value="node1"
              />
            </rule>
          </rsc_location>
          {other_constraint}
        </constraints>
    """
    constraints_xml_integer = """
        <constraints>
          <rsc_location id="location-R1" rsc="R1">
            <rule id="location-R1-rule" boolean-op="and" score="INFINITY">
              <expression id="location-R1-rule-expr"
                  attribute="attr" operation="gt" type="{type}" value="7"
              />
            </rule>
          </rsc_location>
        </constraints>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def assert_success_minimal(self, resource_id):
        self.config.runner.cib.load(resources=self.resources_xml)
        constraints_xml = self.constraints_xml_minimal.format(
            resource_id=resource_id, other_constraint=""
        )
        self.config.env.push_cib(constraints=constraints_xml)

        location.create_plain_with_rule(
            self.env_assist.get_env(),
            const.RESOURCE_ID_TYPE_PLAIN,
            resource_id,
            "#uname eq node1",
            {},
            {},
            [],
        )

    def test_success_minimal_primitive(self):
        self.assert_success_minimal("R1")

    def test_success_minimal_group(self):
        self.assert_success_minimal("G1")

    def test_success_minimal_clone(self):
        self.assert_success_minimal("C1")

    def test_success_minimal_bundle(self):
        self.assert_success_minimal("B1")

    def test_success_all_options_1(self):
        constraints_xml = """
            <constraints>
              <rsc_location id="L1" rsc="R1" resource-discovery="always">
                <rule id="X" boolean-op="and" score="9" role="Master">
                  <expression id="X-expr"
                      attribute="#uname" operation="eq" value="node1"
                  />
                </rule>
              </rsc_location>
            </constraints>
        """
        self.config.runner.cib.load(resources=self.resources_xml)
        self.config.env.push_cib(constraints=constraints_xml)

        location.create_plain_with_rule(
            self.env_assist.get_env(),
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "#uname eq node1",
            {
                "id": "X",
                # test role normalization
                "role": str(const.PCMK_ROLE_PROMOTED).upper(),
                "score": "9",
            },
            {"id": "L1", "resource-discovery": CibResourceDiscovery.ALWAYS},
            [],
        )

    def test_success_all_options_2(self):
        constraints_xml = """
            <constraints>
              <rsc_location id="L1" rsc-pattern="R\\d+"
                  resource-discovery="exclusive"
              >
                <rule id="L1-rule" boolean-op="and" score-attribute="attr"
                    role="Unpromoted"
                >
                  <expression id="L1-rule-expr"
                      attribute="#uname" operation="eq" value="node1"
                  />
                </rule>
              </rsc_location>
            </constraints>
        """
        self.config.runner.cib.load(
            resources=self.resources_xml, filename="cib-empty-3.7.xml"
        )
        self.config.env.push_cib(constraints=constraints_xml)

        location.create_plain_with_rule(
            self.env_assist.get_env(),
            const.RESOURCE_ID_TYPE_REGEXP,
            "R\\d+",
            "#uname eq node1",
            {"role": const.PCMK_ROLE_UNPROMOTED, "score-attribute": "attr"},
            {"id": "L1", "resource-discovery": CibResourceDiscovery.EXCLUSIVE},
            [],
        )

    def test_rule_with_integer_new_cib(self):
        self.config.runner.cib.load(
            resources=self.resources_xml, filename="cib-empty-3.7.xml"
        )
        self.config.env.push_cib(
            constraints=self.constraints_xml_integer.format(type="integer")
        )

        location.create_plain_with_rule(
            self.env_assist.get_env(),
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "attr gt integer 7",
            {},
            {},
            [],
        )

    def test_rule_with_integer_old_cib(self):
        self.config.runner.cib.load(resources=self.resources_xml)
        self.config.runner.cib.upgrade()
        self.config.runner.cib.load(
            resources=self.resources_xml,
            filename="cib-empty-3.7.xml",
            name="runner.cib.load.2",
        )
        self.config.env.push_cib(
            constraints=self.constraints_xml_integer.format(type="integer"),
            load_key="runner.cib.load.2",
        )

        location.create_plain_with_rule(
            self.env_assist.get_env(),
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "attr gt integer 7",
            {},
            {},
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.CIB_UPGRADE_SUCCESSFUL),
            ]
        )

    def test_rule_with_integer_old_cib_update_not_possible(self):
        self.config.runner.cib.load(resources=self.resources_xml)
        self.config.runner.cib.upgrade()
        self.config.runner.cib.load(
            resources=self.resources_xml, name="runner.cib.load.2"
        )
        self.config.env.push_cib(
            constraints=self.constraints_xml_integer.format(type="number")
        )

        location.create_plain_with_rule(
            self.env_assist.get_env(),
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "attr gt integer 7",
            {},
            {},
            [],
        )

    def test_duplicate_constraint(self):
        self.config.runner.cib.load(
            resources=self.resources_xml,
            constraints=self.constraints_xml_minimal.format(
                resource_id="R1", other_constraint=""
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: location.create_plain_with_rule(
                self.env_assist.get_env(),
                const.RESOURCE_ID_TYPE_PLAIN,
                "R1",
                "#uname eq node1",
                {},
                {},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                    force_code=reports.codes.FORCE,
                    constraint_ids=["location-R1"],
                )
            ]
        )

    def test_duplicate_constraint_forced(self):
        self.config.runner.cib.load(
            resources=self.resources_xml,
            constraints=self.constraints_xml_minimal.format(
                resource_id="R1", other_constraint=""
            ),
        )
        constraints_xml = self.constraints_xml_minimal.format(
            resource_id="R1",
            other_constraint="""
                <rsc_location id="location-R1-1" rsc="R1">
                  <rule id="location-R1-1-rule" boolean-op="and" score="INFINITY">
                    <expression id="location-R1-1-rule-expr"
                        attribute="#uname" operation="eq" value="node1"
                    />
                  </rule>
                </rsc_location>
            """,
        )
        self.config.env.push_cib(constraints=constraints_xml)

        location.create_plain_with_rule(
            self.env_assist.get_env(),
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            "#uname eq node1",
            {},
            {},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                    constraint_ids=["location-R1"],
                )
            ]
        )

    def assert_resource_in_multiinstance(
        self, resource_id, parent_type, parent_id
    ):
        self.config.runner.cib.load(resources=self.resources_xml)
        self.env_assist.assert_raise_library_error(
            lambda: location.create_plain_with_rule(
                self.env_assist.get_env(),
                const.RESOURCE_ID_TYPE_PLAIN,
                resource_id,
                "#uname eq node1",
                {},
                {},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    force_code=reports.codes.FORCE,
                    resource_id=resource_id,
                    parent_type=parent_type,
                    parent_id=parent_id,
                )
            ]
        )

    def assert_resource_in_multiinstance_forced(
        self, resource_id, parent_type, parent_id
    ):
        constraints_xml = self.constraints_xml_minimal.format(
            resource_id=resource_id, other_constraint=""
        )
        self.config.runner.cib.load(resources=self.resources_xml)
        self.config.env.push_cib(constraints=constraints_xml)

        location.create_plain_with_rule(
            self.env_assist.get_env(),
            const.RESOURCE_ID_TYPE_PLAIN,
            resource_id,
            "#uname eq node1",
            {},
            {},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    resource_id=resource_id,
                    parent_type=parent_type,
                    parent_id=parent_id,
                )
            ]
        )

    def test_resource_in_clone(self):
        self.assert_resource_in_multiinstance("C1R1", "clone", "C1")

    def test_resource_in_bundle(self):
        self.assert_resource_in_multiinstance("B1R1", "bundle", "B1")

    def test_resource_in_clone_forced(self):
        self.assert_resource_in_multiinstance_forced("C1R1", "clone", "C1")

    def test_resource_in_bundle_forced(self):
        self.assert_resource_in_multiinstance_forced("B1R1", "bundle", "B1")

    def test_resource_not_found(self):
        self.config.runner.cib.load(resources=self.resources_xml)
        self.env_assist.assert_raise_library_error(
            lambda: location.create_plain_with_rule(
                self.env_assist.get_env(),
                const.RESOURCE_ID_TYPE_PLAIN,
                "RX",
                "#uname eq node1",
                {},
                {},
                [reports.codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="RX",
                    expected_types=[],
                    context_type="",
                    context_id="",
                ),
            ]
        )

    def test_not_resource(self):
        self.config.runner.cib.load(resources=self.resources_xml)
        self.env_assist.assert_raise_library_error(
            lambda: location.create_plain_with_rule(
                self.env_assist.get_env(),
                const.RESOURCE_ID_TYPE_PLAIN,
                "R1-monitor",
                "#uname eq node1",
                {},
                {},
                [reports.codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R1-monitor",
                    expected_types=sorted(cib_const.TAG_LIST_CONSTRAINABLE),
                    current_type="op",
                ),
            ]
        )

    def test_errors(self):
        self.config.runner.cib.load(resources=self.resources_xml)
        self.env_assist.assert_raise_library_error(
            lambda: location.create_plain_with_rule(
                self.env_assist.get_env(),
                "bad resource id type",
                "R1",
                "#uname eq",
                {
                    "bad": "option",
                    "score": "bad score",
                    "score-attribute": "some attribute",
                    "role": "bad role",
                    "id": "R1-monitor",
                },
                {
                    "bad": "option",
                    "id": "B1R1",
                    "resource-discovery": "bad discovery",
                },
                [reports.codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_ID_TYPE,
                    id_type="bad resource id type",
                    allowed_types=["resource_id_plain", "resource_id_regexp"],
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["bad"],
                    allowed=["id", "resource-discovery"],
                    option_type="constraint",
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.ID_ALREADY_EXISTS,
                    id="B1R1",
                ),
                fixture.warn(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="resource-discovery",
                    option_value="bad discovery",
                    allowed_values=[
                        CibResourceDiscovery.ALWAYS,
                        CibResourceDiscovery.EXCLUSIVE,
                        CibResourceDiscovery.NEVER,
                    ],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["bad"],
                    allowed=["id", "role", "score", "score-attribute"],
                    option_type="rule",
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    option_names=["score", "score-attribute"],
                    option_type="rule",
                ),
                fixture.error(
                    reports.codes.ID_ALREADY_EXISTS,
                    id="R1-monitor",
                ),
                fixture.error(
                    reports.codes.INVALID_SCORE,
                    score="bad score",
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    option_value="bad role",
                    allowed_values=(
                        const.PCMK_ROLE_PROMOTED,
                        const.PCMK_ROLE_UNPROMOTED,
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.RULE_EXPRESSION_PARSE_ERROR,
                    rule_string="#uname eq",
                    reason="Expected <attribute value>",
                    rule_line="#uname eq",
                    line_number=1,
                    column_number=10,
                    position=9,
                ),
            ]
        )

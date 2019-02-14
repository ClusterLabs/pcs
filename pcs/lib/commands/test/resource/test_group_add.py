from unittest import TestCase

from lxml import etree

from pcs.common import report_codes
from pcs.lib.commands import resource
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.xml import etree_to_str

class GroupAdd(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_existing_group(self):
        resources_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                </group>
                <primitive id="R1" />
                <primitive id="R2" />
                <primitive id="R3" />
            </resources>
        """
        resources_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="R3" />
                    <primitive id="R1" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
            .env.push_cib(resources=resources_after)
        )
        resource.group_add(
            self.env_assist.get_env(),
            "G",
            ["R3", "R1"]
        )

    def test_group_id_belongs_to_another_element(self):
        resources_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                </group>
                <primitive id="R1">
                    <meta_attributes id="R1-meta_attributes" />
                </primitive>
                <primitive id="R2" />
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "R1-meta_attributes",
                ["R2"]
            ),
            [
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R1-meta_attributes",
                    expected_types=["group"],
                    current_type="meta_attributes",
                ),
            ],
        )

    def test_new_group(self):
        resources_before = """
            <resources>
                <primitive id="R1" />
                <primitive id="R2" />
                <primitive id="R3" />
            </resources>
        """
        resources_after = """
            <resources>
                <primitive id="R2" />
                <group id="G">
                    <primitive id="R3" />
                    <primitive id="R1" />
                </group>
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
            .env.push_cib(resources=resources_after)
        )
        resource.group_add(
            self.env_assist.get_env(),
            "G",
            ["R3", "R1"]
        )

    def test_new_group_not_valid_id(self):
        resources_before = """
            <resources>
                <primitive id="R1" />
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "1Gr:oup",
                ["R1"]
            ),
            [
                fixture.error(
                    report_codes.INVALID_ID,
                    id="1Gr:oup",
                    id_description="group name",
                    is_first_char=True,
                    invalid_character="1",
                ),
                fixture.error(
                    report_codes.INVALID_ID,
                    id="1Gr:oup",
                    id_description="group name",
                    is_first_char=False,
                    invalid_character=":",
                ),
            ],
        )

    def test_add_missing_resources(self):
        resources_before = """
            <resources>
                <primitive id="R1" />
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["R3", "R2"]
            ),
            [
                fixture.report_not_found("R3", context_type="resources"),
                fixture.report_not_found("R2", context_type="resources"),
            ],
        )

    def test_add_wrong_resources(self):
        resources_before = """
            <resources>
                <primitive id="R1" />
                <clone id="RC1-clone">
                    <primitive id="RC1" />
                </clone>
                <bundle id="RB1-bundle">
                    <primitive id="RB1" />
                </bundle>
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["R1", "RC1-clone", "RC1", "RB1-bundle", "RB1"]
            ),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1-clone",
                    resource_type="clone",
                ),
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1",
                    resource_type="clone",
                ),
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RB1-bundle",
                    resource_type="bundle",
                ),
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RB1",
                    resource_type="bundle",
                ),
            ],
        )

    def test_add_not_resource_elements(self):
        resources_before = """
            <resources>
                <primitive id="R1">
                    <meta_attributes id="R1-meta_attributes" />
                </primitive>
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["R1", "R1-meta_attributes"]
            ),
            [
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R1-meta_attributes",
                    expected_types=[
                        "clone", "master", "group", "primitive", "bundle"
                    ],
                    current_type="meta_attributes",
                ),
            ],
        )

    def test_adjacent_resource_in_another_group(self):
        resources_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                </group>
                <group id="X">
                    <primitive id="RX1" />
                </group>
                <primitive id="R1" />
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["R1"],
                adjacent_resource_id="RX1"
            ),
            [
                fixture.error(
                    report_codes.OBJECT_WITH_ID_IN_UNEXPECTED_CONTEXT,
                    type="primitive",
                    id="RX1",
                    expected_context_type="group",
                    expected_context_id="G",
                ),
            ],
        )

    def test_adjacent_resource_not_in_group(self):
        resources_before = """
            <resources>
                <primitive id="R1" />
                <primitive id="R2" />
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["R1"],
                adjacent_resource_id="R2"
            ),
            [
                fixture.error(
                    report_codes.OBJECT_WITH_ID_IN_UNEXPECTED_CONTEXT,
                    type="primitive",
                    id="R2",
                    expected_context_type="group",
                    expected_context_id="G",
                ),
            ],
        )

    def test_adjacent_resource_doesnt_exist(self):
        resources_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                </group>
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["RG1"],
                adjacent_resource_id="R2"
            ),
            [
                fixture.error(
                    report_codes.ID_NOT_FOUND,
                    id="R2",
                    expected_types=["primitive"],
                    context_type="group",
                    context_id="G",
                ),
            ],
        )

    def test_resources_already_in_the_group(self):
        resources_before = """
            <resources>
                <group id="G">
                    <primitive id="R1" />
                    <primitive id="R2" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["R3", "R2", "R1"],
            ),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_ALREADY_IN_THE_GROUP,
                    resource_list=["R1", "R2"],
                    group_id="G",
                ),
            ],
        )

    def _assert_with_adjacent(self, adjacent_id, after_adjacent):
        resources_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RGX" />
                </group>
                <primitive id="R1" />
                <primitive id="R2" />
                <primitive id="R3" />
            </resources>
        """
        resources_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="R3" />
                    <primitive id="RGX" />
                    <primitive id="R1" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
            .env.push_cib(resources=resources_after)
        )
        resource.group_add(
            self.env_assist.get_env(),
            "G",
            ["R3", "RGX", "R1"],
            adjacent_resource_id=adjacent_id,
            put_after_adjacent=after_adjacent
        )

    def test_after_adjacent(self):
        self._assert_with_adjacent("RG1", True)

    def test_before_adjacent(self):
        self._assert_with_adjacent("RG2", False)

    def test_remove_empty_containers(self):
        resources_before = """
            <resources>
                <group id="X">
                    <primitive id="RX1" />
                </group>
                <group id="Y">
                    <primitive id="RY1" />
                    <primitive id="RY2" />
                </group>
                <clone id="RC1-group-clone">
                    <group id="RC1-group">
                        <primitive id="RC1" />
                    </group>
                </clone>
                <master id="RM1-group-master">
                    <group id="RM1-group">
                        <primitive id="RM1" />
                    </group>
                </master>
            </resources>
        """
        resources_after = """
            <resources>
                <group id="Y">
                    <primitive id="RY1" />
                </group>
                <group id="G">
                    <primitive id="RX1" />
                    <primitive id="RY2" />
                    <primitive id="RC1" />
                    <primitive id="RM1" />
                </group>
            </resources>
        """
        (self.config
            .runner.cib.load(resources=resources_before)
            .env.push_cib(resources=resources_after)
        )
        resource.group_add(
            self.env_assist.get_env(),
            "G",
            ["RX1", "RY2", "RC1", "RM1"]
        )


class GroupAddWait(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        resources_before = """
            <resources>
                <primitive id="R1" />
                <primitive id="R2" />
            </resources>
        """
        resources_after = """
            <resources>
                <group id="G">
                    <primitive id="R1" />
                    <primitive id="R2" />
                </group>
            </resources>
        """
        self.timeout = 10
        (self.config
            .runner.pcmk.can_wait()
            .runner.cib.load(resources=resources_before)
            .env.push_cib(resources=resources_after, wait=self.timeout)
        )

    def test_group_running(self):
        resources_state = fixture.complete_state_resources(etree.fromstring("""
            <resources>
                <group id="G" number_resources="2">
                    <resource id="R1" role="Started" nodes_running_on="1">
                         <node name="node1" id="1" cached="false" />
                     </resource>
                    <resource id="R2" role="Started" nodes_running_on="1">
                         <node name="node1" id="1" cached="false" />
                     </resource>
                </group>
            </resources>
        """))
        self.config.runner.pcmk.load_state(
            resources=etree_to_str(resources_state)
        )
        resource.group_add(
            self.env_assist.get_env(),
            "G",
            ["R1", "R2"],
            wait=self.timeout,
        )
        self.env_assist.assert_reports([
            fixture.report_resource_running(
                "G",
                {"Started": ["node1"]}
            ),
        ])

    def test_group_not_running(self):
        resources_state = fixture.complete_state_resources(etree.fromstring("""
            <resources>
                <group id="G" number_resources="2">
                    <resource id="R1" role="Started" nodes_running_on="1">
                         <node name="node1" id="1" cached="false" />
                     </resource>
                    <resource id="R2" role="Stopped" nodes_running_on="0">
                     </resource>
                </group>
            </resources>
        """))
        self.config.runner.pcmk.load_state(
            resources=etree_to_str(resources_state)
        )
        resource.group_add(
            self.env_assist.get_env(),
            "G",
            ["R1", "R2"],
            wait=self.timeout,
        )
        self.env_assist.assert_reports([
            fixture.report_resource_not_running("G"),
        ])

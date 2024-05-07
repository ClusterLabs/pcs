from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common.reports import codes as report_codes
from pcs.common.reports import messages as report_messages
from pcs.common.reports.const import (
    ADD_REMOVE_CONTAINER_TYPE_GROUP,
    ADD_REMOVE_ITEM_TYPE_RESOURCE,
)
from pcs.common.reports.item import ReportItem
from pcs.lib.commands import resource
from pcs.lib.errors import LibraryError

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc


# This class does not focusing on validation testing, there are validator tests
# for that in pcs_test.tier0.lib.cib.test_resource_relation
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
        (
            self.config.runner.cib.load(
                resources=resources_before
            ).env.push_cib(resources=resources_after)
        )
        resource.group_add(self.env_assist.get_env(), "G", ["R3", "R1"])

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
        (
            self.config.runner.cib.load(
                resources=resources_before
            ).env.push_cib(resources=resources_after)
        )
        resource.group_add(self.env_assist.get_env(), "G", ["R3", "R1"])

    def test_move_from_existing_to_new(self):
        resources_before = """
                    <resources>
                        <group id="G1">
                            <primitive id="RG1" />
                            <primitive id="RG2" />
                            <primitive id="RG3" />
                        </group>
                        <primitive id="R4" />
                    </resources>
                """
        resources_after = """
                    <resources>
                        <group id="G1">
                            <primitive id="RG1" />
                            <primitive id="RG2" />
                        </group>
                        <group id="G2">
                            <primitive id="RG3" />
                            <primitive id="R4" />
                        </group>
                    </resources>
                """
        (
            self.config.runner.cib.load(
                resources=resources_before
            ).env.push_cib(resources=resources_after)
        )
        resource.group_add(self.env_assist.get_env(), "G2", ["RG3", "R4"])

    def test_move_from_existing_to_existing(self):
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
                            <primitive id="R2" />
                        </group>
                    </resources>
                """
        (
            self.config.runner.cib.load(
                resources=resources_before
            ).env.push_cib(resources=resources_after)
        )
        resource.group_add(self.env_assist.get_env(), "G", ["R3", "R1", "R2"])

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
        (
            self.config.runner.cib.load(
                resources=resources_before
            ).env.push_cib(resources=resources_after)
        )
        resource.group_add(
            self.env_assist.get_env(),
            "G",
            ["R3", "RGX", "R1"],
            adjacent_resource_id=adjacent_id,
            put_after_adjacent=after_adjacent,
        )

    def test_after_adjacent(self):
        self._assert_with_adjacent("RG1", True)

    def test_before_adjacent(self):
        self._assert_with_adjacent("RG2", False)

    def test_remove_empty_group(self):
        resources_before = """
            <resources>

                <group id="X">
                    <primitive id="RX1" />
                </group>
                <group id="Y">
                    <primitive id="RY1" />
                    <primitive id="RY2" />
                </group>
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
                </group>
            </resources>
        """
        (
            self.config.runner.cib.load(
                resources=resources_before
            ).env.push_cib(resources=resources_after)
        )
        resource.group_add(self.env_assist.get_env(), "G", ["RX1", "RY2"])

    def test_remove_empty_group_fail(self):
        constraints_before = """
            <constraints>
                <rsc_order first="X" first-action="start" 
                id="order-X-R1-mandatory" then="R1" 
                then-action="start"/>
            </constraints>
        """
        resources_before = """
            <resources>
                <primitive id="R1" />
                <group id="X">
                    <primitive id="RX1" />
                </group>
                <group id="Y">
                    <primitive id="RY1" />
                    <primitive id="RY2" />
                </group>
            </resources>
        """
        resources_after = """
            <resources>
                <primitive id="R1" />
                <group id="Y">
                    <primitive id="RY1" />
                </group>
                <group id="G">
                    <primitive id="RX1" />
                    <primitive id="RY2" />
                </group>
            </resources>
        """

        self.config.runner.cib.load(
            resources=resources_before, constraints=constraints_before
        ).env.push_cib(
            exception=LibraryError(
                ReportItem.error(
                    report_messages.CibPushError("stderr", "stdout")
                )
            ),
            resources=resources_after,
            constraints=constraints_before,
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["RX1", "RY2"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CANNOT_LEAVE_GROUP_EMPTY_AFTER_MOVE,
                    group_id="X",
                    inner_resource_ids=["RX1"],
                ),
            ]
        )

    def test_remove_empty_clone(self):
        resources_before = """
            <resources>
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
                <group id="G">
                    <primitive id="RC1" />
                    <primitive id="RM1" />
                </group>
            </resources>
        """
        (
            self.config.runner.cib.load(
                resources=resources_before
            ).env.push_cib(resources=resources_after)
        )
        resource.group_add(self.env_assist.get_env(), "G", ["RC1", "RM1"])

    def test_remove_empty_clone_fail(self):
        constraints_before = """
            <constraints>
                <rsc_order first="RM1-group-master" first-action="start" 
                id="order-RM1-group-master-R1-mandatory" then="R1" 
                then-action="start"/>
                <rsc_order first="RC1-group-clone" first-action="start" 
                id="order-RC1-group-clone-R1-mandatory" then="R2" 
                then-action="start"/>
            </constraints>
        """
        resources_before = """
            <resources>
                <primitive id="R1" />
                <primitive id="R2" />
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
                <primitive id="R1"></primitive>
                <primitive id="R2"></primitive>
                <group id="G">
                    <primitive id="RC1"></primitive>
                    <primitive id="RM1"></primitive>
                </group>
            </resources>
        """

        self.config.runner.cib.load(
            resources=resources_before, constraints=constraints_before
        ).env.push_cib(
            exception=LibraryError(
                ReportItem.error(
                    report_messages.CibPushError("stderr", "stdout")
                )
            ),
            resources=resources_after,
            constraints=constraints_before,
        )
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["RC1", "RM1"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CANNOT_LEAVE_GROUP_EMPTY_AFTER_MOVE,
                    group_id="RC1-group",
                    inner_resource_ids=["RC1"],
                ),
                fixture.error(
                    report_codes.CANNOT_LEAVE_GROUP_EMPTY_AFTER_MOVE,
                    group_id="RM1-group",
                    inner_resource_ids=["RM1"],
                ),
            ]
        )

    def test_validation(self):
        resources_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                </group>
                <primitive id="R1">
                    <meta_attributes id="R1-meta_attributes" />
                </primitive>
                <primitive id="R2">
                    <meta_attributes id="R2-meta_attributes" />
                </primitive>
                <clone id="RC1-clone">
                    <primitive id="RC1" />
                </clone>
            </resources>
        """
        (self.config.runner.cib.load(resources=resources_before))
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "R1-meta_attributes",
                ["R2", "R4", "R3", "R2-meta_attributes", "RC1-clone", "RC1"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R1-meta_attributes",
                    expected_types=["group"],
                    current_type="meta_attributes",
                ),
                fixture.report_not_found("R4", expected_types=[]),
                fixture.report_not_found("R3", expected_types=[]),
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R2-meta_attributes",
                    expected_types=["primitive"],
                    current_type="meta_attributes",
                ),
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1-clone",
                    resource_type="clone",
                    parent_id=None,
                    parent_type=None,
                ),
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1",
                    resource_type="primitive",
                    parent_id="RC1-clone",
                    parent_type="clone",
                ),
            ]
        )

    def test_validation_adjacent(self):
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
        (self.config.runner.cib.load(resources=resources_before))
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(
                self.env_assist.get_env(),
                "G",
                ["R1"],
                adjacent_resource_id="RX1",
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                    adjacent_item_id="RX1",
                ),
            ]
        )

    def test_validation_stonith_is_forbidden(self):
        resources_before = """
            <resources>
                <primitive id="S" class="stonith" />
                <group id="G">
                    <primitive id="RG1" />
                </group>
            </resources>
        """
        (self.config.runner.cib.load(resources=resources_before))
        self.env_assist.assert_raise_library_error(
            lambda: resource.group_add(self.env_assist.get_env(), "G", ["S"])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COMMAND_ARGUMENT_TYPE_MISMATCH,
                    not_accepted_type="stonith resources",
                    command_to_use_instead=None,
                ),
            ]
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
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
        (
            self.config.runner.cib.load(
                resources=resources_before
            ).env.push_cib(resources=resources_after, wait=self.timeout)
        )

    def test_group_running(self):
        resources_state = """
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
        """
        self.config.runner.pcmk.load_state(resources=resources_state)
        resource.group_add(
            self.env_assist.get_env(),
            "G",
            ["R1", "R2"],
            wait=self.timeout,
        )
        self.env_assist.assert_reports(
            [
                fixture.report_resource_running("G", {"Started": ["node1"]}),
                fixture.deprecation(report_codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

    def test_group_not_running(self):
        resources_state = """
            <resources>
                <group id="G" number_resources="2">
                    <resource id="R1" role="Started" nodes_running_on="1">
                         <node name="node1" id="1" cached="false" />
                     </resource>
                    <resource id="R2" role="Stopped" nodes_running_on="0">
                     </resource>
                </group>
            </resources>
        """
        self.config.runner.pcmk.load_state(resources=resources_state)
        resource.group_add(
            self.env_assist.get_env(),
            "G",
            ["R1", "R2"],
            wait=self.timeout,
        )
        self.env_assist.assert_reports(
            [
                fixture.report_resource_not_running("G"),
                fixture.deprecation(report_codes.RESOURCE_WAIT_DEPRECATED),
            ]
        )

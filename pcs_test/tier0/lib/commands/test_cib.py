from typing import Optional
from unittest import (
    TestCase,
    mock,
)

from pcs.common import reports
from pcs.common.resource_status import ResourceState
from pcs.lib.commands import cib as lib

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import (
    TmpFileCall,
    TmpFileMock,
)
from pcs_test.tools.fixture_cib import modify_cib
from pcs_test.tools.misc import read_test_resource


def _constraints(*argv):
    return f"<constraints>{''.join(argv)}</constraints>"


FIXTURE_LOC_CONSTRAINT_WITH_1_RULE = """
    <rsc_location id="lr1" rsc="A">
        <rule id="r1" boolean-op="and" score="100">
            <expression id="r1e1" operation="eq"
                attribute="#uname" value="node1"/>
            <date_expression id="r1e2" operation="gt"
                start="1970-01-01"/>
        </rule>
    </rsc_location>
"""

FIXTURE_LOC_CONSTRAINT_WITH_2_RULES = """
    <rsc_location id="lr2" rsc="B">
        <rule id="r2" score="-INFINITY" >
            <expression id="r2e1" attribute="pingd"
                operation="lt" value="3000"/>
        </rule>
        <rule id="r3" score-attribute="pingd" >
            <expression id="r3e1" attribute="pingd"
                operation="defined"/>
        </rule>
    </rsc_location>
"""

FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES = _constraints(
    FIXTURE_LOC_CONSTRAINT_WITH_1_RULE,
    FIXTURE_LOC_CONSTRAINT_WITH_2_RULES,
)

EXPECTED_TYPES_FOR_REMOVE = ["constraint", "location rule", "resource"]


def fixture_remote_resource(resource_id: str) -> str:
    return f'<primitive id="{resource_id}" class="ocf" type="remote" provider="pacemaker"/>'


def fixture_guest_resource(resource_id: str) -> str:
    return f"""
        <primitive id="{resource_id}" class="heartbeat" type="VirtualDomain">
            <meta_attributes id="meta">
                <nvpair id="meta-remote-node" name="remote-node" value="remote"/>
            </meta_attributes>
        </primitive>
    """


class StopResourcesWaitMixin:
    def fixture_init_tmp_file_mocker(self):
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

    def fixture_stop_resources_wait_calls(
        self,
        initial_cib: str,
        initial_state_modifiers: Optional[dict[str, str]] = None,
        after_disable_cib_modifiers: Optional[dict[str, str]] = None,
        after_disable_state_modifiers: Optional[dict[str, str]] = None,
        successful_stop: bool = True,
    ):
        self.config.runner.pcmk.load_state(
            name="stop_wait.load_state.before",
            **(initial_state_modifiers or {}),
        )

        self.__disabled_cib = modify_cib(
            initial_cib, **(after_disable_cib_modifiers or {})
        )
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall(
                    "stop_wait.cib.disable.before", orig_content=initial_cib
                ),
                TmpFileCall(
                    "stop_wait.cib.disable.after",
                    orig_content=self.__disabled_cib,
                ),
            ]
        )
        self.config.runner.cib.diff(
            "stop_wait.cib.disable.before",
            "stop_wait.cib.disable.after",
            name="stop_wait.cib.diff.disable",
            stdout="stop_wait.cib.diff.disable",
        )
        self.config.runner.cib.push_diff(
            name="stop_wait.cib.push.disable",
            cib_diff="stop_wait.cib.diff.disable",
        )

        self.config.runner.pcmk.wait(timeout=0)
        self.config.runner.pcmk.load_state(
            name="stop_wait.state.after",
            **(after_disable_state_modifiers or {}),
        )

        if successful_stop:
            self.config.runner.cib.load_content(
                self.__disabled_cib, name="stop_wait.cib.load.after"
            )

    def fixture_push_cib_after_stopping(self, **modifiers):
        self.tmp_file_mock_obj.extend_calls(
            [
                TmpFileCall(
                    "stop_wait.cib.delete.before",
                    orig_content=self.__disabled_cib,
                ),
                TmpFileCall(
                    "stop_wait.cib.delete.after",
                    orig_content=modify_cib(
                        read_test_resource("cib-empty.xml"), **modifiers
                    ),
                ),
            ]
        )

        self.config.runner.cib.diff(
            "stop_wait.cib.delete.before",
            "stop_wait.cib.delete.after",
            name="stop_wait.cib.diff.delete",
            stdout="stop_wait.cib.diff.delete",
        )

        self.config.runner.cib.push_diff(
            name="stop_wait.cib.push.delete",
            cib_diff="stop_wait.cib.diff.delete",
        )


class RemoveElements(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_ids_not_found_and_unsupported_types(self):
        self.config.runner.cib.load(
            tags="""
                <tags>
                    <tag id="T">
                        <obj_ref id="A"/>
                    </tag>
                </tags>
            """
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(), ["A", "T", "C"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found("A", expected_types=[]),
                fixture.report_not_found("C", expected_types=[]),
                fixture.report_unexpected_element(
                    "T", "tag", EXPECTED_TYPES_FOR_REMOVE
                ),
            ]
        )

    def test_duplicate_ids_specified(self):
        self.config.runner.cib.load(
            constraints="""
                <constraints>
                    <rsc_location id="l1" rsc="A" node="node1" score="200"/>
                    <rsc_location id="l2" rsc="A" node="node2" score="100"/>
                </constraints>
            """
        )
        self.config.env.push_cib(
            constraints="""
                <constraints>
                    <rsc_location id="l2" rsc="A" node="node2" score="100"/>
                </constraints>
            """
        )
        lib.remove_elements(self.env_assist.get_env(), ["l1", "l1"])

    def test_remove_constraints(self):
        self.config.runner.cib.load(
            constraints="""
                <constraints>
                    <rsc_location id="l1" rsc="A" node="node1" score="200"/>
                    <rsc_location id="l2" rsc="A" node="node2" score="100"/>
                    <rsc_order id="o1" first="A" then="B"/>
                    <rsc_order id="o2" first="A" then="B"/>
                    <rsc_colocation id="c1" rsc="A" with-rsc="B" score="100"/>
                    <rsc_colocation id="c2" rsc="A" with-rsc="B" score="100"/>
                    <rsc_ticket id="t1" ticket="T" rsc="A"/>
                    <rsc_ticket id="t2" ticket="T" rsc="B"/>
                </constraints>
            """
        )
        self.config.env.push_cib(
            constraints="""
                <constraints>
                    <rsc_location id="l2" rsc="A" node="node2" score="100"/>
                    <rsc_order id="o1" first="A" then="B"/>
                    <rsc_ticket id="t2" ticket="T" rsc="B"/>
                </constraints>
            """
        )
        lib.remove_elements(
            self.env_assist.get_env(), ["l1", "o2", "c1", "c2", "t1"]
        )

    def test_remove_location_rules(self):
        self.config.runner.cib.load(
            constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES
        )
        self.config.env.push_cib(constraints="<constraints/>")
        lib.remove_elements(self.env_assist.get_env(), ["r1", "r2", "r3"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_REMOVE_DEPENDANT_ELEMENTS,
                    id_tag_map={"lr1": "rsc_location", "lr2": "rsc_location"},
                ),
            ]
        )

    def test_remove_location_rule_expressions(self):
        self.config.runner.cib.load(
            constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(), ["r1e1", "r1e2"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_unexpected_element(
                    "r1e1", "expression", EXPECTED_TYPES_FOR_REMOVE
                ),
                fixture.report_unexpected_element(
                    "r1e2", "date_expression", EXPECTED_TYPES_FOR_REMOVE
                ),
            ]
        )

    def test_remove_resources(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="P-1"/>
                    <primitive id="P-2"/>
                    <group id="G">
                        <primitive id="G-1"/>
                        <primitive id="G-2"/>
                    </group>
                    <clone id="C">
                        <group id="C-G">
                            <primitive id="C-G-1"/>
                            <primitive id="C-G-2"/>
                        </group>
                    </clone>
                    <bundle id="B">
                        <primitive id="B-1"/>
                    </bundle>
                </resources>
            """
        )
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive id="P-2"/>
                </resources>
            """
        )
        lib.remove_elements(
            self.env_assist.get_env(),
            ["P-1", "G", "C", "B"],
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_REMOVE_DEPENDANT_ELEMENTS,
                    id_tag_map={
                        "G-1": "primitive",
                        "G-2": "primitive",
                        "C-G": "group",
                        "C-G-1": "primitive",
                        "C-G-2": "primitive",
                        "B-1": "primitive",
                    },
                ),
                fixture.warn(
                    reports.codes.STOPPING_RESOURCES_BEFORE_DELETING_SKIPPED
                ),
            ]
        )

    def test_remove_resource_guest(self):
        cib = modify_cib(
            read_test_resource("cib-empty.xml"),
            resources=f"""
                <resources>
                    {fixture_guest_resource("R1")}
                    <group id="G1">
                        {fixture_guest_resource("R2")}
                    </group>
                    <clone id="C1">
                        {fixture_guest_resource("R3")}
                    </clone>
                    <clone id="C2">
                        <group id="G2">
                            {fixture_guest_resource("R4")}
                        </group>
                    </clone>
                </resources>
            """,
        )
        self.config.runner.cib.load_content(cib)
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(), ["R1", "R2", "R3", "R4"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id="R1",
                ),
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id="R2",
                ),
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id="R3",
                ),
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id="R4",
                ),
            ]
        )

    def test_remove_resource_remote(self):
        cib = modify_cib(
            read_test_resource("cib-empty.xml"),
            resources=f"""
                <resources>
                    {fixture_remote_resource("R1")}
                    <group id="G1">
                        {fixture_remote_resource("R2")}
                    </group>
                    <clone id="C1">
                        {fixture_remote_resource("R3")}
                    </clone>
                    <clone id="C2">
                        <group id="G2">
                            {fixture_remote_resource("R4")}
                        </group>
                    </clone>
                </resources>
            """,
        )
        self.config.runner.cib.load_content(cib)
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(), ["R1", "R2", "R3", "R4"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_REMOTE,
                    resource_id="R1",
                ),
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_REMOTE,
                    resource_id="R2",
                ),
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_REMOTE,
                    resource_id="R3",
                ),
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_REMOTE,
                    resource_id="R4",
                ),
            ]
        )

    def test_remove_resource_multiple_dependencies(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_location id="L1" rsc="A" node="node1" score="200"/>
                    <rsc_location id="L2" rsc="B" node="node1" score="200"/>
                    <rsc_colocation score="-1" id="C">
                        <resource_set role="Started" id="SET">
                            <resource_ref id="A"/>
                            <resource_ref id="B"/>
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """,
            tags="""
                <tags>
                    <tag id="T">
                        <obj_ref id="A"/>
                        <obj_ref id="B"/>
                    </tag>
                </tags>
            """,
            fencing_topology="""
                <fencing-topology>
                    <fencing-level index="1" devices="A" target="NODE-A" id="FL"/>
                </fencing-topology>
            """,
            optional_in_conf="""
                <acls>
                    <acl_role id="ROLE">
                        <acl_permission id="PERMISSION" kind="read" reference="A"/>
                    </acl_role>
                    <acl_target id="TARGET">
                        <role id="ROLE"/>
                    </acl_target>
                </acls>
            """,
        )
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive id="B"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_location id="L2" rsc="B" node="node1" score="200"/>
                    <rsc_colocation score="-1" id="C">
                        <resource_set role="Started" id="SET">
                            <resource_ref id="B"/>
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """,
            tags="""
                <tags>
                    <tag id="T">
                        <obj_ref id="B"/>
                    </tag>
                </tags>
            """,
            fencing_topology="<fencing-topology/>",
            optional_in_conf="""
                <acls>
                    <acl_role id="ROLE">
                    </acl_role>
                    <acl_target id="TARGET">
                        <role id="ROLE"/>
                    </acl_target>
                </acls>
            """,
        )
        lib.remove_elements(
            self.env_assist.get_env(), ["A"], [reports.codes.FORCE]
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_REMOVE_DEPENDANT_ELEMENTS,
                    id_tag_map={
                        "L1": "rsc_location",
                        "FL": "fencing-level",
                        "PERMISSION": "acl_permission",
                    },
                ),
                fixture.info(
                    reports.codes.CIB_REMOVE_REFERENCES,
                    id_tag_map={
                        "A": "primitive",
                        "T": "tag",
                        "PERMISSION": "acl_permission",
                        "ROLE": "acl_role",
                        "SET": "resource_set",
                    },
                    removing_references_from={
                        "A": {"T", "SET"},
                        "PERMISSION": {"ROLE"},
                    },
                ),
                fixture.warn(
                    reports.codes.STOPPING_RESOURCES_BEFORE_DELETING_SKIPPED
                ),
            ]
        )


class RemoveElementsStopResources(TestCase, StopResourcesWaitMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.fixture_init_tmp_file_mocker()

    def test_one_resource(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """
        )
        self.fixture_stop_resources_wait_calls(
            self.config.calls.get("runner.cib.load").stdout,
            initial_state_modifiers={
                "resources": """
                    <resources>
                        <resource id="A" managed="true" role="Started"/>
                    </resources>
                """
            },
            after_disable_cib_modifiers={
                "resources": """
                    <resources>
                        <primitive id="A">
                            <meta_attributes id="A-meta_attributes">
                                <nvpair id="A-meta_attributes-target-role" name="target-role" value="Stopped"/>
                            </meta_attributes>
                        </primitive>
                    </resources>
                """
            },
            after_disable_state_modifiers={
                "resources": """
                    <resources>
                        <resource id="A" managed="true" role="Stopped"/>
                    </resources>
                """
            },
        )
        self.fixture_push_cib_after_stopping(resources="<resources/>")

        lib.remove_elements(self.env_assist.get_env(), ["A"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES_BEFORE_DELETING,
                    resource_id_list=["A"],
                ),
                fixture.info(reports.codes.WAIT_FOR_IDLE_STARTED, timeout=0),
            ]
        )

    def test_resource_unmanaged(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """
        )
        self.fixture_stop_resources_wait_calls(
            self.config.calls.get("runner.cib.load").stdout,
            initial_state_modifiers={
                "resources": """
                    <resources>
                        <resource id="A" managed="false" role="Stopped"/>
                    </resources>
                """
            },
            after_disable_cib_modifiers={
                "resources": """
                    <resources>
                        <primitive id="A">
                            <meta_attributes id="A-meta_attributes">
                                <nvpair id="A-meta_attributes-target-role" name="target-role" value="Stopped"/>
                            </meta_attributes>
                        </primitive>
                    </resources>
                """
            },
            after_disable_state_modifiers={
                "resources": """
                    <resources>
                        <resource id="A" managed="false" role="Stopped"/>
                    </resources>
                """
            },
        )
        self.fixture_push_cib_after_stopping(resources="<resources/>")

        lib.remove_elements(self.env_assist.get_env(), ["A"])
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_IS_UNMANAGED, resource_id="A"
                ),
                fixture.info(
                    reports.codes.STOPPING_RESOURCES_BEFORE_DELETING,
                    resource_id_list=["A"],
                ),
                fixture.info(reports.codes.WAIT_FOR_IDLE_STARTED, timeout=0),
            ]
        )

    def test_resource_remove_failed_to_stop(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """
        )
        self.fixture_stop_resources_wait_calls(
            self.config.calls.get("runner.cib.load").stdout,
            initial_state_modifiers={
                "resources": """
                    <resources>
                        <resource id="A" managed="true" role="Started"/>
                    </resources>
                """
            },
            after_disable_cib_modifiers={
                "resources": """
                    <resources>
                        <primitive id="A">
                            <meta_attributes id="A-meta_attributes">
                                <nvpair id="A-meta_attributes-target-role" name="target-role" value="Stopped"/>
                            </meta_attributes>
                        </primitive>
                    </resources>
                """
            },
            after_disable_state_modifiers={
                "resources": """
                    <resources>
                        <resource id="A" managed="true" role="Started"/>
                    </resources>
                """
            },
            successful_stop=False,
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(self.env_assist.get_env(), ["A"])
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES_BEFORE_DELETING,
                    resource_id_list=["A"],
                ),
                fixture.info(reports.codes.WAIT_FOR_IDLE_STARTED, timeout=0),
                fixture.error(
                    reports.codes.CANNOT_STOP_RESOURCES_BEFORE_DELETING,
                    resource_id_list=["A"],
                    force_code=reports.codes.FORCE,
                ),
            ]
        )

    def test_disable_only_resources(self):
        constraints = """
            <constraints>
                <rsc_location id="L" rsc="A" node="node2" score="200"/>
            </constraints>
        """
        tags = """
            <tags>
                <tag id="T">
                    <obj_ref id="A"/>
                </tag>
            </tags>
        """
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """,
            constraints=constraints,
            tags=tags,
        )
        self.fixture_stop_resources_wait_calls(
            self.config.calls.get("runner.cib.load").stdout,
            initial_state_modifiers={
                "resources": """
                    <resources>
                        <resource id="A" managed="true" role="Stopped"/>
                    </resources>
                """
            },
            after_disable_cib_modifiers={
                "resources": """
                    <resources>
                        <primitive id="A">
                            <meta_attributes id="A-meta_attributes">
                                <nvpair id="A-meta_attributes-target-role" name="target-role" value="Stopped"/>
                            </meta_attributes>
                        </primitive>
                    </resources>
                """,
                "constraints": constraints,
                "tags": tags,
            },
            after_disable_state_modifiers={
                "resources": """
                    <resources>
                        <resource id="A" managed="true" role="Stopped"/>
                    </resources>
                """
            },
        )
        self.fixture_push_cib_after_stopping(
            resources="<resources/>",
            constraints="<constraints/>",
            tags="<tags/>",
        )

        lib.remove_elements(self.env_assist.get_env(), ["A"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES_BEFORE_DELETING,
                    resource_id_list=["A"],
                ),
                fixture.info(reports.codes.WAIT_FOR_IDLE_STARTED, timeout=0),
                fixture.info(
                    reports.codes.CIB_REMOVE_DEPENDANT_ELEMENTS,
                    id_tag_map={"L": "rsc_location", "T": "tag"},
                ),
            ]
        )

    def test_stop_inner_elements(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <clone id="C">
                        <group id="G">
                            <primitive id="A"/>
                            <primitive id="B"/>
                        </group>
                    </clone>
                </resources>
            """
        )
        self.fixture_stop_resources_wait_calls(
            self.config.calls.get("runner.cib.load").stdout,
            initial_state_modifiers={
                "resources": """
                    <resources>
                        <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                            <group id="G:0" number_resources="1" maintenance="false" managed="true" disabled="false">
                                <resource id="A" role="Started" managed="true"/>
                                <resource id="B" role="Started" managed="true"/>
                            </group>
                            <group id="G:1" number_resources="2" maintenance="false" managed="true" disabled="false">
                                <resource id="A" role="Started" managed="true"/>
                                <resource id="B" role="Started" managed="true"/>
                            </group>
                        </clone>
                    </resources>
                """
            },
            after_disable_cib_modifiers={
                "resources": """
                    <resources>
                        <clone id="C">
                            <meta_attributes id="C-meta_attributes">
                                <nvpair id="C-meta_attributes-target-role" name="target-role" value="Stopped"/>
                            </meta_attributes>
                            <group id="G">
                                <meta_attributes id="G-meta_attributes">
                                    <nvpair id="G-meta_attributes-target-role" name="target-role" value="Stopped"/>
                                </meta_attributes>
                                <primitive id="A">
                                    <meta_attributes id="A-meta_attributes">
                                        <nvpair id="A-meta_attributes-target-role" name="target-role" value="Stopped"/>
                                    </meta_attributes>
                                </primitive>
                                <primitive id="B">
                                    <meta_attributes id="B-meta_attributes">
                                        <nvpair id="B-meta_attributes-target-role" name="target-role" value="Stopped"/>
                                    </meta_attributes>
                                </primitive>
                            </group>
                        </clone>
                    </resources>
                """
            },
            after_disable_state_modifiers={
                "resources": """
                    <resources>
                        <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                            <group id="G:0" number_resources="1" maintenance="false" managed="true" disabled="false">
                                <resource id="A" role="Stopped" managed="true"/>
                                <resource id="B" role="Stopped" managed="true"/>
                            </group>
                            <group id="G:1" number_resources="2" maintenance="false" managed="true" disabled="false">
                                <resource id="A" role="Stopped" managed="true"/>
                                <resource id="B" role="Stopped" managed="true"/>
                            </group>
                        </clone>
                    </resources>
                """
            },
        )
        self.fixture_push_cib_after_stopping(resources="<resources/>")

        lib.remove_elements(self.env_assist.get_env(), ["C"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES_BEFORE_DELETING,
                    resource_id_list=["A", "B", "C", "G"],
                ),
                fixture.info(reports.codes.WAIT_FOR_IDLE_STARTED, timeout=0),
                fixture.info(
                    reports.codes.CIB_REMOVE_DEPENDANT_ELEMENTS,
                    id_tag_map={
                        "G": "group",
                        "A": "primitive",
                        "B": "primitive",
                    },
                ),
            ]
        )

    def test_disable_only_needed_resources(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <clone id="C">
                        <group id="G">
                            <primitive id="A"/>
                            <primitive id="B"/>
                        </group>
                    </clone>
                </resources>
            """
        )
        self.fixture_stop_resources_wait_calls(
            self.config.calls.get("runner.cib.load").stdout,
            initial_state_modifiers={
                "resources": """
                    <resources>
                        <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                            <group id="G:0" number_resources="1" maintenance="false" managed="true" disabled="false">
                                <resource id="A" role="Started" managed="true"/>
                                <resource id="B" role="Started" managed="true"/>
                            </group>
                            <group id="G:1" number_resources="2" maintenance="false" managed="true" disabled="false">
                                <resource id="A" role="Started" managed="true"/>
                                <resource id="B" role="Started" managed="true"/>
                            </group>
                        </clone>
                    </resources>
                """
            },
            after_disable_cib_modifiers={
                "resources": """
                    <resources>
                        <clone id="C">
                            <group id="G">
                                <primitive id="A">
                                    <meta_attributes id="A-meta_attributes">
                                        <nvpair id="A-meta_attributes-target-role" name="target-role" value="Stopped"/>
                                    </meta_attributes>
                                </primitive>
                                <primitive id="B"/>
                            </group>
                        </clone>
                    </resources>
                """
            },
            after_disable_state_modifiers={
                "resources": """
                    <resources>
                        <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                            <group id="G:0" number_resources="1" maintenance="false" managed="true" disabled="false">
                                <resource id="A" role="Stopped" managed="true"/>
                                <resource id="B" role="Started" managed="true"/>
                            </group>
                            <group id="G:1" number_resources="2" maintenance="false" managed="true" disabled="false">
                                <resource id="A" role="Stopped" managed="true"/>
                                <resource id="B" role="Started" managed="true"/>
                            </group>
                        </clone>
                    </resources>
                """
            },
        )
        self.fixture_push_cib_after_stopping(
            resources="""
                <resources>
                    <clone id="C">
                        <group id="G">
                            <primitive id="B"/>
                        </group>
                    </clone>
                </resources>
            """
        )

        lib.remove_elements(self.env_assist.get_env(), ["A"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES_BEFORE_DELETING,
                    resource_id_list=["A"],
                ),
                fixture.info(reports.codes.WAIT_FOR_IDLE_STARTED, timeout=0),
                fixture.info(
                    reports.codes.CIB_REMOVE_REFERENCES,
                    id_tag_map={"A": "primitive", "G": "group"},
                    removing_references_from={"A": {"G"}},
                ),
            ]
        )

    def test_skip_state_check_on_missing_from_status(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <bundle id="test-bundle">
                        <podman image="localhost/pcmktest:test"/>
                        <primitive id="apa" class="ocf" type="apache" provider="heartbeat"/>
                    </bundle>
                </resources>
            """
        )
        self.fixture_stop_resources_wait_calls(
            self.config.calls.get("runner.cib.load").stdout,
            initial_state_modifiers={"resources": "<resources/>"},
            after_disable_cib_modifiers={
                "resources": """
                    <resources>
                        <bundle id="test-bundle">
                            <podman image="localhost/pcmktest:test"/>
                            <primitive id="apa" class="ocf" type="apache" provider="heartbeat">
                                <meta_attributes id="apa-meta_attributes">
                                    <nvpair id="apa-meta_attributes-target-role" name="target-role" value="Stopped"/>
                                </meta_attributes>
                            </primitive>
                        </bundle>
                    </resources>
                """
            },
            after_disable_state_modifiers={"resources": "<resources/>"},
        )
        self.fixture_push_cib_after_stopping(
            resources="""
                <resources>
                    <bundle id="test-bundle">
                        <podman image="localhost/pcmktest:test"/>
                    </bundle>
                </resources>
            """
        )
        lib.remove_elements(self.env_assist.get_env(), ["apa"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES_BEFORE_DELETING,
                    resource_id_list=["apa"],
                ),
                fixture.debug(
                    reports.codes.CONFIGURED_RESOURCE_MISSING_IN_STATUS,
                    resource_id="apa",
                    checked_state=ResourceState.UNMANAGED,
                ),
                fixture.info(reports.codes.WAIT_FOR_IDLE_STARTED, timeout=0),
                fixture.debug(
                    reports.codes.CONFIGURED_RESOURCE_MISSING_IN_STATUS,
                    resource_id="apa",
                    checked_state=ResourceState.STOPPED,
                ),
                fixture.info(
                    reports.codes.CIB_REMOVE_REFERENCES,
                    id_tag_map={"apa": "primitive", "test-bundle": "bundle"},
                    removing_references_from={"apa": {"test-bundle"}},
                ),
            ]
        )

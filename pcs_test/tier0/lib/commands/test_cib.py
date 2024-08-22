from unittest import (
    TestCase,
    mock,
)

from pcs.common import reports
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
                fixture.report_not_found(
                    "A", expected_types=["configuration element"]
                ),
                fixture.report_not_found(
                    "C", expected_types=["configuration element"]
                ),
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
                )
            ]
        )

    def test_remove_resource_guest(self):
        self.config.runner.cib.load(filename="cib-largefile.xml")
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(), ["container1"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id="container1",
                )
            ]
        )

    def test_remove_resource_remote(self):
        self.config.runner.cib.load(filename="cib-remote.xml")
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(), ["rh93-remote"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.USE_COMMAND_NODE_REMOVE_REMOTE,
                    resource_id="rh93-remote",
                )
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
            ]
        )


class RemoveElementsStopResources(TestCase):
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

    def fixture_env(
        self,
        initial_cib_modifiers: dict[str, str],
        initial_state_modifiers: dict[str, str],
        after_disable_cib_modifiers: dict[str, str],
        after_disable_state_modifiers: dict[str, str],
        after_delete_cib_modifiers: dict[str, str],
        successful_stop=True,
    ):

        self.config.runner.cib.load(
            name="load.disable", **initial_cib_modifiers
        )
        self.config.runner.pcmk.load_state(
            name="state.disable", **initial_state_modifiers
        )
        self.config.runner.cib.diff(
            "cib.disable.before",
            "cib.disable.after",
            name="diff.disable",
            stdout="diff_disable",
        )
        self.config.runner.cib.push_diff(
            name="push.disable", cib_diff="diff_disable"
        )

        original_cib = self.config.calls.get("load.disable").stdout
        after_disable_cib = modify_cib(
            original_cib, **after_disable_cib_modifiers
        )

        self.config.runner.pcmk.wait(timeout=0)
        self.config.runner.pcmk.load_state(
            name="state.delete", **after_disable_state_modifiers
        )

        mock_files = [
            TmpFileCall(
                "cib.disable.before",
                orig_content=self.config.calls.get("load.disable").stdout,
            ),
            TmpFileCall(
                "cib.disable.after",
                orig_content=after_disable_cib,
            ),
        ]

        if successful_stop:
            self.config.runner.cib.load(
                name="load.delete", **after_disable_cib_modifiers
            )
            self.config.runner.cib.diff(
                "cib.delete.before",
                "cib.delete.after",
                name="diff.delete",
                stdout="diff_delete",
            )

            self.config.runner.cib.push_diff(
                name="push.delete", cib_diff="diff_delete"
            )

            mock_files.extend(
                [
                    TmpFileCall(
                        "cib.delete.before", orig_content=after_disable_cib
                    ),
                    TmpFileCall(
                        "cib.delete.after",
                        orig_content=modify_cib(
                            read_test_resource("cib-empty.xml"),
                            **after_delete_cib_modifiers,
                        ),
                    ),
                ]
            )

        self.tmp_file_mock_obj.set_calls(mock_files)

    def test_one_resource(self):
        self.fixture_env(
            initial_cib_modifiers={
                "resources": """
                    <resources>
                        <primitive id="A"/>
                    </resources>
                """
            },
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
            after_delete_cib_modifiers={"resources": "<resources/>"},
        )

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
        self.fixture_env(
            initial_cib_modifiers={
                "resources": """
                    <resources>
                        <primitive id="A"/>
                    </resources>
                """
            },
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
            after_delete_cib_modifiers={"resources": "<resources/>"},
        )

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
        self.fixture_env(
            initial_cib_modifiers={
                "resources": """
                    <resources>
                        <primitive id="A"/>
                    </resources>
                """
            },
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
            after_delete_cib_modifiers={},
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

        self.fixture_env(
            initial_cib_modifiers={
                "resources": """
                    <resources>
                        <primitive id="A"/>
                    </resources>
                """,
                "constraints": constraints,
                "tags": tags,
            },
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
            after_delete_cib_modifiers={
                "resources": "<resources/>",
                "constraints": "<constraints/>",
                "tags": "<tags/>",
            },
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

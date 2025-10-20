import json
from unittest import TestCase, mock

from pcs import settings
from pcs.common import reports
from pcs.lib.cib.description import TAG_LIST_SUPPORTS_DESCRIPTION
from pcs.lib.commands import cib as lib

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.fixture_cib import modify_cib
from pcs_test.tools.misc import get_test_resource as rc
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


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_rng/api/api-result.rng")
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
                </resources>
            """
        )
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <resource id="P-1" managed="true" role="Stopped"/>
                    <group id="G" number_resources="2" maintenance="false" managed="true" disabled="false">
                        <resource id="G-1" managed="true" role="Stopped"/>
                        <resource id="G-2" managed="true" role="Stopped"/>
                    </group>
                    <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                        <group id="C-G" number_resources="2" maintenance="false" managed="true" disabled="false">
                            <resource id="C-G-1" managed="true" role="Stopped"/>
                            <resource id="C-G-2" managed="true" role="Stopped"/>
                        </group>
                    </clone>
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
            ["P-1", "G", "C"],
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
                    },
                )
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
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <resource id="R1" managed="true" role="Stopped"/>
                    <group id="G1" number_resources="1" maintenance="false" managed="true" disabled="false">
                        <resource id="R2" managed="true" role="Stopped"/>
                    </group>
                    <clone id="C1" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                        <resource id="R3" managed="true" role="Stopped"/>
                    </clone>
                    <clone id="C1" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                        <group id="G2" number_resources="1" maintenance="false" managed="true" disabled="false">
                            <resource id="R4" managed="true" role="Stopped"/>
                        </group>
                    </clone>
                </resources>
            """
        )
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
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <resource id="R1" managed="true" role="Stopped"/>
                    <group id="G1" number_resources="1" maintenance="false" managed="true" disabled="false">
                        <resource id="R2" managed="true" role="Stopped"/>
                    </group>
                    <clone id="C1" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                        <resource id="R3" managed="true" role="Stopped"/>
                    </clone>
                    <clone id="C1" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                        <group id="G2" number_resources="1" maintenance="false" managed="true" disabled="false">
                            <resource id="R4" managed="true" role="Stopped"/>
                        </group>
                    </clone>
                </resources>
            """
        )
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
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <resource id="A" role="Stopped" managed="true"/>
                    <resource id="B" role="Stopped" managed="true"/>
                </resources>
            """
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
        lib.remove_elements(self.env_assist.get_env(), ["A"])
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

    def test_remove_resources_started(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="P-1"/>
                    <primitive id="P-2"/>
                </resources>
            """
        )
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <resource id="P-1" role="Started"/>
                    <resource id="P-2" role="Stopped"/>
                </resources>
            """
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(), ["P-1", "P-2"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CANNOT_REMOVE_RESOURCES_NOT_STOPPED,
                    resource_id_list=["P-1"],
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_remove_resources_started_forced(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="P-1"/>
                    <primitive id="P-2"/>
                </resources>
            """
        )
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <resource id="P-1" role="Started"/>
                    <resource id="P-2" role="Stopped"/>
                </resources>
            """
        )
        self.config.env.push_cib(resources="<resources />")

        lib.remove_elements(
            self.env_assist.get_env(), ["P-1", "P-2"], [reports.codes.FORCE]
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.CANNOT_REMOVE_RESOURCES_NOT_STOPPED,
                    resource_id_list=["P-1"],
                )
            ]
        )

    def test_remove_resources_stonith_state_check_skipped(self):
        # adding extra stonith, so the last stonith check passes
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="P-1"/>
                    <primitive class="stonith" id="S-1" type="fence_xvm"/>
                    <primitive class="stonith" id="S-2" type="fence_xvm"/>
                </resources>
            """
        )
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <resource id="P-1" role="Stopped"/>
                    <resource id="S-1" role="Started"/>
                </resources>
            """
        )
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive class="stonith" id="S-2" type="fence_xvm"/>
                </resources>
            """
        )

        lib.remove_elements(self.env_assist.get_env(), ["P-1", "S-1"])

    def test_remove_resources_not_live_cib(self):
        cib = modify_cib(
            read_test_resource("cib-empty.xml"),
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """,
        )
        # This makes env.is_cib_live return False
        self.config.env.set_cib_data(cib)
        self.config.runner.cib.load_content(
            cib, env={"CIB_file": "/fake/tmp/file"}
        )
        self.config.env.push_cib(
            resources="<resources/>", load_key="runner.cib.load_content"
        )

        lib.remove_elements(self.env_assist.get_env(), ["A"])
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STOPPED_RESOURCES_BEFORE_DELETE_CHECK_SKIPPED,
                    resource_id_list=["A"],
                    reason_type=reports.const.REASON_NOT_LIVE_CIB,
                )
            ]
        )


class StonithAndSbdCheck(TestCase):
    """
    Test that an error is produced when removing the last stonith resource and
    sbd is disabled
    """

    resources = """
        <resources>
            <primitive id="S1" class="stonith" type="fence_any" />
            <primitive id="S2" class="stonith" type="fence_any" />
        </resources>
    """

    def fixture_config_sbd_calls(self, sbd_enabled):
        node_name_list = ["node-1", "node-2"]
        self.config.env.set_known_nodes(node_name_list)
        self.config.corosync_conf.load(node_name_list=node_name_list)
        self.config.http.sbd.check_sbd(
            communication_list=[
                dict(
                    label=node,
                    param_list=[("watchdog", ""), ("device_list", "[]")],
                    output=json.dumps(
                        dict(
                            sbd=dict(
                                installed=True,
                                enabled=sbd_enabled,
                                running=sbd_enabled,
                            )
                        )
                    ),
                )
                for node in node_name_list
            ]
        )

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_some_stonith_left(self):
        # sbd calls do not happen if some stonith is left
        self.config.runner.cib.load(resources=self.resources)
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive id="S2" class="stonith" type="fence_any" />
                </resources>
            """
        )

        lib.remove_elements(self.env_assist.get_env(), ["S1"])
        self.env_assist.assert_reports([])

    def test_no_stonith_left_sbd_enabled(self):
        self.config.runner.cib.load(resources=self.resources)
        self.fixture_config_sbd_calls(sbd_enabled=True)
        self.config.env.push_cib(resources="<resources />")

        lib.remove_elements(self.env_assist.get_env(), ["S1", "S2"])
        self.env_assist.assert_reports([])

    def test_fake_stonith_left_sbd_disabled(self):
        resources = """
            <resources>
                <primitive id="S1" class="stonith" type="fence_any" />
                <primitive id="S2" class="stonith" type="fence_sbd" />
            </resources>
        """
        self.config.runner.cib.load(resources=resources)
        self.fixture_config_sbd_calls(sbd_enabled=False)

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(self.env_assist.get_env(), ["S1"])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT,
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_disabled_stonith_left_sbd_disabled(self):
        resources = """
            <resources>
                <primitive id="S1" class="stonith" type="fence_any">
                    <meta_attributes>
                        <nvpair name="target-role" value="stopped" />
                    </meta_attributes>
                </primitive>
                <primitive id="S2" class="stonith" type="fence_any" />
            </resources>
        """
        self.config.runner.cib.load(resources=resources)
        self.fixture_config_sbd_calls(sbd_enabled=False)

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(self.env_assist.get_env(), ["S2"])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT,
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_stonith_was_already_noneffective_and_sbd_disabled(self):
        resources = """
            <resources>
                <primitive id="S1" class="stonith" type="fence_any">
                    <meta_attributes id="S1-meta_attributes">
                        <nvpair id="S1-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                </primitive>
                <primitive id="S2" class="stonith" type="fence_sbd" />
            </resources>
        """
        self.config.runner.cib.load(resources=resources)
        self.fixture_config_sbd_calls(sbd_enabled=False)
        self.config.env.push_cib(resources="<resources />")

        lib.remove_elements(self.env_assist.get_env(), ["S1", "S2"])
        self.env_assist.assert_reports([])

    def test_no_stonith_left_sbd_disabled(self):
        self.config.runner.cib.load(resources=self.resources)
        self.fixture_config_sbd_calls(sbd_enabled=False)

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(self.env_assist.get_env(), ["S1", "S2"])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT,
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_no_stonith_left_sbd_disabled_forced(self):
        self.config.runner.cib.load(resources=self.resources)
        self.fixture_config_sbd_calls(sbd_enabled=False)
        self.config.env.push_cib(resources="<resources />")

        lib.remove_elements(
            self.env_assist.get_env(), ["S1", "S2"], {reports.codes.FORCE}
        )

        self.env_assist.assert_reports(
            [fixture.warn(reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT)]
        )

    def test_no_stonith_left_sbd_partially_enabled(self):
        node_name_list = ["node-1", "node-2"]
        self.config.env.set_known_nodes(node_name_list)
        self.config.runner.cib.load(resources=self.resources)
        self.config.corosync_conf.load(node_name_list=node_name_list)
        self.config.http.sbd.check_sbd(
            communication_list=[
                dict(
                    label="node-1",
                    param_list=[("watchdog", ""), ("device_list", "[]")],
                    output=json.dumps(
                        dict(
                            sbd=dict(installed=True, enabled=True, running=True)
                        )
                    ),
                ),
                dict(
                    label="node-2",
                    param_list=[("watchdog", ""), ("device_list", "[]")],
                    output=json.dumps(
                        dict(
                            sbd=dict(
                                installed=True, enabled=False, running=False
                            )
                        )
                    ),
                ),
            ]
        )
        self.config.env.push_cib(resources="<resources />")

        lib.remove_elements(self.env_assist.get_env(), ["S1", "S2"])
        self.env_assist.assert_reports([])

    def test_communication_error(self):
        self.config.runner.cib.load(resources=self.resources)
        node_name_list = ["node-1", "node-2"]
        self.config.env.set_known_nodes(node_name_list)
        self.config.corosync_conf.load(node_name_list=node_name_list)
        self.config.http.sbd.check_sbd(
            communication_list=[
                dict(
                    label="node-1",
                    param_list=[("watchdog", ""), ("device_list", "[]")],
                    output=json.dumps(
                        dict(
                            sbd=dict(installed=True, enabled=True, running=True)
                        )
                    ),
                ),
                dict(
                    label="node-2",
                    param_list=[("watchdog", ""), ("device_list", "[]")],
                    was_connected=False,
                ),
            ]
        )
        self.config.env.push_cib(resources="<resources />")

        lib.remove_elements(self.env_assist.get_env(), ["S1", "S2"])
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="node-2",
                    command="remote/check_sbd",
                    reason=None,
                ),
                fixture.warn(
                    reports.codes.UNABLE_TO_GET_SBD_STATUS,
                    node="node-2",
                    reason="",
                ),
            ]
        )


class ElementDescriptionSet(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.new_description = "I am a stick."
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B" description="I am a description"/>
                </resources>
            """
        )

    def test_success_add_description(self):
        self.config.env.push_cib(
            resources=f"""
                <resources>
                    <primitive id="A" description="{self.new_description}"/>
                    <primitive id="B" description="I am a description"/>
                </resources>
            """
        )
        lib.element_description_set(
            self.env_assist.get_env(), "A", self.new_description
        )

    def test_success_update_description(self):
        self.config.env.push_cib(
            resources=f"""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B" description="{self.new_description}"/>
                </resources>
            """
        )
        lib.element_description_set(
            self.env_assist.get_env(), "B", self.new_description
        )

    def test_success_remove_description(self):
        self.config.env.push_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                </resources>
            """
        )
        lib.element_description_set(self.env_assist.get_env(), "B", "")

    def test_element_does_not_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: lib.element_description_set(
                self.env_assist.get_env(), "C", self.new_description
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="C",
                    expected_types=sorted(TAG_LIST_SUPPORTS_DESCRIPTION),
                    context_type="",
                    context_id="",
                )
            ]
        )

    def test_element_does_not_support_description(self):
        self.config.runner.cib.load(
            instead="runner.cib.load",
            constraints="""
                <constraints>
                    <rsc_location id="L1" rsc="A" node="node1" score="200"/>
                </constraints>
            """,
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.element_description_set(
                self.env_assist.get_env(), "L1", self.new_description
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="L1",
                    expected_types=sorted(TAG_LIST_SUPPORTS_DESCRIPTION),
                    current_type="rsc_location",
                ),
            ]
        )


class ElementDescriptionGet(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.description = "I am a stick."
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    <primitive id="A" description="{self.description}"/>
                    <primitive id="B"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_location id="L1" rsc="A" node="node1" score="200"/>
                </constraints>
            """,
        )

    def test_success_return_description(self):
        result = lib.element_description_get(self.env_assist.get_env(), "A")
        self.assertEqual(result, self.description)

    def test_success_no_description(self):
        result = lib.element_description_get(self.env_assist.get_env(), "B")
        self.assertEqual(result, "")

    def test_element_does_not_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: lib.element_description_get(self.env_assist.get_env(), "C")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="C",
                    expected_types=sorted(TAG_LIST_SUPPORTS_DESCRIPTION),
                    context_type="",
                    context_id="",
                )
            ]
        )

    def test_element_does_not_support_description(self):
        self.env_assist.assert_raise_library_error(
            lambda: lib.element_description_get(self.env_assist.get_env(), "L1")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="L1",
                    expected_types=sorted(TAG_LIST_SUPPORTS_DESCRIPTION),
                    current_type="rsc_location",
                ),
            ]
        )

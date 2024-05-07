from unittest import TestCase

from pcs.common.pacemaker.resource.relations import ResourceRelationType
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import resource

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


def fixture_primitive(_id, members):
    return dict(
        id=_id,
        type=ResourceRelationType.RSC_PRIMITIVE,
        metadata={
            "id": _id,
            "class": "ocf",
            "provider": "pacemaker",
            "type": "Dummy",
        },
        members=members,
    )


def fixture_primitive_xml(_id):
    return f"""
        <primitive id="{_id}" class="ocf" provider="pacemaker" type="Dummy"/>
    """


def fixture_node(entity, members=None, leaf=False):
    return dict(
        relation_entity=entity,
        is_leaf=leaf,
        members=members or [],
    )


def fixture_order(res1, res2, kind="Mandatory", score=None):
    _id = f"order-{res1}-{res2}"
    out = dict(
        id=_id,
        type=ResourceRelationType.ORDER,
        members=[res1, res2],
        metadata={
            "id": _id,
            "first": res1,
            "first-action": "start",
            "then": res2,
            "then-action": "start",
            "kind": kind,
        },
    )
    if score:
        out["metadata"]["score"] = score
    return out


class GetResourceRelationsTree(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_not_existing_resource(self):
        self.config.runner.cib.load()
        resource_id = "not_existing"
        self.env_assist.assert_raise_library_error(
            lambda: resource.get_resource_relations_tree(
                self.env_assist.get_env(),
                resource_id,
            ),
            [
                fixture.report_not_found(
                    resource_id, expected_types=["resource"]
                )
            ],
            expected_in_processor=False,
        )

    def test_validation_stonith_is_forbidden(self):
        self.config.runner.cib.load(
            resources="""
                <resources><primitive id="S" class="stonith" /></resources>
            """
        )
        resource_id = "S"
        self.env_assist.assert_raise_library_error(
            lambda: resource.get_resource_relations_tree(
                self.env_assist.get_env(),
                resource_id,
            ),
            [
                fixture.error(
                    report_codes.COMMAND_ARGUMENT_TYPE_MISMATCH,
                    not_accepted_type="stonith resource",
                    command_to_use_instead=None,
                )
            ],
            expected_in_processor=False,
        )

    def test_simple(self):
        self.config.runner.cib.load(
            resources="<resources>{}</resources>".format(
                fixture_primitive_xml("d1") + fixture_primitive_xml("d2")
            ),
            constraints="""
            <constraints>
                <rsc_order first="d1" first-action="start"
                    id="order-d1-d2" then="d2" then-action="start"
                    kind="Mandatory"/>
            </constraints>
            """,
        )
        prim_members = ["order-d1-d2"]
        expected = fixture_node(
            fixture_primitive("d1", prim_members),
            [
                fixture_node(
                    fixture_order("d1", "d2"),
                    [fixture_node(fixture_primitive("d2", prim_members))],
                )
            ],
        )
        self.assertEqual(
            expected,
            resource.get_resource_relations_tree(
                self.env_assist.get_env(), "d1"
            ),
        )


class GetResourceRelationsTreeComplex(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(
            resources="""
                <resources>
                    {primitives}
                    <clone id="c">
                        <group id="cg">
                        {in_group}
                        </group>
                    </clone>
                </resources>
            """.format(
                primitives=(
                    fixture_primitive_xml("d1")
                    + fixture_primitive_xml("d2")
                    + fixture_primitive_xml("d3")
                ),
                in_group=(
                    fixture_primitive_xml("cgd1")
                    + fixture_primitive_xml("cgd2")
                    + fixture_primitive_xml("cgd0")
                ),
            ),
            constraints="""
            <constraints>
              <rsc_order first="d1" first-action="start" id="order-d1-d2"
                  then="d2" then-action="start" kind="Mandatory"/>
              <rsc_order first="cgd1" first-action="start" id="order-cgd1-d2"
                  then="d2" then-action="start" kind="Optional" score="10"/>
              <rsc_order kind="Serialize" symmetrical="true"
                  id="pcs_rsc_order_set_1">
                <resource_set sequential="true" require-all="true"
                    action="start" id="pcs_rsc_set_1">
                  <resource_ref id="d1"/>
                  <resource_ref id="d3"/>
                </resource_set>
                <resource_set action="stop" sequential="false"
                    require-all="false" id="pcs_rsc_set_2">
                  <resource_ref id="cg"/>
                  <resource_ref id="d2"/>
                </resource_set>
              </rsc_order>
            </constraints>
            """,
        )
        self.d1_members = ["order-d1-d2", "pcs_rsc_order_set_1"]
        self.d2_members = [
            "order-d1-d2",
            "order-cgd1-d2",
            "pcs_rsc_order_set_1",
        ]
        self.order_set = dict(
            id="pcs_rsc_order_set_1",
            type=ResourceRelationType.ORDER_SET,
            members=["cg", "d1", "d2", "d3"],
            metadata={
                "id": "pcs_rsc_order_set_1",
                "sets": [
                    {
                        "id": "pcs_rsc_set_1",
                        "metadata": {
                            "id": "pcs_rsc_set_1",
                            "sequential": "true",
                            "require-all": "true",
                            "action": "start",
                        },
                        "members": ["d1", "d3"],
                    },
                    {
                        "id": "pcs_rsc_set_2",
                        "metadata": {
                            "id": "pcs_rsc_set_2",
                            "sequential": "false",
                            "require-all": "false",
                            "action": "stop",
                        },
                        "members": ["cg", "d2"],
                    },
                ],
                "kind": "Serialize",
                "symmetrical": "true",
            },
        )
        self.cg_ent = dict(
            id="cg",
            type=ResourceRelationType.RSC_GROUP,
            members=["pcs_rsc_order_set_1", "inner:cg", "outer:c"],
            metadata=dict(id="cg"),
        )

    def test_d1(self):
        outer_cg = dict(
            id="outer:cg",
            type=ResourceRelationType.OUTER_RESOURCE,
            members=["cg"],
            metadata=dict(id="cg"),
        )
        order_opt = fixture_order("cgd1", "d2", kind="Optional", score="10")
        expected = fixture_node(
            fixture_primitive("d1", self.d1_members),
            [
                fixture_node(
                    fixture_order("d1", "d2"),
                    [
                        fixture_node(
                            fixture_primitive("d2", self.d2_members),
                            [
                                fixture_node(
                                    order_opt,
                                    [
                                        fixture_node(
                                            fixture_primitive(
                                                "cgd1",
                                                ["order-cgd1-d2", "outer:cg"],
                                            ),
                                            [
                                                fixture_node(
                                                    outer_cg,
                                                    [
                                                        fixture_node(
                                                            self.cg_ent,
                                                            leaf=True,
                                                        ),
                                                    ],
                                                )
                                            ],
                                        ),
                                    ],
                                ),
                                fixture_node(self.order_set, leaf=True),
                            ],
                        )
                    ],
                ),
                fixture_node(
                    self.order_set,
                    [
                        fixture_node(
                            self.cg_ent,
                            [
                                fixture_node(
                                    dict(
                                        id="inner:cg",
                                        type=(
                                            ResourceRelationType.INNER_RESOURCES
                                        ),
                                        members=["cgd1", "cgd2", "cgd0"],
                                        metadata=dict(id="cg"),
                                    ),
                                    [
                                        fixture_node(
                                            fixture_primitive(
                                                "cgd1",
                                                ["order-cgd1-d2", "outer:cg"],
                                            ),
                                            leaf=True,
                                        ),
                                        fixture_node(
                                            fixture_primitive(
                                                "cgd2", ["outer:cg"]
                                            ),
                                        ),
                                        fixture_node(
                                            fixture_primitive(
                                                "cgd0", ["outer:cg"]
                                            ),
                                        ),
                                    ],
                                ),
                                fixture_node(
                                    dict(
                                        id="outer:c",
                                        type=(
                                            ResourceRelationType.OUTER_RESOURCE
                                        ),
                                        members=["c"],
                                        metadata=dict(id="c"),
                                    ),
                                    [
                                        fixture_node(
                                            dict(
                                                id="c",
                                                type=ResourceRelationType.RSC_CLONE,
                                                members=["inner:c"],
                                                metadata=dict(id="c"),
                                            ),
                                            [],
                                        )
                                    ],
                                ),
                            ],
                        ),
                        fixture_node(
                            fixture_primitive("d2", self.d2_members), leaf=True
                        ),
                        fixture_node(
                            fixture_primitive("d3", ["pcs_rsc_order_set_1"]),
                        ),
                    ],
                ),
            ],
        )
        self.assertEqual(
            expected,
            resource.get_resource_relations_tree(
                self.env_assist.get_env(), "d1"
            ),
        )

from unittest import TestCase

from lxml import etree

from pcs.common.interface import dto
from pcs.common.pacemaker.resource.relations import (
    RelationEntityDto,
    ResourceRelationDto,
    ResourceRelationType,
)
from pcs.lib.cib.resource import relations as lib


def fixture_cib(resources, constraints):
    return etree.fromstring(
        f"""
        <cib>
          <configuration>
            <resources>
            {resources}
            </resources>
            <constraints>
            {constraints}
            </constraints>
          </configuration>
        </cib>
    """
    )


def fixture_dummy_metadata(_id):
    return {
        "id": _id,
        "class": "c",
        "provider": "pcmk",
        "type": "Dummy",
    }


class ResourceRelationNode(TestCase):
    @staticmethod
    def entity_fixture(index):
        return dto.from_dict(
            RelationEntityDto,
            dict(
                id=f"ent_id{index}",
                type=str(ResourceRelationType.INNER_RESOURCES.value),
                members=[f"{index}m1", f"{index}m2", f"{index}m0"],
                metadata=dict(
                    id=f"ent_id{index}",
                    k0="val0",
                    k1="val1",
                ),
            ),
        )

    def assert_dto_equal(self, expected, actual):
        self.assertEqual(dto.to_dict(expected), dto.to_dict(actual))

    def test_no_members(self):
        ent = self.entity_fixture("0")
        obj = lib.ResourceRelationNode(ent)
        self.assert_dto_equal(ResourceRelationDto(ent, [], False), obj.to_dto())

    def test_with_members(self):
        ent0 = self.entity_fixture("0")
        ent1 = self.entity_fixture("1")
        ent2 = self.entity_fixture("2")
        ent3 = self.entity_fixture("3")
        obj = lib.ResourceRelationNode(ent0)
        obj.add_member(lib.ResourceRelationNode(ent1))
        member = lib.ResourceRelationNode(ent2)
        member.add_member(lib.ResourceRelationNode(ent3))
        obj.add_member(member)
        self.assert_dto_equal(
            ResourceRelationDto(
                ent0,
                [
                    ResourceRelationDto(ent1, [], False),
                    ResourceRelationDto(
                        ent2,
                        [
                            ResourceRelationDto(ent3, [], False),
                        ],
                        False,
                    ),
                ],
                False,
            ),
            obj.to_dto(),
        )

    def test_stop(self):
        ent = self.entity_fixture("0")
        obj = lib.ResourceRelationNode(ent)
        obj.stop()
        self.assert_dto_equal(
            ResourceRelationDto(ent, [], True),
            obj.to_dto(),
        )

    def test_add_member(self):
        ent0 = self.entity_fixture("0")
        ent1 = self.entity_fixture("1")
        obj = lib.ResourceRelationNode(ent0)
        obj.add_member(lib.ResourceRelationNode(ent1))
        self.assert_dto_equal(
            ResourceRelationDto(
                ent0,
                [ResourceRelationDto(ent1, [], False)],
                False,
            ),
            obj.to_dto(),
        )

    def test_add_member_itself(self):
        ent = self.entity_fixture("0")
        obj = lib.ResourceRelationNode(ent)
        obj.add_member(obj)
        self.assert_dto_equal(
            ResourceRelationDto(ent, [], False),
            obj.to_dto(),
        )

    def test_add_member_already_have_parent(self):
        obj0 = lib.ResourceRelationNode(self.entity_fixture("0"))
        obj1 = lib.ResourceRelationNode(self.entity_fixture("1"))
        obj2 = lib.ResourceRelationNode(self.entity_fixture("2"))
        obj0.add_member(obj1)
        with self.assertRaises(AssertionError):
            obj2.add_member(obj1)

    def test_add_member_already_in_branch(self):
        ent0 = self.entity_fixture("0")
        ent1 = self.entity_fixture("1")
        obj0 = lib.ResourceRelationNode(ent0)
        obj1 = lib.ResourceRelationNode(ent1)
        obj0.add_member(obj1)
        obj1.add_member(obj0)
        self.assert_dto_equal(
            ResourceRelationDto(
                ent0, [ResourceRelationDto(ent1, [], False)], False
            ),
            obj0.to_dto(),
        )

    def test_add_member_already_in_different_branch(self):
        ent0 = self.entity_fixture("0")
        ent1 = self.entity_fixture("1")
        obj0 = lib.ResourceRelationNode(ent0)
        obj0.add_member(lib.ResourceRelationNode(ent1))
        obj0.add_member(lib.ResourceRelationNode(ent1))
        self.assert_dto_equal(
            ResourceRelationDto(
                ent0,
                [
                    ResourceRelationDto(ent1, [], False),
                    ResourceRelationDto(ent1, [], False),
                ],
                False,
            ),
            obj0.to_dto(),
        )


class ResourceRelationsFetcher(TestCase):
    def test_ordering_constraint(self):
        obj = lib.ResourceRelationsFetcher(
            fixture_cib(
                """
            <primitive id="d1" class="c" provider="pcmk" type="Dummy"/>
            <primitive id="d2" class="c" provider="pcmk" type="Dummy"/>
            """,
                """
            <rsc_order first="d1" first-action="start"
                id="order-d1-d2-mandatory" then="d2" then-action="start"
                kind="Mandatory"/>
            """,
            )
        )
        expected = (
            {
                "d1": RelationEntityDto(
                    "d1",
                    ResourceRelationType.RSC_PRIMITIVE,
                    ["order-d1-d2-mandatory"],
                    fixture_dummy_metadata("d1"),
                ),
                "d2": RelationEntityDto(
                    "d2",
                    ResourceRelationType.RSC_PRIMITIVE,
                    ["order-d1-d2-mandatory"],
                    fixture_dummy_metadata("d2"),
                ),
            },
            {
                "order-d1-d2-mandatory": RelationEntityDto(
                    "order-d1-d2-mandatory",
                    ResourceRelationType.ORDER,
                    members=["d1", "d2"],
                    metadata={
                        "id": "order-d1-d2-mandatory",
                        "first": "d1",
                        "first-action": "start",
                        "then": "d2",
                        "then-action": "start",
                        "kind": "Mandatory",
                    },
                ),
            },
        )
        for res in ("d1", "d2"):
            with self.subTest(resource=res):
                self.assertEqual(expected, obj.get_relations(res))

    def test_ordering_set_constraint(self):
        obj = lib.ResourceRelationsFetcher(
            fixture_cib(
                """
            <primitive id="d1" class="c" provider="pcmk" type="Dummy"/>
            <primitive id="d2" class="c" provider="pcmk" type="Dummy"/>
            <primitive id="d3" class="c" provider="pcmk" type="Dummy"/>
            <primitive id="d4" class="c" provider="pcmk" type="Dummy"/>
            <primitive id="d5" class="c" provider="pcmk" type="Dummy"/>
            <primitive id="d6" class="c" provider="pcmk" type="Dummy"/>
            """,
                """
            <rsc_order kind="Serialize" symmetrical="true"
                id="pcs_rsc_order_set_1">
              <resource_set sequential="true" require-all="true" action="start"
                  id="pcs_rsc_set_1">
                <resource_ref id="d1"/>
                <resource_ref id="d3"/>
                <resource_ref id="d2"/>
              </resource_set>
              <resource_set action="stop" sequential="false"
                  require-all="false" id="pcs_rsc_set_2">
                <resource_ref id="d6"/>
                <resource_ref id="d5"/>
                <resource_ref id="d4"/>
              </resource_set>
            </rsc_order>
            """,
            )
        )

        def rsc_entity(_id):
            return RelationEntityDto(
                _id,
                ResourceRelationType.RSC_PRIMITIVE,
                ["pcs_rsc_order_set_1"],
                fixture_dummy_metadata(_id),
            )

        res_list = ("d1", "d2", "d3", "d4", "d5", "d6")
        expected = (
            {_id: rsc_entity(_id) for _id in res_list},
            {
                "pcs_rsc_order_set_1": RelationEntityDto(
                    "pcs_rsc_order_set_1",
                    ResourceRelationType.ORDER_SET,
                    members=["d1", "d2", "d3", "d4", "d5", "d6"],
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
                                "members": ["d1", "d3", "d2"],
                            },
                            {
                                "id": "pcs_rsc_set_2",
                                "metadata": {
                                    "id": "pcs_rsc_set_2",
                                    "sequential": "false",
                                    "require-all": "false",
                                    "action": "stop",
                                },
                                "members": ["d6", "d5", "d4"],
                            },
                        ],
                        "kind": "Serialize",
                        "symmetrical": "true",
                    },
                ),
            },
        )
        for res in res_list:
            with self.subTest(resource=res):
                self.assertEqual(expected, obj.get_relations(res))

    def test_group(self):
        obj = lib.ResourceRelationsFetcher(
            fixture_cib(
                """
            <group id="g1">
              <primitive id="d1" class="c" provider="pcmk" type="Dummy"/>
              <primitive id="d2" class="c" provider="pcmk" type="Dummy"/>
            </group>
            """,
                "",
            )
        )
        expected = (
            {
                "d1": RelationEntityDto(
                    "d1",
                    ResourceRelationType.RSC_PRIMITIVE,
                    ["outer:g1"],
                    fixture_dummy_metadata("d1"),
                ),
                "d2": RelationEntityDto(
                    "d2",
                    ResourceRelationType.RSC_PRIMITIVE,
                    ["outer:g1"],
                    fixture_dummy_metadata("d2"),
                ),
                "g1": RelationEntityDto(
                    "g1",
                    ResourceRelationType.RSC_GROUP,
                    ["inner:g1"],
                    {"id": "g1"},
                ),
            },
            {
                "inner:g1": RelationEntityDto(
                    "inner:g1",
                    ResourceRelationType.INNER_RESOURCES,
                    ["d1", "d2"],
                    {"id": "g1"},
                ),
                "outer:g1": RelationEntityDto(
                    "outer:g1",
                    ResourceRelationType.OUTER_RESOURCE,
                    ["g1"],
                    {"id": "g1"},
                ),
            },
        )
        for res in ("d1", "d2", "g1"):
            with self.subTest(resource=res):
                self.assertEqual(expected, obj.get_relations(res))

    def _test_wrapper(self, wrapper_tag, rel_type):
        obj = lib.ResourceRelationsFetcher(
            fixture_cib(
                f"""
            <{wrapper_tag} id="w1">
              <primitive id="d1" class="c" provider="pcmk" type="Dummy"/>
            </{wrapper_tag}>
            """,
                "",
            )
        )
        expected = (
            {
                "d1": RelationEntityDto(
                    "d1",
                    ResourceRelationType.RSC_PRIMITIVE,
                    ["outer:w1"],
                    fixture_dummy_metadata("d1"),
                ),
                "w1": RelationEntityDto(
                    "w1", rel_type, ["inner:w1"], {"id": "w1"}
                ),
            },
            {
                "inner:w1": RelationEntityDto(
                    "inner:w1",
                    ResourceRelationType.INNER_RESOURCES,
                    ["d1"],
                    {"id": "w1"},
                ),
                "outer:w1": RelationEntityDto(
                    "outer:w1",
                    ResourceRelationType.OUTER_RESOURCE,
                    ["w1"],
                    {"id": "w1"},
                ),
            },
        )
        for res in ("d1", "w1"):
            with self.subTest(resource=res):
                self.assertEqual(expected, obj.get_relations(res))

    def test_clone(self):
        self._test_wrapper("clone", ResourceRelationType.RSC_CLONE)

    def test_master(self):
        self._test_wrapper("master", ResourceRelationType.RSC_CLONE)

    def test_bundle(self):
        self._test_wrapper("bundle", ResourceRelationType.RSC_BUNDLE)

    def test_cloned_group(self):
        obj = lib.ResourceRelationsFetcher(
            fixture_cib(
                """
            <clone id="c1">
                <group id="g1">
                  <primitive id="d1" class="c" provider="pcmk" type="Dummy"/>
                  <primitive id="d2" class="c" provider="pcmk" type="Dummy"/>
                </group>
            </clone>
            """,
                "",
            )
        )
        expected = (
            {
                "d1": RelationEntityDto(
                    "d1",
                    ResourceRelationType.RSC_PRIMITIVE,
                    ["outer:g1"],
                    fixture_dummy_metadata("d1"),
                ),
                "d2": RelationEntityDto(
                    "d2",
                    ResourceRelationType.RSC_PRIMITIVE,
                    ["outer:g1"],
                    fixture_dummy_metadata("d2"),
                ),
                "g1": RelationEntityDto(
                    "g1",
                    ResourceRelationType.RSC_GROUP,
                    ["inner:g1", "outer:c1"],
                    {"id": "g1"},
                ),
                "c1": RelationEntityDto(
                    "c1",
                    ResourceRelationType.RSC_CLONE,
                    ["inner:c1"],
                    {"id": "c1"},
                ),
            },
            {
                "inner:g1": RelationEntityDto(
                    "inner:g1",
                    ResourceRelationType.INNER_RESOURCES,
                    ["d1", "d2"],
                    {"id": "g1"},
                ),
                "outer:g1": RelationEntityDto(
                    "outer:g1",
                    ResourceRelationType.OUTER_RESOURCE,
                    ["g1"],
                    {"id": "g1"},
                ),
                "inner:c1": RelationEntityDto(
                    "inner:c1",
                    ResourceRelationType.INNER_RESOURCES,
                    ["g1"],
                    {"id": "c1"},
                ),
                "outer:c1": RelationEntityDto(
                    "outer:c1",
                    ResourceRelationType.OUTER_RESOURCE,
                    ["c1"],
                    {"id": "c1"},
                ),
            },
        )
        for res in ("d1", "d2", "g1", "c1"):
            with self.subTest(resource=res):
                self.assertEqual(expected, obj.get_relations(res))


class ResourceRelationTreeBuilder(TestCase):
    @staticmethod
    def primitive_fixture(_id, members):
        return RelationEntityDto(
            _id,
            ResourceRelationType.RSC_PRIMITIVE,
            members,
            fixture_dummy_metadata(_id),
        )

    def test_resource_not_present(self):
        with self.assertRaises(AssertionError):
            lib.ResourceRelationTreeBuilder({}, {}).get_tree("not_existing")

    def test_simple_order(self):
        resources_members = ["order-d1-d2-mandatory"]
        resources = {
            "d1": self.primitive_fixture("d1", resources_members),
            "d2": self.primitive_fixture("d2", resources_members),
        }
        relations = {
            "order-d1-d2-mandatory": RelationEntityDto(
                "order-d1-d2-mandatory",
                ResourceRelationType.ORDER,
                members=["d1", "d2"],
                metadata={
                    "id": "order-d1-d2-mandatory",
                    "first": "d1",
                    "first-action": "start",
                    "then": "d2",
                    "then-action": "start",
                    "kind": "Mandatory",
                },
            ),
        }
        expected = dict(
            relation_entity=dto.to_dict(resources["d2"]),
            is_leaf=False,
            members=[
                dict(
                    relation_entity=dto.to_dict(
                        relations["order-d1-d2-mandatory"]
                    ),
                    is_leaf=False,
                    members=[
                        dict(
                            relation_entity=dto.to_dict(resources["d1"]),
                            is_leaf=False,
                            members=[],
                        )
                    ],
                )
            ],
        )
        self.assertEqual(
            expected,
            dto.to_dict(
                lib.ResourceRelationTreeBuilder(resources, relations)
                .get_tree("d2")
                .to_dto()
            ),
        )

    def test_simple_order_set(self):
        res_list = ("d1", "d2", "d3", "d4", "d5", "d6")
        resources_members = ["pcs_rsc_order_set_1"]
        resources = {
            _id: self.primitive_fixture(_id, resources_members)
            for _id in res_list
        }
        relations = {
            "pcs_rsc_order_set_1": RelationEntityDto(
                "pcs_rsc_order_set_1",
                ResourceRelationType.ORDER_SET,
                members=["d1", "d2", "d3", "d4", "d5", "d6"],
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
                            "members": ["d1", "d3", "d2"],
                        },
                        {
                            "id": "pcs_rsc_set_2",
                            "metadata": {
                                "id": "pcs_rsc_set_2",
                                "sequential": "false",
                                "require-all": "false",
                                "action": "stop",
                            },
                            "members": ["d6", "d5", "d4"],
                        },
                    ],
                    "kind": "Serialize",
                    "symmetrical": "true",
                },
            ),
        }

        def get_res(_id):
            return dict(
                relation_entity=dto.to_dict(resources[_id]),
                is_leaf=False,
                members=[],
            )

        expected = dict(
            relation_entity=dto.to_dict(resources["d5"]),
            is_leaf=False,
            members=[
                dict(
                    relation_entity=dto.to_dict(
                        relations["pcs_rsc_order_set_1"]
                    ),
                    is_leaf=False,
                    members=[
                        get_res(_id) for _id in ("d1", "d2", "d3", "d4", "d6")
                    ],
                )
            ],
        )
        self.assertEqual(
            expected,
            dto.to_dict(
                lib.ResourceRelationTreeBuilder(resources, relations)
                .get_tree("d5")
                .to_dto()
            ),
        )

    def test_simple_in_group(self):
        resources_members = ["outer:g1"]
        resources = {
            "d1": self.primitive_fixture("d1", resources_members),
            "d2": self.primitive_fixture("d2", resources_members),
            "g1": RelationEntityDto("g1", "group", ["inner:g1"], {"id": "g1"}),
        }
        relations = {
            "inner:g1": RelationEntityDto(
                "inner:g1",
                ResourceRelationType.INNER_RESOURCES,
                ["d1", "d2"],
                {"id": "g1"},
            ),
            "outer:g1": RelationEntityDto(
                "outer:g1",
                ResourceRelationType.OUTER_RESOURCE,
                ["g1"],
                {"id": "g1"},
            ),
        }
        expected = dict(
            relation_entity=dto.to_dict(resources["d1"]),
            is_leaf=False,
            members=[
                dict(
                    relation_entity=dto.to_dict(relations["outer:g1"]),
                    is_leaf=False,
                    members=[
                        dict(
                            relation_entity=dto.to_dict(resources["g1"]),
                            is_leaf=False,
                            members=[
                                dict(
                                    relation_entity=dto.to_dict(
                                        relations["inner:g1"]
                                    ),
                                    is_leaf=False,
                                    members=[
                                        dict(
                                            relation_entity=dto.to_dict(
                                                resources["d2"]
                                            ),
                                            is_leaf=False,
                                            members=[],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
        self.assertEqual(
            expected,
            dto.to_dict(
                lib.ResourceRelationTreeBuilder(resources, relations)
                .get_tree("d1")
                .to_dto()
            ),
        )

    def test_order_loop(self):
        def order_fixture(res1, res2):
            return RelationEntityDto(
                f"order-{res1}-{res2}-mandatory",
                ResourceRelationType.ORDER,
                members=[res1, res2],
                metadata={
                    "id": f"order-{res1}-{res2}-mandatory",
                    "first": res1,
                    "first-action": "start",
                    "then": res2,
                    "then-action": "start",
                    "kind": "Mandatory",
                },
            )

        resources_members = ["order-d1-d2-mandatory", "order-d2-d1-mandatory"]
        resources = {
            "d1": self.primitive_fixture("d1", resources_members),
            "d2": self.primitive_fixture("d2", resources_members),
        }

        relations = {
            "order-d1-d2-mandatory": order_fixture("d1", "d2"),
            "order-d2-d1-mandatory": order_fixture("d2", "d1"),
        }
        expected = dict(
            relation_entity=dto.to_dict(resources["d1"]),
            is_leaf=False,
            members=[
                dict(
                    relation_entity=dto.to_dict(
                        relations["order-d1-d2-mandatory"]
                    ),
                    is_leaf=False,
                    members=[
                        dict(
                            relation_entity=dto.to_dict(resources["d2"]),
                            is_leaf=False,
                            members=[
                                dict(
                                    relation_entity=dto.to_dict(
                                        relations["order-d2-d1-mandatory"]
                                    ),
                                    is_leaf=True,
                                    members=[],
                                ),
                            ],
                        ),
                    ],
                ),
                dict(
                    relation_entity=dto.to_dict(
                        relations["order-d2-d1-mandatory"]
                    ),
                    is_leaf=False,
                    members=[
                        dict(
                            relation_entity=dto.to_dict(resources["d2"]),
                            is_leaf=True,
                            members=[],
                        ),
                    ],
                ),
            ],
        )
        self.assertEqual(
            expected,
            dto.to_dict(
                lib.ResourceRelationTreeBuilder(resources, relations)
                .get_tree("d1")
                .to_dto()
            ),
        )

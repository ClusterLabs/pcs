from pcs.test.tools.pcs_unittest import mock, TestCase

from pcs.common.pacemaker.resource.relations import (
    RelationEntityDto,
    ResourceRelationDto,
    ResourceRelationType,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.resource import relations


DEFAULT_MODIFIERS = {"full": False}


class ShowResourceRelationsCmd(TestCase):
    def setUp(self):
        self.maxDiff = None
        self.lib_call = mock.Mock()
        self.lib = mock.Mock(spec_set=["resource"])
        self.lib.resource = mock.Mock(spec_set=["get_resource_relations_tree"])
        self.lib.resource.get_resource_relations_tree = self.lib_call
        self.lib_call.return_value = ResourceRelationDto(
            RelationEntityDto(
                "d1", "primitive", [], {
                    "class": "ocf",
                    "provider": "pacemaker",
                    "type": "Dummy",
                }
            ),
            [
                ResourceRelationDto(
                    RelationEntityDto(
                        "order1", ResourceRelationType.ORDER, [], {
                            "first-action": "start",
                            "first": "d1",
                            "then-action": "start",
                            "then": "d2",
                            "kind": "Mandatory",
                            "symmetrical": "true",
                        }
                    ),
                    [
                        ResourceRelationDto(
                            RelationEntityDto(
                                "d2", "primitive", [], {
                                    "class": "ocf",
                                    "provider": "heartbeat",
                                    "type": "Dummy",
                                }
                            ),
                            [],
                            False
                        ),
                    ],
                    False
                ),
                ResourceRelationDto(
                    RelationEntityDto(
                        "inner:g1", ResourceRelationType.INNER_RESOURCES, [], {}
                    ),
                    [
                        ResourceRelationDto(
                            RelationEntityDto("g1", "group", [], {}),
                            [],
                            True,
                        ),
                    ],
                    False
                )
            ],
            False,
        ).to_dict()

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            relations.show_resource_relations_cmd(
                self.lib, [], DEFAULT_MODIFIERS
            )
        self.assertIsNone(cm.exception.message)

    def test_more_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            relations.show_resource_relations_cmd(
                self.lib, ["a1", "a2"], DEFAULT_MODIFIERS
            )
        self.assertIsNone(cm.exception.message)

    @mock.patch("pcs.cli.resource.relations.print")
    def test_success(self, mock_print):
        relations.show_resource_relations_cmd(
            self.lib, ["d1"], DEFAULT_MODIFIERS
        )
        self.lib_call.assert_called_once_with("d1")
        self.assertEqual(
            [
                mock.call("d1"),
                mock.call("|- inner resource(s)"),
                mock.call("|  `- g1 [displayed elsewhere]"),
                mock.call("`- order"),
                mock.call("   |  start d1 then start d2"),
                mock.call("   |  kind=Mandatory symmetrical=true"),
                mock.call("   `- d2"),
            ],
            mock_print.call_args_list
        )

    @mock.patch("pcs.cli.resource.relations.print")
    def test_verbose(self, mock_print):
        relations.show_resource_relations_cmd(self.lib, ["d1"], {"full": True})
        self.lib_call.assert_called_once_with("d1")
        self.assertEqual(
            [
                mock.call("d1 (resource: ocf:pacemaker:Dummy)"),
                mock.call("|- inner resource(s) (None)"),
                mock.call("|  `- g1 (resource: group) [displayed elsewhere]"),
                mock.call("`- order (None)"),
                mock.call("   |  start d1 then start d2"),
                mock.call("   |  kind=Mandatory symmetrical=true"),
                mock.call("   `- d2 (resource: ocf:heartbeat:Dummy)"),
            ],
            mock_print.call_args_list
        )


def _fixture_dummy(_id):
    return RelationEntityDto(
    _id, "primitive", [], {
        "class": "ocf",
        "provider": "pacemaker",
        "type": "Dummy",
    }
)


D1_PRIMITIVE = _fixture_dummy("d1")
D2_PRIMITIVE = _fixture_dummy("d2")


def _fixture_res_rel_dto(ent):
    return ResourceRelationDto(ent, [], True)


class ResourcePrintableNode(TestCase):
    def assert_member(self, member, ent):
        self.assertTrue(isinstance(member, relations.RelationPrintableNode))
        self.assertEqual(ent, member.relation_entity)
        self.assertEqual(True, member.is_leaf)
        self.assertEqual(0, len(member.members))

    def test_from_dto(self):
        inner_ent = RelationEntityDto(
            "inner:g1", ResourceRelationType.INNER_RESOURCES, [], {}
        )
        outer_ent = RelationEntityDto(
            "outer:g1", ResourceRelationType.OUTER_RESOURCE, [], {}
        )
        order_ent1 = RelationEntityDto(
            "order1", ResourceRelationType.ORDER, [], {}
        )
        order_ent2 = RelationEntityDto(
            "order2", ResourceRelationType.ORDER, [], {}
        )
        order_set_ent = RelationEntityDto(
            "order_set", ResourceRelationType.ORDER_SET, [], {}
        )

        dto = ResourceRelationDto(
            D1_PRIMITIVE,
            [
                _fixture_res_rel_dto(order_set_ent),
                _fixture_res_rel_dto(order_ent2),
                _fixture_res_rel_dto(outer_ent),
                _fixture_res_rel_dto(inner_ent),
                _fixture_res_rel_dto(order_ent1),
            ],
            False,
        )
        obj = relations.ResourcePrintableNode.from_dto(dto)
        self.assertEqual(D1_PRIMITIVE, obj.relation_entity)
        self.assertEqual(False, obj.is_leaf)
        expected_members = (
            inner_ent, outer_ent, order_ent1, order_ent2, order_set_ent
        )
        self.assertEqual(len(expected_members), len(obj.members))
        for i, member in enumerate(obj.members):
            self.assert_member(member, expected_members[i])

    def test_primitive(self):
        obj = relations.ResourcePrintableNode(D1_PRIMITIVE, [], False)
        self.assertEqual(
            "d1 (resource: ocf:pacemaker:Dummy)", obj.get_title(verbose=True)
        )
        self.assertEqual([], obj.detail)

    def test_primitive_not_verbose(self):
        obj = relations.ResourcePrintableNode(D1_PRIMITIVE, [], False)
        self.assertEqual("d1", obj.get_title(verbose=False))
        self.assertEqual([], obj.detail)

    def test_primitive_without_provider_class(self):
        obj = relations.ResourcePrintableNode(
            RelationEntityDto(
                "d1", "primitive", [], {
                    "type": "Dummy",
                }
            ),
            [],
            False,
        )
        self.assertEqual("d1 (resource: Dummy)", obj.get_title(verbose=True))
        self.assertEqual([], obj.detail)

    def test_primitive_without_provider(self):
        obj = relations.ResourcePrintableNode(
            RelationEntityDto(
                "d1", "primitive", [], {
                    "class": "ocf",
                    "type": "Dummy",
                }
            ),
            [],
            False,
        )
        self.assertEqual(
            "d1 (resource: ocf:Dummy)", obj.get_title(verbose=True)
        )
        self.assertEqual([], obj.detail)

    def test_primitive_without_class(self):
        obj = relations.ResourcePrintableNode(
            RelationEntityDto(
                "d1", "primitive", [], {
                    "provider": "pacemaker",
                    "type": "Dummy",
                }
            ),
            [],
            False,
        )
        self.assertEqual(
            "d1 (resource: pacemaker:Dummy)", obj.get_title(verbose=True)
        )
        self.assertEqual([], obj.detail)

    def test_other(self):
        obj = relations.ResourcePrintableNode(
            RelationEntityDto("an_id", "a_type", [], {}), [], False,
        )
        self.assertEqual(
            "an_id (resource: a_type)", obj.get_title(verbose=True)
        )
        self.assertEqual([], obj.detail)

    def test_other_not_verbose(self):
        obj = relations.ResourcePrintableNode(
            RelationEntityDto("an_id", "a_type", [], {}), [], False,
        )
        self.assertEqual("an_id", obj.get_title(verbose=False))
        self.assertEqual([], obj.detail)


class RelationPrintableNode(TestCase):
    def setUp(self):
        self.order_entity = RelationEntityDto(
            "order1", ResourceRelationType.ORDER, [], {
                "id": "order1",
                "first-action": "start",
                "first": "d1",
                "then-action": "start",
                "then": "d2",
            }
        )
        self.order_set_entity = RelationEntityDto(
            "order_set_id", ResourceRelationType.ORDER_SET, [], {
                "id": "order_set_id",
                "sets": [
                    {
                        "members": ["d1", "d2", "d3"],
                        "metadata": {},
                    },
                    {
                        "members": ["d4", "d5", "d0"],
                        "metadata": {
                            "sequential": "true",
                            "require-all": "false",
                            "score": "10",
                        },
                    },
                ],
            }
        )

    def assert_member(self, member, ent):
        self.assertTrue(isinstance(member, relations.ResourcePrintableNode))
        self.assertEqual(ent, member.relation_entity)
        self.assertEqual(True, member.is_leaf)
        self.assertEqual(0, len(member.members))

    def test_from_dto(self):
        dto = ResourceRelationDto(
            self.order_entity,
            [
                ResourceRelationDto(D2_PRIMITIVE, [], True),
                ResourceRelationDto(D1_PRIMITIVE, [], True),
            ],
            False
        )
        obj = relations.RelationPrintableNode.from_dto(dto)
        self.assertEqual(self.order_entity, obj.relation_entity)
        self.assertEqual(False, obj.is_leaf)
        self.assertEqual(2, len(obj.members))
        self.assert_member(obj.members[0], D1_PRIMITIVE)
        self.assert_member(obj.members[1], D2_PRIMITIVE)

    def test_order_not_verbose(self):
        obj = relations.RelationPrintableNode(self.order_entity, [], False)
        self.assertEqual("order", obj.get_title(verbose=False))
        self.assertEqual(["start d1 then start d2"], obj.detail)

    def test_order(self):
        obj = relations.RelationPrintableNode(self.order_entity, [], False)
        self.assertEqual("order (order1)", obj.get_title(verbose=True))
        self.assertEqual(["start d1 then start d2"], obj.detail)

    def test_order_full(self):
        self.order_entity.metadata.update({
            "kind": "Optional",
            "symmetrical": "true",
            "unsupported": "value",
            "score": "1000",
        })
        obj = relations.RelationPrintableNode(self.order_entity, [], False)
        self.assertEqual("order (order1)", obj.get_title(verbose=True))
        self.assertEqual(
            [
                "start d1 then start d2",
                "kind=Optional score=1000 symmetrical=true"
            ],
            obj.detail,
        )

    def test_order_set_not_verbose(self):
        obj = relations.RelationPrintableNode(self.order_set_entity, [], False)
        self.assertEqual("order set", obj.get_title(verbose=False))
        self.assertEqual(
            [
                "   set d1 d2 d3",
                "   set d4 d5 d0 (require-all=false score=10 sequential=true)",
            ],
            obj.detail,
        )

    def test_order_set(self):
        obj = relations.RelationPrintableNode(self.order_set_entity, [], False)
        self.assertEqual(
            "order set (order_set_id)", obj.get_title(verbose=True)
        )
        self.assertEqual(
            [
                "   set d1 d2 d3",
                "   set d4 d5 d0 (require-all=false score=10 sequential=true)",
            ],
            obj.detail,
        )

    def test_order_set_full(self):
        self.order_set_entity.metadata.update({
            "symmetrical": "true",
            "kind": "Optional",
            "require-all": "true",
            "score": "100",
            "unsupported": "value",
        })
        self.order_set_entity.metadata["sets"].append({
            "members": ["d9", "d8", "d6", "d7"],
            "metadata": {
                "sequential": "true",
                "require-all": "false",
                "score": "10",
                "ordering": "value",
                "action": "start",
                "role": "promoted",
                "kind": "Optional",
                "unsupported": "value",
            },
        })
        obj = relations.RelationPrintableNode(self.order_set_entity, [], False)
        self.assertEqual(
            "order set (order_set_id)", obj.get_title(verbose=True)
        )
        self.assertEqual(
            [
                "kind=Optional require-all=true score=100 symmetrical=true",
                "   set d1 d2 d3",
                "   set d4 d5 d0 (require-all=false score=10 sequential=true)",
                "   set d9 d8 d6 d7 (action=start kind=Optional ordering=value "
                "require-all=false role=promoted score=10 sequential=true)",
            ],
            obj.detail,
        )

    def test_multiple_inner_resources(self):
        obj = relations.RelationPrintableNode(
            RelationEntityDto(
                "inner:g1",
                ResourceRelationType.INNER_RESOURCES,
                ["m1", "m2", "m0"],
                {"id": "g1"}
            ),
            [],
            False,
        )
        self.assertEqual("inner resource(s) (g1)", obj.get_title(verbose=True))
        self.assertEqual(["members: m1 m2 m0"], obj.detail)

    def test_inner_resources_not_verbose(self):
        obj = relations.RelationPrintableNode(
            RelationEntityDto(
                "inner:g1", ResourceRelationType.INNER_RESOURCES, ["m0"], {
                    "id": "g1",
                }
            ),
            [],
            False,
        )
        self.assertEqual("inner resource(s)", obj.get_title(verbose=False))
        self.assertEqual([], obj.detail)

    def test_inner_resources(self):
        obj = relations.RelationPrintableNode(
            RelationEntityDto(
                "inner:g1", ResourceRelationType.INNER_RESOURCES, ["m0"], {
                    "id": "g1",
                }
            ),
            [],
            False,
        )
        self.assertEqual("inner resource(s) (g1)", obj.get_title(verbose=True))
        self.assertEqual([], obj.detail)

    def test_outer_resourcenot_verbose(self):
        obj = relations.RelationPrintableNode(
            RelationEntityDto(
                "outer:g1", ResourceRelationType.OUTER_RESOURCE, [], {
                    "id": "g1",
                }
            ),
            [],
            False,
        )
        self.assertEqual("outer resource", obj.get_title(verbose=False))
        self.assertEqual([], obj.detail)

    def test_outer_resource(self):
        obj = relations.RelationPrintableNode(
            RelationEntityDto(
                "outer:g1", ResourceRelationType.OUTER_RESOURCE, [], {
                    "id": "g1",
                }
            ),
            [],
            False,
        )
        self.assertEqual("outer resource (g1)", obj.get_title(verbose=True))
        self.assertEqual([], obj.detail)

    def test_unknown_not_verbose(self):
        obj = relations.RelationPrintableNode(
            RelationEntityDto(
                "random", "undifined type", [], {
                    "id": "random_id",
                }
            ),
            [],
            False,
        )
        self.assertEqual("<unknown>", obj.get_title(verbose=False))
        self.assertEqual([], obj.detail)

    def test_unknown(self):
        obj = relations.RelationPrintableNode(
            RelationEntityDto(
                "random", "undifined type", [], {
                    "id": "random_id",
                }
            ),
            [],
            False,
        )
        self.assertEqual("<unknown> (random_id)", obj.get_title(verbose=True))
        self.assertEqual([], obj.detail)

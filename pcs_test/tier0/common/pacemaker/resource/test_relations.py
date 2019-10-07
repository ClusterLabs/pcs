from unittest import TestCase

from pcs.common.pacemaker.resource import relations


class RelationEntityDto(TestCase):
    def setUp(self):
        self.an_id = "an_id"
        self.members = ["m2", "m1", "m3", "m0"]
        self.metadata = dict(
            key1="val1",
            key0="vel0",
            keyx="valx",
        )
        self.str_type = "a_type"
        self.enum_type = relations.ResourceRelationType.ORDER_SET

    def dto_fixture(self, a_type):
        return relations.RelationEntityDto(
            self.an_id, a_type, self.members, self.metadata
        )

    def dict_fixture(self, a_type):
        return dict(
            id=self.an_id,
            type=a_type,
            members=self.members,
            metadata=self.metadata,
        )

    def test_to_dict_type_str(self):
        dto = self.dto_fixture(self.str_type)
        self.assertEqual(self.dict_fixture(self.str_type), dto.to_dict())

    def test_to_dict_type_enum(self):
        dto = self.dto_fixture(self.enum_type)
        self.assertEqual(self.dict_fixture(self.enum_type.value), dto.to_dict())

    def test_from_dict_type_str(self):
        dto = relations.RelationEntityDto.from_dict(
            self.dict_fixture(self.str_type)
        )
        self.assertEqual(dto.id, self.an_id)
        self.assertEqual(dto.type, self.str_type)
        self.assertEqual(dto.members, self.members)
        self.assertEqual(dto.metadata, self.metadata)

    def test_from_dict_type_enum(self):
        dto = relations.RelationEntityDto.from_dict(
            self.dict_fixture(self.enum_type.value)
        )
        self.assertEqual(dto.id, self.an_id)
        self.assertEqual(dto.type, self.enum_type)
        self.assertEqual(dto.members, self.members)
        self.assertEqual(dto.metadata, self.metadata)


class ResourceRelationDto(TestCase):
    @staticmethod
    def ent_dto_fixture(an_id):
        return relations.RelationEntityDto(
            an_id, "a_type", ["m1", "m0", "m2"], dict(k1="v1", kx="vx")
        )

    def test_to_dict_no_members(self):
        ent_dto = self.ent_dto_fixture("an_id")
        dto = relations.ResourceRelationDto(ent_dto, [], True)
        self.assertEqual(
            dict(
                relation_entity=ent_dto.to_dict(),
                members=[],
                is_leaf=True,
            ),
            dto.to_dict()
        )

    def test_to_dict_with_members(self):
        ent_dto = self.ent_dto_fixture("an_id")
        m1_ent = self.ent_dto_fixture("m1_ent")
        m2_ent = self.ent_dto_fixture("m2_ent")
        m3_ent = self.ent_dto_fixture("m3_ent")
        members = [
            relations.ResourceRelationDto(
                m1_ent, [], False
            ),
            relations.ResourceRelationDto(
                m2_ent,
                [relations.ResourceRelationDto(m3_ent, [], True)],
                False
            ),
        ]
        dto = relations.ResourceRelationDto(ent_dto, members, True)
        self.assertEqual(
            dict(
                relation_entity=ent_dto.to_dict(),
                members=[
                    dict(
                        relation_entity=m1_ent.to_dict(),
                        members=[],
                        is_leaf=False,
                    ),
                    dict(
                        relation_entity=m2_ent.to_dict(),
                        members=[
                            dict(
                                relation_entity=m3_ent.to_dict(),
                                members=[],
                                is_leaf=True,
                            )
                        ],
                        is_leaf=False,
                    ),
                ],
                is_leaf=True,
            ),
            dto.to_dict()
        )

    def test_from_dict(self):
        ent_dto = self.ent_dto_fixture("an_id")
        m1_ent = self.ent_dto_fixture("m1_ent")
        m2_ent = self.ent_dto_fixture("m2_ent")
        m3_ent = self.ent_dto_fixture("m3_ent")
        dto = relations.ResourceRelationDto.from_dict(
            dict(
                relation_entity=ent_dto.to_dict(),
                members=[
                    dict(
                        relation_entity=m1_ent.to_dict(),
                        members=[],
                        is_leaf=False,
                    ),
                    dict(
                        relation_entity=m2_ent.to_dict(),
                        members=[
                            dict(
                                relation_entity=m3_ent.to_dict(),
                                members=[],
                                is_leaf=True,
                            )
                        ],
                        is_leaf=False,
                    ),
                ],
                is_leaf=True,
            )
        )
        self.assertEqual(ent_dto.to_dict(), dto.relation_entity.to_dict())
        self.assertEqual(True, dto.is_leaf)
        self.assertEqual(2, len(dto.members))

        self.assertEqual(
            m1_ent.to_dict(), dto.members[0].relation_entity.to_dict()
        )
        self.assertEqual(False, dto.members[0].is_leaf)
        self.assertEqual(0, len(dto.members[0].members))

        self.assertEqual(
            m2_ent.to_dict(), dto.members[1].relation_entity.to_dict()
        )
        self.assertEqual(False, dto.members[1].is_leaf)
        self.assertEqual(1, len(dto.members[1].members))

        self.assertEqual(
            m3_ent.to_dict(),
            dto.members[1].members[0].relation_entity.to_dict(),
        )
        self.assertEqual(True, dto.members[1].members[0].is_leaf)
        self.assertEqual(0, len(dto.members[1].members[0].members))

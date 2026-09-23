from unittest import TestCase

from pcs.common.pacemaker.resource.list import (
    CibResourcesDto,
    get_all_resources_ids,
    get_stonith_resources_ids,
)

from pcs_test.tools.resources_dto import (
    ALL_RESOURCES,
    PRIMITIVE_R1,
    PRIMITIVE_R2,
)


class GetAllResourcesIds(TestCase):
    def test_resources(self):
        self.assertEqual(
            get_all_resources_ids(ALL_RESOURCES),
            {
                "R1",
                "R2",
                "R3",
                "R4",
                "R5",
                "R6",
                "R7",
                "S1",
                "S2",
                "G1",
                "G2",
                "B1",
                "B2",
                "G1-clone",
                "R6-clone",
            },
        )

    def test_no_resources(self):
        self.assertEqual(
            get_all_resources_ids(CibResourcesDto([], [], [], [])), set()
        )


class GetStonithResourcesIds(TestCase):
    def test_resources(self):
        self.assertEqual(get_stonith_resources_ids(ALL_RESOURCES), {"S1", "S2"})

    def test_no_resources(self):
        self.assertEqual(
            get_stonith_resources_ids(CibResourcesDto([], [], [], [])), set()
        )

    def test_no_stonith_resources(self):
        self.assertEqual(
            get_stonith_resources_ids(
                CibResourcesDto([PRIMITIVE_R1, PRIMITIVE_R2], [], [], [])
            ),
            set(),
        )

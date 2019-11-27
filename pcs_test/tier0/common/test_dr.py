from unittest import TestCase

from pcs.common import dr


class DrConfigNodeDto(TestCase):
    def setUp(self):
        self.name = "node-name"

    def _fixture_dto(self):
        return dr.DrConfigNodeDto(self.name)

    def _fixture_dict(self):
        return dict(name=self.name)

    def test_to_dict(self):
        self.assertEqual(
            self._fixture_dict(),
            self._fixture_dto().to_dict()
        )

    def test_from_dict(self):
        dto = dr.DrConfigNodeDto.from_dict(self._fixture_dict())
        self.assertEqual(dto.name, self.name)


class DrConfigSiteDto(TestCase):
    def setUp(self):
        self.role = dr.DrRole.PRIMARY
        self.node_name_list = ["node1", "node2"]

    def _fixture_dto(self):
        return dr.DrConfigSiteDto(
            self.role,
            [dr.DrConfigNodeDto(name) for name in self.node_name_list]
        )

    def _fixture_dict(self):
        return dict(
            site_role=self.role,
            node_list=[dict(name=name) for name in self.node_name_list]
        )

    def test_to_dict(self):
        self.assertEqual(
            self._fixture_dict(),
            self._fixture_dto().to_dict()
        )

    def test_from_dict(self):
        dto = dr.DrConfigSiteDto.from_dict(self._fixture_dict())
        self.assertEqual(dto.site_role, self.role)
        self.assertEqual(len(dto.node_list), len(self.node_name_list))
        for i, dto_node in enumerate(dto.node_list):
            self.assertEqual(
                dto_node.name,
                self.node_name_list[i],
                f"index: {i}"
            )


class DrConfig(TestCase):
    @staticmethod
    def _fixture_site_dto(role, node_name_list):
        return dr.DrConfigSiteDto(
            role,
            [dr.DrConfigNodeDto(name) for name in node_name_list]
        )

    @staticmethod
    def _fixture_dict():
        return {
            "local_site": {
                "node_list": [],
                "site_role": "RECOVERY",
            },
            "remote_site_list": [
                {
                    "node_list": [
                        {"name": "nodeA1"},
                        {"name": "nodeA2"},
                    ],
                    "site_role": "PRIMARY",
                },
                {
                    "node_list": [
                        {"name": "nodeB1"},
                    ],
                    "site_role": "RECOVERY",
                }
            ],
        }

    def test_to_dict(self):
        self.assertEqual(
            self._fixture_dict(),
            dr.DrConfigDto(
                self._fixture_site_dto(dr.DrRole.RECOVERY, []),
                [
                    self._fixture_site_dto(
                        dr.DrRole.PRIMARY,
                        ["nodeA1", "nodeA2"]
                    ),
                    self._fixture_site_dto(
                        dr.DrRole.RECOVERY,
                        ["nodeB1"]
                    ),
                ]
            ).to_dict()
        )

    def test_from_dict(self):
        dto = dr.DrConfigDto.from_dict(self._fixture_dict())
        self.assertEqual(
            dto.local_site.to_dict(),
            self._fixture_site_dto(dr.DrRole.RECOVERY, []).to_dict()
        )
        self.assertEqual(len(dto.remote_site_list), 2)
        self.assertEqual(
            dto.remote_site_list[0].to_dict(),
            self._fixture_site_dto(
                dr.DrRole.PRIMARY, ["nodeA1", "nodeA2"]
            ).to_dict()
        )
        self.assertEqual(
            dto.remote_site_list[1].to_dict(),
            self._fixture_site_dto(dr.DrRole.RECOVERY, ["nodeB1"]).to_dict()
        )

class DrSiteStatusDto(TestCase):
    def setUp(self):
        self.local = False
        self.role = dr.DrRole.PRIMARY
        self.status_plaintext = "plaintext status"
        self.status_successfully_obtained = True

    def dto_fixture(self):
        return dr.DrSiteStatusDto(
            self.local,
            self.role,
            self.status_plaintext,
            self.status_successfully_obtained,
        )

    def dict_fixture(self):
        return dict(
            local_site=self.local,
            site_role=self.role.value,
            status_plaintext=self.status_plaintext,
            status_successfully_obtained=self.status_successfully_obtained,
        )

    def test_to_dict(self):
        self.assertEqual(
            self.dict_fixture(),
            self.dto_fixture().to_dict()
        )

    def test_from_dict(self):
        dto = dr.DrSiteStatusDto.from_dict(self.dict_fixture())
        self.assertEqual(dto.local_site, self.local)
        self.assertEqual(dto.site_role, self.role)
        self.assertEqual(dto.status_plaintext, self.status_plaintext)
        self.assertEqual(
            dto.status_successfully_obtained,
            self.status_successfully_obtained
        )

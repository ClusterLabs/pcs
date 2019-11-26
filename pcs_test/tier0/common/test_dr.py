from unittest import TestCase

from pcs.common import dr

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

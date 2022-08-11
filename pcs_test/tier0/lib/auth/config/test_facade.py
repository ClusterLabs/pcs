from unittest import (
    TestCase,
    mock,
)

from pcs.lib.auth.config.facade import Facade
from pcs.lib.auth.config.types import TokenEntry


def _token_fixture(token):
    return TokenEntry(
        token=token, username=f"user-{token}", creation_date="now"
    )


class FacadeTest(TestCase):
    def setUp(self):
        self.tokens = tuple(f"token{i}" for i in range(3))
        self.facade = Facade(
            tuple(_token_fixture(token) for token in self.tokens)
        )

    def test_non_existing_token(self):
        self.assertIsNone(self.facade.get_user("token3"))

    def test_valid_token(self):
        self.assertEqual(self.facade.get_user("token1"), "user-token1")

    @mock.patch("pcs.lib.auth.config.facade.get_unique_uuid")
    def test_add_user(self, uuid_mock):
        uuid = "unique uuid"
        username = "new_user"
        uuid_mock.return_value = uuid
        self.assertEqual(uuid, self.facade.add_user(username))
        uuid_mock.assert_called_once_with(self.tokens)
        token_entry = self.facade.config[-1]
        self.assertEqual(uuid, token_entry.token)
        self.assertEqual(username, token_entry.username)

    @mock.patch("pcs.lib.auth.config.facade.get_unique_uuid")
    def test_add_existing_user(self, uuid_mock):
        uuid = "unique uuid"
        username = "user-token2"
        self.assertEqual(self.facade.get_user("token2"), username)
        uuid_mock.return_value = uuid
        self.assertEqual(uuid, self.facade.add_user(username))
        uuid_mock.assert_called_once_with(self.tokens)
        token_entry = self.facade.config[-1]
        self.assertEqual(uuid, token_entry.token)
        self.assertEqual(username, token_entry.username)

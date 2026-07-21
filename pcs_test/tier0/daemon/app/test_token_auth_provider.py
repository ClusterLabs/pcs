from unittest import IsolatedAsyncioTestCase, mock

from pcs.daemon.app.auth_provider import (
    NotAuthorizedException,
    TokenAuthProvider,
)
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser


class TokenAuthProviderTest(IsolatedAsyncioTestCase):
    LOGGER_MESSAGE = "Attempting authentication via token"

    def setUp(self):
        self.handler = mock.Mock()
        self.lib_auth_provider = mock.Mock(spec=AuthProvider)
        self.cookie_jar = {"token": "TOKEN", "not_token": "value"}
        self.handler.get_cookie.side_effect = self.cookie_jar.get
        self.mock_logger = mock.Mock(spec_set=["debug"])
        self.provider = TokenAuthProvider(
            self.handler, self.lib_auth_provider, self.mock_logger
        )

    def test_can_handle_request_returns_true_with_cookie(self):
        self.assertTrue(self.provider.can_handle_request())

    def test_can_handle_request_returns_false_without_cookie(self):
        del self.cookie_jar["token"]
        self.assertFalse(self.provider.can_handle_request())

    async def test_auth_user_success(self):
        expected_user = AuthUser("Prokop", ["Buben"])
        self.lib_auth_provider.auth_by_token.return_value = expected_user

        result = await self.provider.auth_user()

        self.assertEqual(result, expected_user)
        self.lib_auth_provider.auth_by_token.assert_called_once_with("TOKEN")
        self.mock_logger.debug.assert_called_once_with(self.LOGGER_MESSAGE)

    async def test_auth_user_error_no_cookie(self):
        del self.cookie_jar["token"]

        with self.assertRaises(NotAuthorizedException):
            await self.provider.auth_user()

        self.mock_logger.debug.assert_has_calls(
            [
                mock.call(self.LOGGER_MESSAGE),
                mock.call(
                    "Credentials for authentication via token not provided"
                ),
            ]
        )
        self.assertEqual(len(self.mock_logger.debug.mock_calls), 2)

    async def test_auth_user_error_login_fails(self):
        self.lib_auth_provider.auth_by_token.return_value = None

        with self.assertRaises(NotAuthorizedException):
            await self.provider.auth_user()

        self.lib_auth_provider.auth_by_token.assert_called_once_with("TOKEN")
        self.mock_logger.debug.assert_called_once_with(self.LOGGER_MESSAGE)

import logging
from unittest import mock

from pcs.daemon.app import auth
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from pcs_test.tier0.daemon.app import fixtures_app

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class AppTest(fixtures_app.AppTest):
    def setUp(self):
        self.auth_provider = AuthProvider(logging.getLogger("test logger"))
        super().setUp()

    def _mock_auth_provider_method(self, method_name, return_value=None):
        method_patcher = mock.patch.object(AuthProvider, method_name)
        self.addCleanup(method_patcher.stop)
        method_mock = method_patcher.start()
        if return_value:
            method_mock.return_value = return_value
        return method_mock

    def get_routes(self):
        return auth.get_routes(
            self.auth_provider,
        )


class Auth(AppTest):
    def setUp(self):
        super().setUp()
        self.auth_provider_mock = self._mock_auth_provider_method(
            "auth_by_username_password"
        )
        self.token = "new token"
        self._mock_auth_provider_method("create_token", self.token)

    def make_auth_request(self):
        return self.post(
            "/remote/auth",
            body={
                "username": fixtures_app.USER,
                "password": fixtures_app.PASSWORD,
            },
        )

    def test_refuse_unknown_user(self):
        self.auth_provider_mock.return_value = None
        self.assertEqual(b"", self.make_auth_request().body)
        self.auth_provider_mock.assert_called_once_with(
            fixtures_app.USER, fixtures_app.PASSWORD
        )

    def test_success(self):
        self.auth_provider_mock.return_value = AuthUser(
            fixtures_app.USER, fixtures_app.GROUPS
        )
        self.assertEqual(
            self.token.encode("utf-8"), self.make_auth_request().body
        )
        self.auth_provider_mock.assert_called_once_with(
            fixtures_app.USER, fixtures_app.PASSWORD
        )

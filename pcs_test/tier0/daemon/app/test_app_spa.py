import logging
import os
from unittest import mock

from pcs.daemon.app import webui
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from pcs_test.tier0.daemon.app import fixtures_app
from pcs_test.tools.misc import get_tmp_dir

LOGIN_BODY = {"username": fixtures_app.USER, "password": fixtures_app.PASSWORD}
PREFIX = "/ui/"

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class AppTest(fixtures_app.AppUiTestMixin):
    def setUp(self):
        self.public_dir = get_tmp_dir("tier0_daemon_app_spa")
        self.spa_dir_path = os.path.join(self.public_dir.name, "ui")
        os.makedirs(self.spa_dir_path)
        self.fallback_path = os.path.join(self.public_dir.name, "fallback.html")
        self.index_path = os.path.join(self.spa_dir_path, "index.html")
        self.index_content = "<html/>"
        with open(self.index_path, "w") as index:
            index.write(self.index_content)
        super().setUp()

    def tearDown(self):
        self.public_dir.cleanup()
        super().tearDown()

    def get_routes(self):
        return webui.get_routes(
            url_prefix=PREFIX,
            app_dir=self.spa_dir_path,
            fallback_page_path=self.fallback_path,
            session_storage=self.session_storage,
            auth_provider=AuthProvider(logging.Logger("test logger")),
        )


class Static(AppTest):
    def test_index(self):
        self.assert_success_response(
            self.get(PREFIX),
            self.index_content,
        )


class Fallback(AppTest):
    def setUp(self):
        super().setUp()
        os.remove(self.index_path)
        self.fallback_content = "fallback"
        with open(self.fallback_path, "w") as index:
            index.write(self.fallback_content)

    def test_index(self):
        self.assert_success_response(
            self.get(PREFIX),
            self.fallback_content,
        )


class Login(AppTest):
    def setUp(self):
        super().setUp()
        auth_provider_patcher = mock.patch.object(
            AuthProvider, "auth_by_username_password"
        )
        self.addCleanup(auth_provider_patcher.stop)
        self.auth_provider_mock = auth_provider_patcher.start()

    def test_login_attempt_failed(self):
        self.auth_provider_mock.return_value = None
        self.assert_unauth_ajax(
            self.post(f"{PREFIX}login", LOGIN_BODY, is_ajax=True)
        )
        self.auth_provider_mock.assert_called_once_with(
            fixtures_app.USER, fixtures_app.PASSWORD
        )

    def test_login_attempt_succeeded(self):
        self.auth_provider_mock.return_value = AuthUser(
            fixtures_app.USER, fixtures_app.GROUPS
        )
        response = self.post(f"{PREFIX}login", LOGIN_BODY, is_ajax=True)
        self.assert_success_response(response, "")
        self.auth_provider_mock.assert_called_once_with(
            fixtures_app.USER, fixtures_app.PASSWORD
        )


class Logout(AppTest):
    def test_can_logout(self):
        session1 = self.create_login_session()
        response = self.get(f"{PREFIX}logout", sid=session1.sid, is_ajax=True)
        self.assert_success_response(response, "OK")
        self.assertIsNone(self.session_storage.get(session1.sid))

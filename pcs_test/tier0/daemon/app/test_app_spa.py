import logging
import os
from unittest import mock

from tornado.httputil import parse_cookie

try:
    from pcs.daemon.app import webui
except ImportError:
    webui = None

from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from pcs_test.tier0.daemon.app import fixtures_app, fixtures_app_webui
from pcs_test.tools.misc import get_tmp_dir, skip_unless_webui_installed

PREFIX = "/ui/"

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


def login_body(username: str, password: str) -> dict[str, str]:
    return {"username": username, "password": password}


class AppTest(fixtures_app_webui.AppTest):
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
        return webui.core.get_routes(
            url_prefix=PREFIX,
            app_dir=self.spa_dir_path,
            fallback_page_path=self.fallback_path,
            session_storage=self.session_storage,
            auth_provider=AuthProvider(logging.getLogger("test logger")),
        )

    def assert_success_response(self, response, expected_body):
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body.decode(), expected_body)

    def assert_sid_in_response(self, response):
        self.assertTrue("Set-Cookie" in response.headers)
        cookie = parse_cookie(response.headers["Set-Cookie"])
        self.assertTrue(webui.auth_provider.PCSD_SESSION in cookie)
        return cookie[webui.auth_provider.PCSD_SESSION]

    def assert_sid_not_in_response(self, response):
        cookie = parse_cookie(response.headers.get("Set-Cookie", ""))
        self.assertFalse(webui.auth_provider.PCSD_SESSION in cookie)


@skip_unless_webui_installed()
class Static(AppTest):
    def test_index(self):
        self.assert_success_response(
            self.get(PREFIX),
            self.index_content,
        )


@skip_unless_webui_installed()
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


@skip_unless_webui_installed()
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

        response = self.post(
            f"{PREFIX}login",
            login_body(fixtures_app.USER, fixtures_app.PASSWORD),
            is_ajax=True,
        )

        self.assert_unauth_ajax(response)
        self.assert_sid_not_in_response(response)
        self.auth_provider_mock.assert_called_once_with(
            fixtures_app.USER, fixtures_app.PASSWORD
        )

    def test_login_attempt_succeeded(self):
        self.auth_provider_mock.return_value = AuthUser(
            fixtures_app.USER, fixtures_app.GROUPS
        )

        response = self.post(
            f"{PREFIX}login",
            login_body(fixtures_app.USER, fixtures_app.PASSWORD),
            is_ajax=True,
        )

        self.assert_success_response(response, "")
        self.assert_sid_in_response(response)
        self.auth_provider_mock.assert_called_once_with(
            fixtures_app.USER, fixtures_app.PASSWORD
        )

    def test_login_with_sid_same_user(self):
        session1 = self.create_login_session()
        self.auth_provider_mock.return_value = AuthUser(
            fixtures_app.USER, fixtures_app.GROUPS
        )

        response = self.post(
            f"{PREFIX}login",
            login_body(fixtures_app.USER, fixtures_app.PASSWORD),
            is_ajax=True,
            sid=session1.sid,
        )

        self.assert_success_response(response, "")
        response_sid = self.assert_sid_in_response(response)
        self.assertEqual(session1.sid, response_sid)
        self.auth_provider_mock.assert_called_once_with(
            fixtures_app.USER, fixtures_app.PASSWORD
        )

    def test_login_with_sid_different_user(self):
        # tests the case when login comes with sid, but the session belongs
        # to different user than the one that is being logged in
        session1 = self.create_login_session()
        self.auth_provider_mock.return_value = AuthUser(
            "different user", fixtures_app.GROUPS
        )

        response = self.post(
            f"{PREFIX}login",
            login_body("different user", fixtures_app.PASSWORD),
            is_ajax=True,
            sid=session1.sid,
        )

        self.assert_success_response(response, "")
        response_sid = self.assert_sid_in_response(response)
        self.assertNotEqual(session1.sid, response_sid)
        self.auth_provider_mock.assert_called_once_with(
            "different user", fixtures_app.PASSWORD
        )


@skip_unless_webui_installed()
class Logout(AppTest):
    def test_can_logout(self):
        session1 = self.create_login_session()
        response = self.get(f"{PREFIX}logout", sid=session1.sid, is_ajax=True)
        self.assert_success_response(response, "OK")
        # check that the cookie is "cleared"
        sid = self.assert_sid_in_response(response)
        self.assertEqual(sid, "")
        self.assertIsNone(self.session_storage.get(session1.sid))

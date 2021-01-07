import logging
import os

from pcs.daemon import auth
from pcs.daemon.app import ui
from pcs_test.tier0.daemon.app import fixtures_app
from pcs_test.tools.misc import (
    create_setup_patch_mixin,
    get_tmp_dir,
)

USER = "user"
PASSWORD = "password"
LOGIN_BODY = {"username": USER, "password": PASSWORD}
PREFIX = "/ui/"

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class AppTest(
    fixtures_app.AppUiTestMixin, create_setup_patch_mixin(ui.app_session)
):
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
        return ui.get_routes(
            url_prefix=PREFIX,
            app_dir=self.spa_dir_path,
            fallback_page_path=self.fallback_path,
            session_storage=self.session_storage,
        )


class Static(AppTest):
    def test_index(self):
        self.assert_success_response(
            self.get(f"{PREFIX}"),
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
            self.get(f"{PREFIX}"),
            self.fallback_content,
        )


class Login(AppTest):
    def setUp(self):
        self.setup_patch("authorize_user", self.authorize_user)
        super().setUp()

    async def authorize_user(self, username, password):
        self.assertEqual(username, USER)
        self.assertEqual(password, PASSWORD)
        return auth.UserAuthInfo(
            username,
            self.user_auth_info.groups,
            is_authorized=self.user_auth_info.valid,
        )

    def test_login_attempt_failed(self):
        self.user_auth_info.valid = False
        self.assert_unauth_ajax(
            self.post(f"{PREFIX}login", LOGIN_BODY, is_ajax=True)
        )

    def test_login_attempt_succeeded(self):
        self.user_auth_info.valid = True
        response = self.post(f"{PREFIX}login", LOGIN_BODY, is_ajax=True)
        self.assert_success_response(
            response,
            self.session_storage.provide(self.extract_sid(response)).ajax_id,
        )


class Logout(AppTest):
    def test_can_logout(self):
        session1 = self.create_login_session()
        response = self.get(f"{PREFIX}logout", sid=session1.sid, is_ajax=True)
        self.assert_success_response(response, "OK")
        self.assertFalse(
            self.session_storage.provide(session1.sid).is_authenticated
        )

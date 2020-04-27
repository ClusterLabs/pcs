import logging
import os

from pcs_test.tools.misc import (
    create_setup_patch_mixin,
    get_tmp_dir,
)
from pcs_test.tier0.daemon.app import fixtures_app

from pcs.daemon import auth, ruby_pcsd
from pcs.daemon.app import sinatra_ui


USER = "user"
PASSWORD = "password"
LOGIN_BODY = {"username": USER, "password": PASSWORD}

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class AppTest(
    fixtures_app.AppUiTestMixin,
    create_setup_patch_mixin(sinatra_ui.app_session),
):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA_GUI)
        self.public_dir = get_tmp_dir("tier0_daemon_app_gui")
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.public_dir.cleanup()

    def get_routes(self):
        return sinatra_ui.get_routes(
            self.session_storage, self.wrapper, self.public_dir.name,
        )

    def assert_is_redirect(self, response, location, status_code=302):
        self.assert_headers_contains(response.headers, {"Location": location})
        self.assertEqual(response.code, status_code)


class Login(AppTest):
    # pylint: disable=too-many-ancestors
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

    def test_get_uses_wrapper(self):
        self.assert_wrappers_response(self.get("/login"))

    def test_login_attempt_failed(self):
        self.user_auth_info.valid = False
        response = self.post("/login", LOGIN_BODY)
        self.assert_is_redirect(response, "/login", 303)
        self.assert_is_redirect(
            self.get("/", sid=self.extract_sid(response)),  # not logged
            "/login",
        )

    def test_login_attempt_failed_ajax(self):
        self.user_auth_info.valid = False
        self.assert_unauth_ajax(self.post("/login", LOGIN_BODY, is_ajax=True))

    def test_login_attempt_succeeded(self):
        self.assert_is_redirect(self.get("/"), "/login")
        self.user_auth_info.valid = True
        response = self.post("/login", LOGIN_BODY)
        self.assert_is_redirect(response, "/manage", status_code=303)
        # it is logged now
        self.assert_wrappers_response(
            self.get("/", sid=self.extract_sid(response))
        )

    def test_login_attempt_succeeded_ajax(self):
        self.user_auth_info.valid = True
        response = self.post("/login", LOGIN_BODY, is_ajax=True)
        self.assert_success_response(
            response,
            self.session_storage.provide(self.extract_sid(response)).ajax_id,
        )


class SinatraGuiProtected(AppTest):
    # pylint: disable=too-many-ancestors
    def test_no_logged_redirects_to_login(self):
        self.assert_is_redirect(self.get("/"), "/login")

    def test_take_result_from_ruby(self):
        self.assert_wrappers_response(
            self.get("/", sid=self.create_login_session().sid)
        )


class SinatraAjaxProtected(AppTest):
    # pylint: disable=too-many-ancestors
    def test_deal_without_authentication(self):
        self.assert_unauth_ajax(self.get("/some-ajax", is_ajax=True))

    def test_deal_without_ajax(self):
        session1 = self.create_login_session()
        response = self.get("/some-ajax", sid=session1.sid)
        self.assert_unauth_ajax(response)
        self.assert_session_in_response(response, session1.sid)

    def test_take_result_from_ruby(self):
        session1 = self.create_login_session()
        response = self.get("/some-ajax", sid=session1.sid, is_ajax=True)
        self.assert_wrappers_response(response)
        self.assert_session_in_response(response, session1.sid)


class Logout(AppTest):
    # pylint: disable=too-many-ancestors
    def test_no_ajax(self):
        session1 = self.create_login_session()
        response = self.get("/logout", sid=session1.sid)
        self.assert_is_redirect(response, "/login")
        self.assertFalse(
            self.session_storage.provide(session1.sid).is_authenticated
        )

    def test_with_ajax(self):
        session1 = self.create_login_session()
        response = self.get("/logout", sid=session1.sid, is_ajax=True)
        self.assert_success_response(response, "OK")
        self.assertFalse(
            self.session_storage.provide(session1.sid).is_authenticated
        )


class Static(AppTest):
    # pylint: disable=too-many-ancestors
    def setUp(self):
        super().setUp()
        self.css_dir_path = os.path.join(self.public_dir.name, "css")
        os.makedirs(self.css_dir_path)
        self.style_path = os.path.join(self.css_dir_path, "style.css")
        self.css = "body{color:black};"
        with open(self.style_path, "w") as style:
            style.write(self.css)

    def test_css(self):
        self.assert_success_response(self.get("/css/style.css"), self.css)

import logging
import os

from tornado.httputil import parse_cookie

from pcs.daemon import session, app_session
from pcs.daemon import app_gui, auth, ruby_pcsd
from pcs.test.tools.misc import(
    create_setup_patch_mixin,
    get_test_resource as rc,
)
from pcs.daemon.test import fixtures_app


USER = "user"
PASSWORD = "password"
GROUPS = ["hacluster"]
LOGIN_BODY = {"username": USER, "password": PASSWORD}
PUBLIC_DIR = rc("web_public")
CSS_DIR = os.path.join(PUBLIC_DIR, "css")

if not os.path.exists(CSS_DIR):
    os.makedirs(CSS_DIR)

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)

class UserAuthInfo:
    # pylint: disable=too-few-public-methods
    valid = False
    groups = []

class AppTest(
    fixtures_app.AppTest, create_setup_patch_mixin(app_gui.app_session)
):
    def setUp(self):
        self.user_auth_info = UserAuthInfo()
        self.groups_valid = True
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA_GUI)
        self.session_storage = session.Storage(lifetime_seconds=10)
        self.setup_patch("check_user_groups", self.check_user_groups)
        super().setUp()

    async def check_user_groups(self, username):
        self.assertEqual(username, USER)
        return auth.UserAuthInfo(
            username,
            self.user_auth_info.groups,
            is_authorized=self.groups_valid
        )

    def get_routes(self):
        return app_gui.get_routes(
            self.session_storage,
            self.wrapper,
            PUBLIC_DIR,
        )

    def extract_sid(self, response):
        return self.assert_session_in_response(response)

    def fetch(self, path, raise_error=False, **kwargs):
        if "sid" in kwargs:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["Cookie"] = (
                f"{app_session.PCSD_SESSION}={kwargs['sid']}"
            )
            del kwargs["sid"]

        if "is_ajax" in kwargs:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["X-Requested-With"] = "XMLHttpRequest"
            del kwargs["is_ajax"]


        if "follow_redirects" not in kwargs:
            kwargs["follow_redirects"] = False

        return super().fetch(path, raise_error=raise_error, **kwargs)

    def create_login_session(self):
        return self.session_storage.login(
            sid=None,
            username=USER,
            groups=GROUPS
        )

    def assert_session_in_response(self, response, sid=None):
        self.assertTrue("Set-Cookie" in response.headers)
        cookie = parse_cookie(response.headers["Set-Cookie"])
        self.assertTrue(app_session.PCSD_SESSION, cookie)
        if sid:
            self.assertEqual(cookie[app_session.PCSD_SESSION], sid)
        return cookie[app_session.PCSD_SESSION]

    def assert_is_redirect(self, response, location, status_code=302):
        self.assert_headers_contains(response.headers, {"Location": location})
        self.assertEqual(response.code, status_code)

    def assert_unauth_ajax(self, response):
        self.assertEqual(response.code, 401)
        self.assertEqual(response.body, b'{"notauthorized":"true"}')

    def assert_success_response(self, response, expected_body):
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body.decode(), expected_body)

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
            is_authorized=self.user_auth_info.valid
        )

    def test_get_uses_wrapper(self):
        self.assert_wrappers_response(self.get("/login"))

    def test_login_attempt_failed(self):
        self.user_auth_info.valid = False
        response = self.post('/login', LOGIN_BODY)
        self.assert_is_redirect(response, "/login", 303)
        self.assert_is_redirect(
            self.get('/', sid=self.extract_sid(response)), # not logged
            "/login"
        )

    def test_login_attempt_failed_ajax(self):
        self.user_auth_info.valid = False
        self.assert_unauth_ajax(self.post('/login', LOGIN_BODY, is_ajax=True))

    def test_login_attempt_succeeded(self):
        self.assert_is_redirect(self.get('/'), "/login")
        self.user_auth_info.valid = True
        response = self.post('/login', LOGIN_BODY)
        self.assert_is_redirect(response, "/manage", status_code=303)
        #it is logged now
        self.assert_wrappers_response(
            self.get('/', sid=self.extract_sid(response))
        )

    def test_login_attempt_succeeded_ajax(self):
        self.user_auth_info.valid = True
        response = self.post('/login', LOGIN_BODY, is_ajax=True)
        self.assert_success_response(
            response,
            self.session_storage.provide(self.extract_sid(response)).ajax_id
        )

class SinatraGuiProtected(AppTest):
    # pylint: disable=too-many-ancestors
    def test_no_logged_redirects_to_login(self):
        self.assert_is_redirect(self.get('/'), "/login")

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

class LoginStatus(AppTest):
    # pylint: disable=too-many-ancestors
    def test_not_authenticated(self):
        self.assert_unauth_ajax(self.get("/login-status"))
        self.assert_unauth_ajax(self.get("/login-status", is_ajax=True))

    def test_authenticated(self):
        session1 = self.create_login_session()
        response = self.get("/login-status", sid=session1.sid, is_ajax=True)
        self.assert_success_response(response, session1.ajax_id)
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
        self.style_path = os.path.join(CSS_DIR, "style.css")
        self.css = "body{color:black};"
        with open(self.style_path, "w") as style:
            style.write(self.css)
        super().setUp()

    def tearDown(self):
        os.remove(self.style_path)
        super().tearDown()

    def test_css(self):
        self.assert_success_response(self.get("/css/style.css"), self.css)

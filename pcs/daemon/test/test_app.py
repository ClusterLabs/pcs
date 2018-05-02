import logging
import os.path
import re
from base64 import b64encode
from urllib.parse import urlencode
from pprint import pformat

from tornado.httputil import HTTPHeaders, parse_cookie
from tornado.locks import Lock
from tornado.testing import AsyncHTTPTestCase

from pcs.daemon import session, ruby_pcsd, http_server
from pcs.daemon import app, auth
from pcs.test.tools.misc import(
    create_setup_patch_mixin,
    get_test_resource as rc,
)


USER = "user"
PASSWORD = "password"
GROUPS=["hacluster"]
LOGIN_BODY ={"username": USER, "password": PASSWORD}
PUBLIC_DIR = rc("web_public")

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)

class RubyPcsdWrapper(ruby_pcsd.Wrapper):
    def __init__(self):
        #pylint: disable=super-init-not-called
        self.request_type = ruby_pcsd.SINATRA_GUI
        self.status_code = 200
        self.headers = {"Some": "value"}
        self.body = b"Success action"

    async def run_ruby(self, request_type, request=None):
        if request_type != self.request_type:
            raise AssertionError(
                f"Wrong request type: expected '{self.request_type}'"
                f" but was {request_type}"
            )
        return {
            "headers": self.headers,
            "status": self.status_code,
            "body": b64encode(self.body),
        }

class HttpsServerManage(http_server.HttpsServerManage):
    def __init__(self):
        #pylint: disable=super-init-not-called
        pass

class AppTest(AsyncHTTPTestCase):
    def setUp(self):
        self.wrapper = RubyPcsdWrapper()
        self.session_storage = session.Storage(lifetime_seconds=10)
        self.lock = Lock()
        super().setUp()

    def get_app(self):
        return app.make_app(
            self.session_storage,
            self.wrapper,
            self.lock,
            PUBLIC_DIR,
            HttpsServerManage(),
        )

    def extract_sid(self, response):
        return self.assert_session_in_response(response)

    def fetch(self, path, **kwargs):
        if "sid" in kwargs:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["Cookie"] =  (
                f"{session.PCSD_SESSION}={kwargs['sid']}"
            )
            del kwargs["sid"]

        if "is_ajax" in kwargs:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["X-Requested-With"] = "XMLHttpRequest"
            del kwargs["is_ajax"]


        if "follow_redirects" not in kwargs:
            kwargs["follow_redirects"] = False

        return super().fetch(path, **kwargs)

    def post(self, path, body, **kwargs):
        kwargs.update({
            "method": "POST",
            "body": urlencode(body),
        })
        return self.fetch(path, **kwargs)

    def get(self, path, **kwargs):
        return self.fetch(path, **kwargs)

    def create_login_session(self):
        return self.session_storage.login(
            sid=None,
            username=USER,
            groups=GROUPS
        )

    def assert_session_in_response(self, response, sid=None):
        self.assertTrue("Set-Cookie" in response.headers)
        cookie = parse_cookie(response.headers["Set-Cookie"])
        self.assertTrue(session.PCSD_SESSION, cookie)
        if sid:
            self.assertEqual(cookie[session.PCSD_SESSION], sid)
        return cookie[session.PCSD_SESSION]


    def assert_headers_contains(self, headers: HTTPHeaders, contained: dict):
        self.assertTrue(
            all(item in headers.get_all() for item in contained.items()),
            "Headers does not contain expected headers"
            "\n  Expected headers:"
            f"\n    {pformat(contained, indent=6)}"
            "\n  All headers:"
            f"\n    {pformat(dict(headers.get_all()), indent=6)}"
        )

    def assert_wrappers_response(self, response):
        self.assertEqual(response.code, self.wrapper.status_code)
        self.assert_headers_contains(response.headers, self.wrapper.headers)
        self.assertEqual(response.body, self.wrapper.body)

    def assert_is_redirect(self, response, location, status_code=302):
        self.assert_headers_contains(response.headers, {"Location": location})
        self.assertEqual(response.code, status_code)

    def assert_unauth_ajax(self, response):
        self.assertEqual(response.code, 401)
        self.assertEqual(response.body, b'{"notauthorized":"true"}')

    def assert_success_response(self, response, expected_body):
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body.decode(), expected_body)

class UserAuthInfo:
    valid = False
    groups = []

class Login(AppTest, create_setup_patch_mixin(app)):
    def setUp(self):
        super().setUp()
        self.user_auth_info = UserAuthInfo()
        self.setup_patch("authorize_user", self.authorize_user)
        super().setUp()

    async def authorize_user(self, username, password):
        self.assertEqual(username, USER)
        self.assertEqual(password, PASSWORD)
        if not self.user_auth_info.valid:
            return None
        return auth.IdentifiedUser(username, self.user_auth_info.groups)

    def test_get_uses_wrapper(self):
        self.assert_wrappers_response(self.get("/login"))

    def test_login_attempt_failed(self):
        self.user_auth_info.valid=False
        response = self.post('/login', LOGIN_BODY)
        self.assert_is_redirect(response, "/login", 303)
        self.assert_is_redirect(
            self.get('/', sid=self.extract_sid(response)), # not logged
            "/login"
        )

    def test_login_attempt_failed_ajax(self):
        self.user_auth_info.valid=False
        self.assert_unauth_ajax(self.post('/login', LOGIN_BODY, is_ajax=True))

    def test_login_attempt_succeeded(self):
        self.assert_is_redirect(self.get('/'), "/login")
        self.user_auth_info.valid=True
        response = self.post('/login', LOGIN_BODY)
        self.assert_is_redirect(response, "/manage", status_code=303)
        #it is logged now
        self.assert_wrappers_response(
            self.get('/', sid=self.extract_sid(response))
        )

    def test_login_attempt_succeeded_ajax(self):
        self.user_auth_info.valid=True
        response = self.post('/login', LOGIN_BODY, is_ajax=True)
        self.assert_success_response(
            response,
            self.session_storage.provide(self.extract_sid(response)).ajax_id
        )

class SinatraGuiProtected(AppTest):
    def test_no_logged_redirects_to_login(self):
        self.assert_is_redirect(self.get('/'), "/login")

    def test_take_result_from_ruby(self):
        self.assert_wrappers_response(
            self.get("/", sid=self.create_login_session().sid)
        )

class SinatraAjaxProtected(AppTest):
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

class SinatraRemote(AppTest):
    def test_take_result_from_ruby(self):
        self.wrapper.request_type = ruby_pcsd.SINATRA_REMOTE
        self.assert_wrappers_response(self.get("/remote/"))

class LoginStatus(AppTest):
    def test_not_authenticated(self):
        self.assert_unauth_ajax(self.get("/login-status"))
        self.assert_unauth_ajax(self.get("/login-status", is_ajax=True))

    def test_authenticated(self):
        session1 = self.create_login_session()
        response = self.get("/login-status", sid=session1.sid, is_ajax=True)
        self.assert_success_response(response, session1.ajax_id)
        self.assert_session_in_response(response, session1.sid)

class Logout(AppTest):
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
    def test_css(self):
        with open(os.path.join(PUBLIC_DIR, "css/style.css")) as style:
            self.assert_success_response(
                self.get("/css/style.css"),
                style.read()
            )

class SyncConfigMutualExclusive(AppTest):
    def setUp(self):
        super().setUp()
        self.wrapper.request_type = ruby_pcsd.SINATRA_REMOTE

    def fetch_set_sync_options(self, method):
        kwargs = (
            dict(method=method, body=urlencode({})) if method == "POST"
            else dict(method=method)
        )
        self.http_client.fetch(
            self.get_url("/remote/set_sync_options"),
            self.stop,
            **kwargs
        )
        # Without lock the timeout should be enough to finish task.  With the
        # lock it should raise because of timeout. The same timeout is used for
        # noticing differences between test with and test without lock.  The
        # timeout is so short to prevent unnecessary slowdown.
        return self.wait(timeout=0.05)

    def check_call_wrapper_without_lock(self, method):
        self.assert_wrappers_response(self.fetch_set_sync_options(method))

    def check_locked(self, method):
        self.lock.acquire()
        try:
            self.fetch_set_sync_options(method)
        except AssertionError as e:
            self.assertTrue(re.match(".*time.*out.*", str(e)) is not None)
            # The http_client timeouted because of lock and this is how we test
            # the locking function. However event loop on the server side should
            # finish. So we release the lock and the request successfully
            # finish.
            self.lock.release()
        else:
            raise AssertionError("Timeout not raised")

    def test_get_not_locked(self):
        self.check_call_wrapper_without_lock("GET")

    def test_get_locked(self):
        self.check_locked("GET")

    def test_post_not_locked(self):
        self.check_call_wrapper_without_lock("POST")

    def test_post_locked(self):
        self.check_locked("POST")

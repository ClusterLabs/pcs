from pprint import pformat
from urllib.parse import urlencode

from tornado.httputil import (
    HTTPHeaders,
    parse_cookie,
)
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from pcs.daemon import ruby_pcsd
from pcs.daemon.app.webui import session
from pcs.daemon.app.webui.auth import PCSD_SESSION

USER = "user"
GROUPS = ["group1", "group2"]
PASSWORD = "password"


class RubyPcsdWrapper(ruby_pcsd.Wrapper):
    def __init__(self, request_type):
        # pylint: disable=super-init-not-called
        self.request_type = request_type
        self.status_code = 200
        self.headers = {"Some": "value"}
        self.body = b"Success action"

    async def run_ruby(
        self,
        request_type,
        http_request=None,
        payload=None,
    ):
        if request_type != self.request_type:
            raise AssertionError(
                f"Wrong request type: expected '{self.request_type}'"
                f" but was {request_type}"
            )
        return {
            "headers": self.headers,
            "status": self.status_code,
            "body": self.body,
        }


class AppTest(AsyncHTTPTestCase):
    wrapper = None

    def get_app(self):
        return Application(self.get_routes())

    def get_routes(self):
        # pylint: disable=no-self-use
        return []

    def fetch(self, path, raise_error=False, **kwargs):
        if "follow_redirects" not in kwargs:
            kwargs["follow_redirects"] = False
        response = super().fetch(path, raise_error=raise_error, **kwargs)
        # "Strict-Transport-Security" header is expected in every response
        self.assertTrue(
            "Strict-Transport-Security" in response.headers,
            f"No 'Strict-Transport-Security' header in response for '{path}'",
        )
        return response

    def post(self, path, body, **kwargs):
        kwargs.update(
            {
                "method": "POST",
                "body": urlencode(body),
            }
        )
        return self.fetch(path, **kwargs)

    def get(self, path, **kwargs):
        return self.fetch(path, **kwargs)

    def assert_headers_contains(self, headers: HTTPHeaders, contained: dict):
        self.assertTrue(
            all(item in headers.get_all() for item in contained.items()),
            "Headers does not contain expected headers"
            "\n  Expected headers:"
            f"\n    {pformat(contained, indent=6)}"
            "\n  All headers:"
            f"\n    {pformat(dict(headers.get_all()), indent=6)}",
        )

    def assert_wrappers_response(self, response):
        self.assertEqual(response.code, self.wrapper.status_code)
        self.assert_headers_contains(response.headers, self.wrapper.headers)
        self.assertEqual(response.body, self.wrapper.body)


class AppUiTestMixin(AppTest):
    def setUp(self):
        self.session_storage = session.Storage(lifetime_seconds=10)
        super().setUp()

    def assert_session_in_response(self, response, sid=None):
        self.assertTrue("Set-Cookie" in response.headers)
        cookie = parse_cookie(response.headers["Set-Cookie"])
        self.assertTrue(PCSD_SESSION, cookie)
        if sid:
            self.assertEqual(cookie[PCSD_SESSION], sid)
        return cookie[PCSD_SESSION]

    def fetch(self, path, raise_error=False, **kwargs):
        if "sid" in kwargs:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["Cookie"] = f"{PCSD_SESSION}={kwargs['sid']}"
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
        return self.session_storage.login(USER)

    def assert_success_response(self, response, expected_body):
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body.decode(), expected_body)

    def assert_unauth_ajax(self, response):
        self.assertEqual(response.code, 401)
        self.assertEqual(response.body, b'{"notauthorized":"true"}')

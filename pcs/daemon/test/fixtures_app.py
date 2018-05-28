from base64 import b64encode
from pprint import pformat
from urllib.parse import urlencode

from tornado.httputil import HTTPHeaders
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from pcs.daemon import ruby_pcsd


class RubyPcsdWrapper(ruby_pcsd.Wrapper):
    def __init__(self, request_type):
        #pylint: disable=super-init-not-called
        self.request_type = request_type
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

class AppTest(AsyncHTTPTestCase):
    # pylint: disable=abstract-method
    def get_app(self):
        return Application(self.get_routes())

    def get_routes(self):
        return []

    def fetch(self, path, **kwargs):
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

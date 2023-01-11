import json
import logging
from base64 import b64encode
from unittest import (
    TestCase,
    mock,
)
from urllib.parse import urlencode

from tornado.httputil import (
    HTTPHeaders,
    HTTPServerRequest,
)
from tornado.testing import (
    AsyncTestCase,
    gen_test,
)
from tornado.web import HTTPError

from pcs.daemon import ruby_pcsd
from pcs.lib.auth.types import AuthUser

from pcs_test.tools.misc import create_patcher
from pcs_test.tools.misc import get_test_resource as rc

# Don't write errors to test output.
logging.getLogger("pcs.daemon").setLevel(logging.CRITICAL)


def create_wrapper():
    return ruby_pcsd.Wrapper(rc("/path/to/ruby_socket"))


def create_http_request():
    return HTTPServerRequest(
        method="POST",
        uri="/pcsd/uri",
        headers=HTTPHeaders({"Cookie": "cookie1=first;cookie2=second"}),
        body=str.encode(urlencode({"post-key": "post-value"})),
        host="pcsd-host:2224",
    )


patch_ruby_pcsd = create_patcher(ruby_pcsd)


class RunRuby(AsyncTestCase):
    def setUp(self):
        self.ruby_response = ""
        self.request = ruby_pcsd.RubyDaemonRequest(ruby_pcsd.SYNC_CONFIGS)
        self.wrapper = create_wrapper()
        patcher = mock.patch.object(
            self.wrapper, "send_to_ruby", self.send_to_ruby
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        super().setUp()

    async def send_to_ruby(self, ruby_request):
        self.assertEqual(ruby_request, self.request)
        return self.ruby_response

    def set_run_result(self, run_result):
        self.ruby_response = json.dumps({**run_result, "logs": []})

    def assert_sinatra_result(self, result, headers, status, body):
        self.assertEqual(result.headers, headers)
        self.assertEqual(result.status, status)
        self.assertEqual(result.body, str.encode(body))

    @gen_test
    def test_correct_sending(self):
        run_result = {"next": 10}
        self.set_run_result(run_result)
        result = yield self.wrapper.run_ruby(ruby_pcsd.SYNC_CONFIGS)
        self.assertEqual(result["next"], run_result["next"])

    @gen_test
    def test_error_from_ruby(self):
        with self.assertRaises(HTTPError):
            yield self.wrapper.run_ruby(ruby_pcsd.SYNC_CONFIGS)

    @gen_test
    def test_sync_config_shortcut_success(self):
        _next = 10
        self.set_run_result({"next": _next})
        result = yield self.wrapper.sync_configs()
        self.assertEqual(result, _next)

    @patch_ruby_pcsd("now", return_value=0)
    @gen_test
    def test_sync_config_shorcut_fail(self, now):
        # pylint: disable=unused-argument
        result = yield self.wrapper.sync_configs()
        self.assertEqual(result, ruby_pcsd.DEFAULT_SYNC_CONFIG_DELAY)

    @gen_test
    def test_request(self):
        headers = {"some": "header"}
        status = 200
        body = "content"
        user = "user"
        groups = ["hacluster"]
        self.set_run_result(
            {
                "headers": headers,
                "status": status,
                "body": b64encode(str.encode(body)).decode(),
            }
        )
        http_request = create_http_request()
        self.request = ruby_pcsd.RubyDaemonRequest(
            ruby_pcsd.SINATRA,
            http_request,
            {
                "username": user,
                "groups": groups,
            },
        )
        result = yield self.wrapper.request(
            AuthUser(username=user, groups=groups), http_request
        )
        self.assert_sinatra_result(result, headers, status, body)


class ProcessResponseLog(TestCase):
    @patch_ruby_pcsd("log.from_external_source")
    @patch_ruby_pcsd("next", mock.Mock(return_value=1))
    def test_put_correct_values_to_log(self, from_external_source):
        # pylint: disable=no-self-use
        ruby_pcsd.process_response_logs(
            [
                {
                    "level": "FATAL",
                    "timestamp_usec": 1234567890,
                    "message": "ruby_message",
                }
            ]
        )
        from_external_source.assert_called_once_with(
            level=logging.CRITICAL,
            created=1234.56789,
            usecs=567890,
            message="ruby_message",
            group_id=1,
        )

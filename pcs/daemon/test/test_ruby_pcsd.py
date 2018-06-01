import json
import logging
from base64 import b64encode
from unittest import TestCase, mock
from urllib.parse import urlencode

from tornado.httputil import HTTPServerRequest
from tornado.testing import AsyncTestCase, gen_test
from tornado.web import HTTPError

from pcs.daemon import ruby_pcsd
from pcs.test.tools.misc import create_patcher,  get_test_resource as rc

# Don't write errors to test output.
logging.getLogger("pcs.daemon").setLevel(logging.CRITICAL)

def create_wrapper():
    return ruby_pcsd.Wrapper(
        rc("/path/to/gem_home"),
        rc("/path/to/pcsd/cmdline/entry"),
    )

def create_http_request():
    return HTTPServerRequest(
        method="POST",
        uri="/pcsd/uri",
        headers={"Cookie": "cookie1=first;cookie2=second"},
        body=str.encode(urlencode({"post-key": "post-value"})),
        host="pcsd-host:2224"
    )

class GetSinatraRequest(TestCase):
    def test_translate_request(self):
        self.maxDiff = None
        self.assertEqual(
            create_wrapper().get_sinatra_request(create_http_request()),
            {
                'env': {
                    'HTTPS': 'off',
                    'HTTP_ACCEPT': '*/*',
                    'HTTP_COOKIE': 'cookie1=first;cookie2=second',
                    'HTTP_HOST': 'pcsd-host:2224',
                    'HTTP_VERSION': 'HTTP/1.0',
                    'PATH_INFO': '/pcsd/uri',
                    'QUERY_STRING': '',
                    'REMOTE_ADDR': None, # It requires complicated request args
                    'REMOTE_HOST': 'pcsd-host:2224',
                    'REQUEST_METHOD': 'POST',
                    'REQUEST_PATH': '/pcsd/uri',
                    'REQUEST_URI': 'http://pcsd-host:2224/pcsd/uri',
                    'SCRIPT_NAME': '',
                    'SERVER_NAME': 'pcsd-host',
                    'SERVER_PORT': 2224,
                    'SERVER_PROTOCOL': 'HTTP/1.0',
                    'rack.input': 'post-key=post-value'
                }
            }
        )

patch_ruby_pcsd = create_patcher(ruby_pcsd)

class RunRuby(AsyncTestCase):
    def setUp(self):
        self.stdout = ""
        self.stderr = ""
        self.request = self.create_request()
        self.wrapper = create_wrapper()
        patcher = mock.patch.object(
            self.wrapper,
            "send_to_ruby",
            self.send_to_ruby
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        super().setUp()

    async def send_to_ruby(self, request_json):
        self.assertEqual(json.loads(request_json), self.request)
        return self.stdout, self.stderr

    def create_request(self, type=ruby_pcsd.SYNC_CONFIGS):
        return {"type": type}

    def set_run_result(self, run_result):
        self.stdout = json.dumps({**run_result, "logs": []})

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
        next = 10
        self.set_run_result({"next": next})
        result = yield self.wrapper.sync_configs()
        self.assertEqual(result, next)

    @patch_ruby_pcsd("now", return_value=0)
    @gen_test
    def test_sync_config_shorcut_fail(self, now):
        result = yield self.wrapper.sync_configs()
        self.assertEqual(result, ruby_pcsd.DEFAULT_SYNC_CONFIG_DELAY)

    @gen_test
    def test_request_remote(self):
        headers = {"some": "header"}
        status = 200
        body = "content"
        self.set_run_result({
            "headers": headers,
            "status": status,
            "body": b64encode(str.encode(body)).decode(),
        })
        http_request = create_http_request()
        self.request = {
            **self.create_request(ruby_pcsd.SINATRA_REMOTE),
            **self.wrapper.get_sinatra_request(http_request),
        }
        result = yield self.wrapper.request_remote(http_request)
        self.assert_sinatra_result(result, headers, status, body)

    @gen_test
    def test_request_gui(self):
        headers = {"some": "header"}
        status = 200
        body = "content"

        user = "user"
        groups = ["hacluster"]
        is_authenticated = True

        self.set_run_result({
            "headers": headers,
            "status": status,
            "body": b64encode(str.encode(body)).decode(),
        })
        http_request = create_http_request()
        self.request = {
            **self.create_request(ruby_pcsd.SINATRA_GUI),
            **self.wrapper.get_sinatra_request(http_request),
            "session": {
                "username": user,
                "groups": groups,
                "is_authenticated": is_authenticated,
            }
        }
        result = yield self.wrapper.request_gui(
            http_request,
            user=user,
            groups=groups,
            is_authenticated=is_authenticated,
        )
        self.assert_sinatra_result(result, headers, status, body)

class ProcessResponseLog(TestCase):
    @patch_ruby_pcsd("log.from_external_source")
    @patch_ruby_pcsd("next", mock.Mock(return_value=1))
    def test_put_correct_values_to_log(self, from_external_source):
        ruby_pcsd.process_response_logs([{
            "level": "FATAL",
            "timestamp_usec": 1234567890,
            "message": "ruby_message",
        }])
        from_external_source.assert_called_once_with(
            level=logging.CRITICAL,
            created=1234.56789,
            usecs=567890,
            message="ruby_message",
            group_id=1,
        )

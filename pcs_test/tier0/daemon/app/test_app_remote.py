import base64
import logging
from unittest import mock
from urllib.parse import urlencode

from tornado.locks import Lock
from tornado.util import TimeoutError as TornadoTimeoutError

from pcs.daemon import http_server, ruby_pcsd
from pcs.daemon.app import sinatra_remote

from pcs_test.tier0.daemon.app import fixtures_app
from pcs_test.tier0.daemon.app.fixtures_app_api import MockAuthProviderFactory

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class AppTest(fixtures_app.AppTest):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA)
        self.https_server_manage = mock.MagicMock(
            spec_set=http_server.HttpsServerManage
        )
        self.lock = Lock()
        self.api_auth_provider_factory = MockAuthProviderFactory()
        super().setUp()

    def get_routes(self):
        return sinatra_remote.get_routes(
            self.api_auth_provider_factory,
            self.wrapper,
            self.lock,
            self.https_server_manage,
        )


class SetCerts(AppTest):
    def setUp(self):
        super().setUp()
        self.headers = {"Cookie": "token=1234"}

    def test_it_asks_for_cert_reload_if_ruby_succeeds(self):
        self.wrapper.status_code = 200
        self.wrapper.body = b"success"
        # body is irrelevant
        self.assert_wrappers_response(
            self.post("/remote/set_certs", body={}, headers=self.headers)
        )
        self.https_server_manage.reload_certs.assert_called_once()

    def test_it_not_asks_for_cert_reload_if_ruby_fail(self):
        self.wrapper.status_code = 400
        self.wrapper.body = b"cannot save ssl certificate without ssl key"
        # body is irrelevant
        self.assert_wrappers_response(
            self.post("/remote/set_certs", body={}, headers=self.headers)
        )
        self.https_server_manage.reload_certs.assert_not_called()


class SinatraRemote(AppTest):
    def setUp(self):
        super().setUp()
        self.headers = {"Cookie": "token=1234"}

    def test_take_result_from_ruby(self):
        self.assert_wrappers_response(
            self.get("/remote/", headers=self.headers)
        )

        self.api_auth_provider_factory.provider.auth_user.assert_called_once_with()
        self.assertTrue(self.wrapper.was_run_ruby_called)
        self.assertEqual(
            self.wrapper.run_ruby_payload,
            {"username": "hacluster", "groups": ["haclient"]},
        )

    def test_auth_not_authorized(self):
        self.api_auth_provider_factory.auth_result = "not_authorized"

        response = self.get("/remote/", headers=self.headers)

        self.assertEqual(response.code, 401)
        self.api_auth_provider_factory.provider.auth_user.assert_called_once_with()
        self.assertFalse(self.wrapper.was_run_ruby_called)

    def test_success_desired_user(self):
        groups_encoded = base64.b64encode(
            "haclient wheel square".encode("utf-8")
        ).decode("utf-8")
        self.headers["Cookie"] = (
            self.headers["Cookie"]
            + ";CIB_user=foo"
            + f";CIB_user_groups={groups_encoded}"
        )
        self.assert_wrappers_response(
            self.get("/remote/", headers=self.headers)
        )

        self.api_auth_provider_factory.provider.auth_user.assert_called_once_with()
        self.assertTrue(self.wrapper.was_run_ruby_called)
        self.assertEqual(
            self.wrapper.run_ruby_payload,
            {"username": "foo", "groups": ["haclient", "wheel", "square"]},
        )


class SyncConfigMutualExclusive(AppTest):
    """
    This class contains tests that the request handler of url
    `/remote/set_sync_options` waits until current synchronization is done (i.e.
    respects lock).

    Every test simply calls url `/remote/set_sync_options`. If there is no lock
    (it means that synchronization is not in progress) the handler gives
    response. If there is a lock handler waits and the request fails because of
    timeout and test detects an expected timeout error.
    """

    def fetch_set_sync_options(self, method):
        def fetch_sync_options():
            return self.http_client.fetch(
                self.get_url("/remote/set_configs"), **kwargs
            )

        kwargs = (
            dict(method=method, body=urlencode({}))
            if method == "POST"
            else dict(method=method)
        )
        kwargs["headers"] = {"Cookie": "token=1234"}

        # Without lock the timeout should be enough to finish task. With the
        # lock it should raise because of timeout. The same timeout is used for
        # noticing differences between test with and test without lock.
        # The timeout needs to be long enough for the test to fit into it even
        # if running on a slower machine. And it should be short enough not to
        # make the test run unnecessary long.
        return self.io_loop.run_sync(fetch_sync_options, timeout=2.5)

    def check_call_wrapper_without_lock(self, method):
        self.assert_wrappers_response(self.fetch_set_sync_options(method))

    def check_locked(self, method):
        self.lock.acquire()
        try:
            self.fetch_set_sync_options(method)
        except TornadoTimeoutError:
            # The http_client timeouted because of lock and this is how we test
            # the locking function. However event loop on the server side should
            # finish. So we release the lock and the request successfully
            # finish.
            self.lock.release()
            # Now, there is an unfinished request. It was started by calling
            # fetch("/remote/set_sync_options") (in self.fetch_set_sync_options)
            # and it was waiting for the lock to be released.
            # The lock was released and the request is able to be finished now.
            # So, io_loop needs an opportunity to execute the rest of request.
            # Next line runs io_loop to finish hanging request. Without this an
            # error appears during calling
            # `self.http_server.close_all_connections` in tearDown...
            self.io_loop.run_sync(lambda: None)
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

import logging
from unittest import mock
from urllib.parse import urlencode

from tornado.locks import Lock
from tornado.util import TimeoutError as TornadoTimeoutError

from pcs.daemon import (
    http_server,
    ruby_pcsd,
)
from pcs.daemon.app import sinatra_remote
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from pcs_test.tier0.daemon.app import fixtures_app

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class AppTest(fixtures_app.AppTest):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA)
        self.https_server_manage = mock.MagicMock(
            spec_set=http_server.HttpsServerManage
        )
        self.lock = Lock()
        self.auth_provider = AuthProvider(logging.getLogger("test logger"))
        super().setUp()

    def _mock_auth_provider_method(self, method_name, return_value=None):
        method_patcher = mock.patch.object(AuthProvider, method_name)
        self.addCleanup(method_patcher.stop)
        method_mock = method_patcher.start()
        if return_value:
            method_mock.return_value = return_value
        return method_mock

    def get_routes(self):
        return sinatra_remote.get_routes(
            self.wrapper,
            self.lock,
            self.https_server_manage,
            self.auth_provider,
        )


class SetCerts(AppTest):
    def setUp(self):
        super().setUp()
        self._mock_auth_provider_method(
            "auth_by_token", AuthUser(username="user", groups=("group1",))
        )
        self.headers = {"Cookie": "token=1234"}

    def test_it_asks_for_cert_reload_if_ruby_succeeds(self):
        self.wrapper.status_code = 200
        self.wrapper.body = b"success"
        # body is irelevant
        self.assert_wrappers_response(
            self.post("/remote/set_certs", body={}, headers=self.headers)
        )
        self.https_server_manage.reload_certs.assert_called_once()

    def test_it_not_asks_for_cert_reload_if_ruby_fail(self):
        self.wrapper.status_code = 400
        self.wrapper.body = b"cannot save ssl certificate without ssl key"
        # body is irelevant
        self.assert_wrappers_response(
            self.post("/remote/set_certs", body={}, headers=self.headers)
        )
        self.https_server_manage.reload_certs.assert_not_called()


class SinatraRemote(AppTest):
    def setUp(self):
        super().setUp()
        self._mock_auth_provider_method(
            "auth_by_token", AuthUser(username="user", groups=("group1",))
        )
        self.headers = {"Cookie": "token=1234"}

    def test_take_result_from_ruby(self):
        self.assert_wrappers_response(
            self.get("/remote/", headers=self.headers)
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

    def setUp(self):
        super().setUp()
        self._mock_auth_provider_method(
            "auth_by_token", AuthUser(username="user", groups=("group1",))
        )

    def fetch_set_sync_options(self, method):
        def fetch_sync_options():
            return self.http_client.fetch(
                self.get_url("/remote/set_sync_options"), **kwargs
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
        return self.io_loop.run_sync(fetch_sync_options, timeout=0.5)

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

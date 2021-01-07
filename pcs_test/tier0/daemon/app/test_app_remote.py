import logging
from urllib.parse import urlencode
from unittest import mock

from tornado.locks import Lock
from tornado.util import TimeoutError as TornadoTimeoutError

from pcs_test.tier0.daemon.app import fixtures_app
from pcs_test.tools.misc import create_setup_patch_mixin

from pcs.daemon import ruby_pcsd, http_server
from pcs.daemon.app import sinatra_remote

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class AppTest(fixtures_app.AppTest):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA_REMOTE)
        self.https_server_manage = mock.MagicMock(
            spec_set=http_server.HttpsServerManage
        )
        self.lock = Lock()
        super().setUp()

    def get_routes(self):
        return sinatra_remote.get_routes(
            self.wrapper,
            self.lock,
            self.https_server_manage,
        )


class SetCerts(AppTest):
    def test_it_asks_for_cert_reload_if_ruby_succeeds(self):
        self.wrapper.status_code = 200
        self.wrapper.body = b"success"
        # body is irelevant
        self.assert_wrappers_response(self.post("/remote/set_certs", body={}))
        self.https_server_manage.reload_certs.assert_called_once()

    def test_it_not_asks_for_cert_reload_if_ruby_fail(self):
        self.wrapper.status_code = 400
        self.wrapper.body = b"cannot save ssl certificate without ssl key"
        # body is irelevant
        self.assert_wrappers_response(self.post("/remote/set_certs", body={}))
        self.https_server_manage.reload_certs.assert_not_called()


class Auth(
    AppTest,
    create_setup_patch_mixin(sinatra_remote),
    fixtures_app.UserAuthMixin,
):
    # pylint: disable=too-many-ancestors
    def setUp(self):
        self.setup_patch("authorize_user", self.authorize_user)
        super().setUp()

    def make_auth_request(self, valid=True):
        self.user_auth_info = fixtures_app.UserAuthInfo(valid=valid)
        return self.post(
            "/remote/auth",
            body={
                "username": fixtures_app.USER,
                "password": fixtures_app.PASSWORD,
            },
        )

    def test_refuse_unknown_user(self):
        self.assertEqual(b"", self.make_auth_request(valid=False).body)

    def test_wraps_ruby_on_valid_user(self):
        self.assert_wrappers_response(self.make_auth_request())


class SinatraRemote(AppTest):
    def test_take_result_from_ruby(self):
        self.assert_wrappers_response(self.get("/remote/"))


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
        kwargs = (
            dict(method=method, body=urlencode({}))
            if method == "POST"
            else dict(method=method)
        )

        # Without lock the timeout should be enough to finish task. With the
        # lock it should raise because of timeout. The same timeout is used for
        # noticing differences between test with and test without lock.
        fetch_sync_options = lambda: self.http_client.fetch(
            self.get_url("/remote/set_sync_options"), **kwargs
        )
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

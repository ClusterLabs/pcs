import re
from urllib.parse import urlencode
from unittest import mock

from tornado.locks import Lock

from pcs.daemon import ruby_pcsd, app_remote, http_server
from pcs.daemon.test import fixtures_app

class AppTest(fixtures_app.AppTest):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA_REMOTE)
        self.https_server_manage = mock.MagicMock(
            spec_set=http_server.HttpsServerManage
        )
        self.lock = Lock()
        super().setUp()

    def get_routes(self):
        return app_remote.get_routes(
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

class SinatraRemote(AppTest):
    def test_take_result_from_ruby(self):
        self.assert_wrappers_response(self.get("/remote/"))

class SyncConfigMutualExclusive(AppTest):
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

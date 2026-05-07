import base64
import logging
from unittest import mock

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
        self.api_auth_provider_factory = MockAuthProviderFactory()
        super().setUp()

    def get_routes(self):
        return sinatra_remote.get_routes(
            self.api_auth_provider_factory,
            self.wrapper,
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

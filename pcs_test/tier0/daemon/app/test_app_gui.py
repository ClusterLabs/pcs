import logging
from unittest import mock

from tornado.httputil import parse_cookie

from pcs.daemon import ruby_pcsd
from pcs.daemon.app import sinatra_ui

try:
    from pcs.daemon.app import webui
except ImportError:
    webui = None
from pcs.daemon.app.auth_provider import (
    UnixSocketAuthProvider,
    UnixSocketAuthProviderFactory,
)
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from pcs_test.tier0.daemon.app import (
    fixtures_app,
    fixtures_app_webui,
)
from pcs_test.tools.misc import skip_unless_webui_installed

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


def patch_login_user():
    return mock.patch.object(
        AuthProvider,
        "login_user",
        lambda _self, username: AuthUser(username=username, groups=[username]),
    )


def patch_unix_socket_provider(user):
    return mock.patch.multiple(
        UnixSocketAuthProvider,
        can_handle_request=lambda _self: True,
        _get_unix_socket_user=lambda _self: user,
    )


lib_auth_provider = AuthProvider(logging.getLogger("test logger"))


@skip_unless_webui_installed()
@patch_login_user()
class SinatraAjaxProtectedSession(fixtures_app_webui.AppTest):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA)
        super().setUp()

    def get_routes(self):
        return sinatra_ui.get_routes(
            webui.auth_provider.SessionAuthProviderFactory(
                lib_auth_provider, self.session_storage
            ),
            self.wrapper,
        )

    def assert_session_in_response(self, response, sid=None):
        self.assertTrue("Set-Cookie" in response.headers)
        cookie = parse_cookie(response.headers["Set-Cookie"])
        self.assertTrue(webui.auth.PCSD_SESSION, cookie)
        if sid:
            self.assertEqual(cookie[webui.auth.PCSD_SESSION], sid)
        return cookie[webui.auth.PCSD_SESSION]

    def test_deal_without_authentication(self):
        self.assert_unauth_ajax(self.get("/some-ajax", is_ajax=True))

    def test_not_ajax(self):
        session1 = self.create_login_session()
        self.assert_unauth_ajax(self.get("/some-ajax", sid=session1.sid))

    def test_take_result_from_ruby(self):
        session1 = self.create_login_session()
        response = self.get("/some-ajax", sid=session1.sid, is_ajax=True)
        self.assert_wrappers_response(response)
        self.assert_session_in_response(response, session1.sid)


@patch_login_user()
class SinatraAjaxProtectedUnixSocket(fixtures_app.AppTest):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA)
        super().setUp()

    def get_routes(self):
        return sinatra_ui.get_routes(
            UnixSocketAuthProviderFactory(lib_auth_provider), self.wrapper
        )

    @patch_unix_socket_provider(None)
    def test_deal_without_authentication(self):
        self.assert_unauth_ajax(self.get("/some-ajax", is_ajax=True))

    @patch_unix_socket_provider(fixtures_app.USER)
    def test_take_result_from_ruby(self):
        response = self.get("/some-ajax", is_ajax=True)
        self.assert_wrappers_response(response)

    @patch_unix_socket_provider(fixtures_app.USER)
    def test_not_ajax(self):
        self.assert_unauth_ajax(self.get("/some-ajax"))

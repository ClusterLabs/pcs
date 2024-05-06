import logging
from unittest import mock

from pcs.daemon import ruby_pcsd
from pcs.daemon.app import sinatra_ui
from pcs.daemon.app.auth import UnixSocketAuthProvider
from pcs.daemon.app.webui import sinatra_ui as sinatra_ui_webui
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from pcs_test.tier0.daemon.app import fixtures_app

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


def patch_login_user():
    return mock.patch.object(
        AuthProvider,
        "login_user",
        lambda _self, username: AuthUser(username=username, groups=[username]),
    )


def patch_get_unix_socket_user(user):
    return mock.patch.object(
        UnixSocketAuthProvider,
        "get_unix_socket_user",
        lambda _self: user,
    )


auth_provider = AuthProvider(logging.getLogger("test logger"))


class AppTest(fixtures_app.AppUiTestMixin):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA)
        super().setUp()


@patch_login_user()
class SinatraAjaxProtectedSession(AppTest):
    def get_routes(self):
        return sinatra_ui_webui.get_routes(
            self.session_storage,
            auth_provider,
            self.wrapper,
        )

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
class SinatraAjaxProtectedUnixSocket(AppTest):
    def get_routes(self):
        return sinatra_ui.get_routes(auth_provider, self.wrapper)

    @patch_get_unix_socket_user(None)
    def test_deal_without_authentication(self):
        self.assert_unauth_ajax(self.get("/some-ajax", is_ajax=True))

    @patch_get_unix_socket_user(fixtures_app.USER)
    def test_take_result_from_ruby(self):
        response = self.get("/some-ajax", is_ajax=True)
        self.assert_wrappers_response(response)

    @patch_get_unix_socket_user(fixtures_app.USER)
    def test_not_ajax(self):
        self.assert_unauth_ajax(self.get("/some-ajax"))

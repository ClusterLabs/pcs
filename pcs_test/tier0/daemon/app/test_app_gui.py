import logging
from unittest import mock

from pcs.daemon import ruby_pcsd
from pcs.daemon.app import sinatra_ui
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from pcs_test.tier0.daemon.app import fixtures_app

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class AppTest(fixtures_app.AppUiTestMixin):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA)
        super().setUp()

    def get_routes(self):
        return sinatra_ui.get_routes(
            self.session_storage,
            AuthProvider(logging.getLogger("test logger")),
            self.wrapper,
        )


@mock.patch.object(
    AuthProvider,
    "login_user",
    lambda _self, username: AuthUser(username=username, groups=[username]),
)
class SinatraAjaxProtected(AppTest):
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

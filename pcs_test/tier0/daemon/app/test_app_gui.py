import logging

from pcs.daemon import (
    auth,
    ruby_pcsd,
)
from pcs.daemon.app import sinatra_ui

from pcs_test.tier0.daemon.app import fixtures_app
from pcs_test.tools.misc import create_setup_patch_mixin

USER = "user"
PASSWORD = "password"
LOGIN_BODY = {"username": USER, "password": PASSWORD}

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class AppTest(
    fixtures_app.AppUiTestMixin,
    create_setup_patch_mixin(sinatra_ui),
):
    def setUp(self):
        self.wrapper = fixtures_app.RubyPcsdWrapper(ruby_pcsd.SINATRA_GUI)
        self.setup_patch("check_user_groups", self.check_user_groups)
        super().setUp()

    async def check_user_groups(self, username):
        self.assertEqual(username, USER)
        return auth.UserAuthInfo(
            username,
            self.user_auth_info.groups,
            is_authorized=self.groups_valid,
        )

    def get_routes(self):
        return sinatra_ui.get_routes(
            self.session_storage,
            self.wrapper,
        )

    def assert_is_redirect(self, response, location, status_code=302):
        self.assert_headers_contains(response.headers, {"Location": location})
        self.assertEqual(response.code, status_code)


class SinatraAjaxProtected(AppTest):
    # pylint: disable=too-many-ancestors
    def test_deal_without_authentication(self):
        self.assert_unauth_ajax(self.get("/some-ajax", is_ajax=True))

    def test_deal_without_ajax(self):
        session1 = self.create_login_session()
        response = self.get("/some-ajax", sid=session1.sid)
        self.assert_unauth_ajax(response)
        self.assert_session_in_response(response, session1.sid)

    def test_take_result_from_ruby(self):
        session1 = self.create_login_session()
        response = self.get("/some-ajax", sid=session1.sid, is_ajax=True)
        self.assert_wrappers_response(response)
        self.assert_session_in_response(response, session1.sid)

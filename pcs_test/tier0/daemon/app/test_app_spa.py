import logging
import os

from pcs.daemon import auth
from pcs.daemon.app import ui
from pcs_test.tier0.daemon.app import fixtures_app
from pcs_test.tools.misc import(
    create_setup_patch_mixin,
    get_test_resource as rc,
)

USER = "user"
PASSWORD = "password"
LOGIN_BODY = {"username": USER, "password": PASSWORD}
PUBLIC_DIR = rc("web_public")
PREFIX = "/ui/"
SPA_DIR = os.path.join(PUBLIC_DIR, PREFIX)
FALLBACK = os.path.join(PUBLIC_DIR, "fallback.html")
INDEX = os.path.join(SPA_DIR, "index.html")

if not os.path.exists(SPA_DIR):
    os.makedirs(SPA_DIR)

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)

class AppTest(
    fixtures_app.AppUiTest, create_setup_patch_mixin(ui.app_session)
):
    def setUp(self):
        self.index_content = "<html/>"
        with open(INDEX, "w") as index:
            index.write(self.index_content)
        super().setUp()

    def tearDown(self):
        if os.path.isfile(INDEX):
            os.remove(INDEX)
        super().tearDown()

    def get_routes(self):
        return ui.get_routes(
            url_prefix=PREFIX,
            app_dir=SPA_DIR,
            fallback_page_path=FALLBACK,
            session_storage=self.session_storage
        )

class Static(AppTest):
    def test_index(self):
        self.assert_success_response(
            self.get(f"{PREFIX}"),
            self.index_content,
        )

class Fallback(AppTest):
    def setUp(self):
        super().setUp()
        os.remove(INDEX)
        self.fallback_content = "fallback"
        with open(FALLBACK, "w") as index:
            index.write(self.fallback_content)

    def tearDown(self):
        os.remove(FALLBACK)
        super().tearDown()

    def test_index(self):
        self.assert_success_response(
            self.get(f"{PREFIX}"),
            self.fallback_content,
        )

class Login(AppTest):
    def setUp(self):
        self.setup_patch("authorize_user", self.authorize_user)
        super().setUp()

    async def authorize_user(self, username, password):
        self.assertEqual(username, USER)
        self.assertEqual(password, PASSWORD)
        return auth.UserAuthInfo(
            username,
            self.user_auth_info.groups,
            is_authorized=self.user_auth_info.valid
        )

    def test_login_attempt_failed(self):
        self.user_auth_info.valid = False
        self.assert_unauth_ajax(
            self.post(f'{PREFIX}login', LOGIN_BODY, is_ajax=True)
        )

    def test_login_attempt_succeeded(self):
        self.user_auth_info.valid = True
        response = self.post(f'{PREFIX}login', LOGIN_BODY, is_ajax=True)
        self.assert_success_response(
            response,
            self.session_storage.provide(self.extract_sid(response)).ajax_id
        )

class Logout(AppTest):
    def test_can_logout(self):
        session1 = self.create_login_session()
        response = self.get(f"{PREFIX}logout", sid=session1.sid, is_ajax=True)
        self.assert_success_response(response, "OK")
        self.assertFalse(
            self.session_storage.provide(session1.sid).is_authenticated
        )

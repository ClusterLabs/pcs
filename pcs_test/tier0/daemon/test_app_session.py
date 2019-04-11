from tornado.httputil import parse_cookie
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application, RequestHandler

from pcs_test.tier0.daemon.test_session import AssertMixin
from pcs_test.tier0.daemon.fixtures_app import(
    USER,
    GROUPS,
    PASSWORD,
    UserAuthInfo,
    UserAuthMixin
)
from pcs_test.tools.misc import create_setup_patch_mixin

from pcs.daemon import session, app_session

# pylint: disable=too-many-ancestors

SID = "abc"

def headers_with_sid(cookie_sid):
    return {
        "headers": {
            "Cookie": f"{app_session.PCSD_SESSION}={cookie_sid}"
        }
    }

class Handler(app_session.Mixin, RequestHandler):
    # pylint: disable=abstract-method,arguments-differ
    test = None
    @property
    def response_cookies(self):
        return {} if not hasattr(self, "_new_cookie") else {
            key: morsel.value for key, morsel in self._new_cookie.items()
        }

    async def get(self, *args, **kwargs):
        if self.test.auto_init_session:
            await self.init_session()
        await self.test.on_handle(self)

VANILLA_SESSION = "VANILLA_SESSION"
AUTHENTICATED_SESSION = "AUTHENTICATED_SESSION"
RESPONSE_WITH_SID = "RESPONSE_WITH_SID"
RESPONSE_WITHOUT_SID = "RESPONSE_WITHOUT_SID"
RESPONSE_SID_IN_STORAGE = "RESPONSE_SID_IN_STORAGE"

class MixinTest(
    AsyncHTTPTestCase, AssertMixin, create_setup_patch_mixin(app_session),
    UserAuthMixin
):
    init_session = None
    auto_init_session = True
    groups_valid = False
    response_sid_expectation = None
    """
    The app_session.Mixin is tested via Handler(RequestHandler) that mix it. The
    particular tests acts inside the handler.
    """
    def setUp(self):
        Handler.test = self
        self.storage = session.Storage(lifetime_seconds=10)
        self.setup_patch("check_user_groups", self.check_user_groups)
        self.setup_patch("authorize_user", self.authorize_user)
        self.fetch_args = {}
        self.sid = None

        self.response = None

        super().setUp()

    def get_app(self):
        return Application([("/", Handler, dict(session_storage=self.storage))])

    @property
    def session_dict(self):
        # pylint: disable=protected-access
        return self.storage._Storage__sessions

    def sid_from_body(self, response):
        self.assertIn("Set-Cookie", response.headers)
        cookie = parse_cookie(response.headers["Set-Cookie"])
        self.assertIn(app_session.PCSD_SESSION, cookie)
        return cookie[app_session.PCSD_SESSION]

    def extra_checks(self, response):
        pass

    async def on_handle(self, handler):
        pass

    def test(self):
        if self.init_session == VANILLA_SESSION:
            self.sid = self.storage.provide().sid
            self.fetch_args = headers_with_sid(self.sid)
        elif self.init_session == AUTHENTICATED_SESSION:
            self.sid = self.storage.login(
                sid=None,
                username=USER,
                groups=[]
            ).sid
            self.fetch_args = headers_with_sid(self.sid)

        response = self.fetch("/", **self.fetch_args)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"")
        if self.response_sid_expectation == RESPONSE_WITH_SID:
            self.assertEqual(self.sid_from_body(response), self.sid)
        elif self.response_sid_expectation == RESPONSE_WITHOUT_SID:
            self.assertNotIn("Set-Cookie", response.headers)
        self.extra_checks(response)

class SidNotInRequestCookiesByDefault(MixinTest):
    response_sid_expectation = RESPONSE_WITHOUT_SID
    async def on_handle(self, handler):
        self.assertFalse(handler.was_sid_in_request_cookies())

class SidInRequestCookiesButNotInResponseCookies(MixinTest):
    init_session = VANILLA_SESSION
    response_sid_expectation = RESPONSE_WITHOUT_SID
    async def on_handle(self, handler):
        self.assertTrue(handler.was_sid_in_request_cookies())
        self.assertEqual(self.sid, handler.session.sid)
        self.assertFalse(app_session.PCSD_SESSION in handler.response_cookies)

class SidInResponseCookies(MixinTest):
    init_session = VANILLA_SESSION
    response_sid_expectation = RESPONSE_WITH_SID
    async def on_handle(self, handler):
        self.assertTrue(handler.was_sid_in_request_cookies())
        handler.put_request_cookies_sid_to_response_cookies_sid()
        self.assertTrue(app_session.PCSD_SESSION in handler.response_cookies)

class GetNewSession(MixinTest):
    auto_init_session = False
    response_sid_expectation = RESPONSE_WITH_SID
    async def on_handle(self, handler):
        self.assertEqual(len(self.session_dict), 0)
        await handler.init_session()
        self.assertEqual(len(self.session_dict), 1)
        self.sid = handler.session.sid
        handler.sid_to_cookies()

class SessionInMixinSurviveDestroyInStorage(MixinTest):
    async def on_handle(self, handler):
        # A handler can wait for something (e.g. external command). The already
        # started request should succeed even if the session expires in the
        # meantime.
        session1 = handler.session
        self.storage.destroy(session1.sid)
        self.assertIs(session1, handler.session)

class SessionIsPropagatedToResponseCookie(MixinTest):
    async def on_handle(self, handler):
        handler.sid_to_cookies()
        self.assertEqual(
            handler.response_cookies[app_session.PCSD_SESSION],
            handler.session.sid
        )

    def extra_checks(self, response):
        self.assertIn(self.sid_from_body(response), self.session_dict)

class CanLoginAndLogout(MixinTest):
    user_auth_info = UserAuthInfo(valid=True)
    auto_init_session = False
    async def on_handle(self, handler):
        await handler.session_auth_user(USER, PASSWORD)
        self.assert_authenticated_session(handler.session, USER, GROUPS)
        handler.session_logout()
        self.assert_vanila_session(handler.session)

class FailedLoginAttempt(MixinTest):
    auto_init_session = False
    async def on_handle(self, handler):
        await handler.session_auth_user(USER, PASSWORD)
        self.assert_login_failed_session(handler.session, USER)

class FailedLoginAttemptWithoutSessionSign(MixinTest):
    auto_init_session = False
    async def on_handle(self, handler):
        await handler.session_auth_user(
            USER,
            PASSWORD,
            sign_rejection=False,
        )
        self.assert_vanila_session(handler.session)

class CanLogoutWithoutSessionAccess(MixinTest):
    init_session = VANILLA_SESSION
    auto_init_session = False
    async def on_handle(self, handler):
        handler.session_logout()
        self.assertNotEqual(self.sid, handler.session.sid)

class AuthUpdatedByGroupCheck(MixinTest):
    init_session = AUTHENTICATED_SESSION
    groups_valid = True

    async def on_handle(self, handler):
        self.assertTrue(handler.was_sid_in_request_cookies())
        self.assertTrue(handler.session.is_authenticated)

class AuthRefusedByGroupCheck(MixinTest):
    init_session = AUTHENTICATED_SESSION
    async def on_handle(self, handler):
        self.assertFalse(handler.session.is_authenticated)

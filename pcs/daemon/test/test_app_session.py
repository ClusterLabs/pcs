from unittest import TestCase

from pcs.daemon import session, app_session
from pcs.daemon.test.test_session import AssertMixin


SID = "abc"
USER = "user"
GROUPS = ["group1", "group2"]

class RequestHandler(app_session.Mixin):
    def __init__(self, request_cookies=None):
        self.request_cookies = request_cookies or {}
        self.response_cookies = {}

    def get_cookie(self, key, default):
        return self.request_cookies.get(key, default)

    def set_cookie(self, key, value):
        self.response_cookies[key] = value

class MixinTest(TestCase, AssertMixin):
    def setUp(self):
        self.storage = session.Storage(lifetime_seconds=10)
        self.handler = RequestHandler()
        self.handler.initialize(self.storage)
        self.handler.prepare()

    def test_can_login_and_logout(self):
        self.handler.session_login(USER, GROUPS)
        self.assert_authenticated_session(self.handler.session, USER, GROUPS)
        self.handler.session_logout()
        self.assert_vanila_session(self.handler.session)

    def test_can_sign_failed_login_attempt(self):
        self.handler.session_login_failed(USER)
        self.assert_login_failed_session(self.handler.session, USER)

    def test_use_session_according_to_cookies(self):
        session1 = self.storage.provide()
        self.handler.request_cookies = {app_session.PCSD_SESSION: session1.sid}
        self.assertIs(session1, self.handler.session)

    def test_can_logout_without_session_access(self):
        session1 = self.storage.provide()
        self.handler.request_cookies = {app_session.PCSD_SESSION: session1.sid}
        self.handler.session_logout()
        self.assertIsNot(session1, self.handler.session)

    def test_mixin_session_survive_destroy_in_storage(self):
        # A handler can wait for something (e.g. external command). The already
        # started request should succeed even if the session expires in the
        # meantime.
        session1 = self.handler.session
        self.storage.destroy(session1.sid)
        self.assertIs(session1, self.handler.session)

    def test_put_request_cookies_sid_to_response_cookies_sid(self):
        self.handler.request_cookies = {app_session.PCSD_SESSION: SID}
        self.handler.put_request_cookies_sid_to_response_cookies_sid()
        self.assertEqual(
            self.handler.response_cookies,
            {app_session.PCSD_SESSION: SID},
        )

    def test_check_if_was_sid_in_request_cookies(self):
        self.assertFalse(self.handler.was_sid_in_request_cookies())
        self.handler.request_cookies = {app_session.PCSD_SESSION: SID}
        self.assertTrue(self.handler.was_sid_in_request_cookies())

    def test_session_id_is_propagated_to_response_cookies(self):
        self.handler.sid_to_cookies()
        self.assertEqual(
            self.handler.response_cookies[app_session.PCSD_SESSION],
            self.handler.session.sid
        )

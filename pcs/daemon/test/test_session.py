from unittest import TestCase
from contextlib import contextmanager

from pcs.daemon.session import Session
from pcs.daemon import session
from pcs.test.tools.misc import create_setup_patch_mixin

SID = "abc"
USER = "user"
GROUPS = ["group1", "group2"]


class AssertMixin:
    def assert_vanila_session(self, session):
        self.assertIsNone(session.username)
        self.assertFalse(session.is_authenticated)
        self.assertIsNone(session.ajax_id)
        self.assertEqual(session.groups, [])

    def assert_authenticated_session(self, session, username, groups):
        self.assertEqual(session.username, username)
        self.assertEqual(session.groups, groups)
        self.assertTrue(session.is_authenticated)
        self.assertTrue(session.ajax_id is not None)

    def assert_login_failed_session(self, session, username):
        self.assertEqual(session.username, username)
        self.assertFalse(session.is_authenticated)

PatchSessionMixin = create_setup_patch_mixin(session)

class SessionTest(TestCase, AssertMixin, PatchSessionMixin):
    def setUp(self):
        self.now = self.setup_patch("now", return_value=0)
        self.session = Session(SID)

    def test_session_grows_older(self):
        self.now.return_value = 10.1
        self.assertTrue(self.session.was_unused_last(10))
        self.assertFalse(self.session.was_unused_last(11))

    @contextmanager
    def refresh_test(self):
        self.now.return_value = 10.1
        yield self.session
        self.now.return_value = 11.2
        self.assertTrue(self.session.was_unused_last(1))
        self.assertFalse(self.session.was_unused_last(2))

    def test_session_is_refreshable(self):
        # pylint: disable=pointless-statement
        with self.refresh_test() as session1:
            session1.refresh()
        with self.refresh_test() as session1:
            session1.is_authenticated
        with self.refresh_test() as session1:
            session1.username
        with self.refresh_test() as session1:
            session1.groups
        with self.refresh_test() as session1:
            session1.sid
        with self.refresh_test() as session1:
            session1.ajax_id

class StorageTest(TestCase, AssertMixin, PatchSessionMixin):
    def setUp(self):
        self.now = self.setup_patch("now", return_value=0)
        self.storage = session.Storage(lifetime_seconds=10)

    def test_creates_vanilla_session_when_sid_not_specified(self):
        self.assert_vanila_session(self.storage.provide())

    def test_does_not_accept_foreign_sid(self):
        session1 = self.storage.provide("unknown_sid")
        self.assertNotEqual(session1.sid, "unknown_sid")
        self.assert_vanila_session(session1)

    def test_provides_the_same_session_for_same_sid(self):
        session1 = self.storage.provide()
        session2 = self.storage.provide(session1.sid)
        self.assertIs(session1, session2)

    def test_can_destroy_session(self):
        session1 = self.storage.provide()
        self.storage.destroy(session1.sid)
        session2 = self.storage.provide(session1.sid)
        self.assertIsNot(session1, session2)

    def test_can_drop_expired_sessions_explicitly(self):
        session1 = self.storage.provide()
        self.now.return_value = 5
        session2 = self.storage.provide()
        self.now.return_value = 12
        self.storage.drop_expired()
        session3 = self.storage.provide(session1.sid)
        session4 = self.storage.provide(session2.sid)
        self.assertIsNot(session3, session1)
        self.assertIs(session4, session2)

    def test_can_drop_expired_session_implicitly(self):
        session1 = self.storage.provide()
        sid = session1.sid
        self.now.return_value = 11
        session2 = self.storage.provide(sid)
        self.assertIsNot(session1, session2)

    def test_can_login_new_session(self):
        self.assert_authenticated_session(
            self.storage.login(sid=None, username=USER, groups=GROUPS),
            USER,
            GROUPS,
        )

    def test_can_login_existing_session(self):
        session1 = self.storage.provide()
        session2 = self.storage.login(session1.sid, USER, GROUPS)
        self.assert_authenticated_session(session2, USER, GROUPS)
        self.assertEqual(session1.sid, session2.sid)

    def test_can_sign_failed_login_attempt_new_session(self):
        self.assert_login_failed_session(
            self.storage.rejected_user(sid=None, username=USER),
            USER
        )

    def test_can_sign_failed_login_attempt_existing_session(self):
        session1 = self.storage.provide()
        session2 = self.storage.rejected_user(session1.sid, USER)
        self.assert_login_failed_session(session2, USER)
        self.assertEqual(session1.sid, session2.sid)

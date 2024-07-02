from contextlib import contextmanager
from unittest import TestCase

try:
    from pcs.daemon.app import webui
except ImportError:
    webui = None

from pcs_test.tools.misc import (
    create_setup_patch_mixin,
    skip_unless_webui_installed,
)

SID = "abc"
USER = "user"
GROUPS = ["group1", "group2"]


# If webui is None, the tests in this file using these mixins are skipped,
# passing a dummy object instead to make this executable
PatchSessionMixin = create_setup_patch_mixin(webui) if webui else object


@skip_unless_webui_installed()
class SessionTest(TestCase, PatchSessionMixin):
    def setUp(self):
        self.now = self.setup_patch("session.now", return_value=0)
        self.session = webui.session.Session(SID, USER)

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
            session1.username
        with self.refresh_test() as session1:
            session1.sid


@skip_unless_webui_installed()
class StorageTest(TestCase, PatchSessionMixin):
    def setUp(self):
        self.now = self.setup_patch("session.now", return_value=0)
        self.storage = webui.session.Storage(lifetime_seconds=10)

    def test_does_not_accept_foreign_sid(self):
        self.assertIsNone(self.storage.get("unknown_sid"))

    def test_provides_the_same_session_for_same_sid(self):
        session1 = self.storage.login(USER)
        session2 = self.storage.get(session1.sid)
        self.assertIs(session1, session2)

    def test_can_destroy_session(self):
        session1 = self.storage.login(USER)
        self.storage.destroy(session1.sid)
        self.assertIsNone(self.storage.get(session1.sid))

    def test_can_drop_expired_sessions_explicitly(self):
        session1 = self.storage.login(USER)
        self.now.return_value = 5
        session2 = self.storage.login(USER)
        self.now.return_value = 12
        self.storage.drop_expired()
        self.assertIsNone(self.storage.get(session1.sid))
        self.assertIs(self.storage.get(session2.sid), session2)

    def test_can_drop_expired_session_implicitly(self):
        session1 = self.storage.login(USER)
        self.now.return_value = 11
        self.storage.login(USER)
        self.assertIsNone(self.storage.get(session1.sid))

    def test_can_login_new_session(self):
        session1 = self.storage.login(USER)
        self.assertIsNotNone(session1)
        self.assertEqual(session1.username, USER)

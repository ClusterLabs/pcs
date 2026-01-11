from unittest import IsolatedAsyncioTestCase, mock

from pcs.daemon.app.auth import NotAuthorizedException
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

try:
    from pcs.daemon.app import webui
except ImportError:
    webui = None

from pcs_test.tools.misc import skip_unless_webui_installed


class MockStorage:
    """Mock session storage for testing."""

    def __init__(self):
        self.sessions = {}

    def get(self, sid):
        return self.sessions.get(sid)

    def add_session(self, sid, username):
        """Add a session to storage (test helper)."""
        session = webui.session.Session(sid, username)
        self.sessions[sid] = session
        return session


@skip_unless_webui_installed()
class SessionAuthProviderTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = mock.Mock()
        cookie_jar = {webui.auth_provider.PCSD_SESSION: "session123"}
        self.handler.get_cookie.side_effect = (
            lambda name, default: cookie_jar.get(name, default)
        )

        self.session_storage = MockStorage()

        self.lib_auth_provider = mock.Mock(spec=AuthProvider)

    def test_is_available_returns_true_with_session(self):
        self.session_storage.add_session("session123", "bob")

        provider = webui.auth_provider.SessionAuthProvider(
            self.handler, self.lib_auth_provider, self.session_storage
        )

        self.assertTrue(provider.is_available())

    def test_is_available_returns_false_without_session(self):
        provider = webui.auth_provider.SessionAuthProvider(
            self.handler, self.lib_auth_provider, self.session_storage
        )

        self.assertFalse(provider.is_available())

    async def test_auth_user_success_with_valid_session(self):
        self.session_storage.add_session("session123", "bob")

        provider = webui.auth_provider.SessionAuthProvider(
            self.handler, self.lib_auth_provider, self.session_storage
        )
        expected_user = AuthUser("bob", ["users"])
        self.lib_auth_provider.login_user.return_value = expected_user

        result = await provider.auth_user()

        self.assertEqual(result, expected_user)
        self.lib_auth_provider.login_user.assert_called_once_with("bob")
        self.handler.set_cookie.assert_called_once_with(
            webui.auth_provider.PCSD_SESSION,
            "session123",
            secure=True,
            httponly=True,
            samesite="Lax",
        )

    async def test_auth_user_raises_when_session_is_none(self):
        provider = webui.auth_provider.SessionAuthProvider(
            self.handler, self.lib_auth_provider, self.session_storage
        )

        with self.assertRaises(NotAuthorizedException):
            await provider.auth_user()

        self.lib_auth_provider.login_user.assert_not_called()
        self.handler.set_cookie.assert_not_called()

    async def test_auth_user_raises_when_login_fails(self):
        self.session_storage.add_session("session123", "bob")

        provider = webui.auth_provider.SessionAuthProvider(
            self.handler, self.lib_auth_provider, self.session_storage
        )
        self.lib_auth_provider.login_user.return_value = None

        with self.assertRaises(NotAuthorizedException):
            await provider.auth_user()

        self.lib_auth_provider.login_user.assert_called_once_with("bob")
        self.handler.set_cookie.assert_not_called()

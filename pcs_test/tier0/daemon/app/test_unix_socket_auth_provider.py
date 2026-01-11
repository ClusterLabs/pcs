import socket
import struct
from unittest import IsolatedAsyncioTestCase, mock

from pcs.daemon.app.auth import NotAuthorizedException
from pcs.daemon.app.auth_provider import UnixSocketAuthProvider
from pcs.lib.auth.const import SUPERUSER
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser


class UnixSocketAuthProviderTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = mock.Mock()
        self.lib_auth_provider = mock.Mock(spec=AuthProvider)
        self.provider = UnixSocketAuthProvider(
            self.handler, self.lib_auth_provider
        )

    def _setup_unix_socket(self, uid=1000, username="testuser"):
        """Setup mock handler with Unix socket connection."""
        # Mock socket with AF_UNIX family
        mock_socket = mock.Mock()
        mock_socket.family = socket.AF_UNIX

        # Mock getsockopt to return credentials
        # Format: pid (int), uid (int), gid (int)
        credentials = struct.pack("3i", 12345, uid, 1000)
        mock_socket.getsockopt.return_value = credentials

        # Mock stream and connection
        mock_stream = mock.Mock()
        mock_stream.socket = mock_socket

        mock_connection = mock.Mock()
        mock_connection.stream = mock_stream

        self.handler.request.connection = mock_connection

        # Mock pwd.getpwuid
        if uid != 0:  # Root doesn't need pwd.getpwuid
            mock_passwd = mock.Mock()
            mock_passwd.pw_name = username
            self.pwd_patcher = mock.patch(
                "pcs.daemon.app.auth_provider.pwd.getpwuid"
            )
            self.mock_getpwuid = self.pwd_patcher.start()
            self.mock_getpwuid.return_value = mock_passwd
            self.addCleanup(self.pwd_patcher.stop)

    def _setup_tcp_socket(self):
        """Setup mock handler with TCP socket connection."""
        mock_socket = mock.Mock()
        mock_socket.family = socket.AF_INET  # TCP socket

        mock_stream = mock.Mock()
        mock_stream.socket = mock_socket

        mock_connection = mock.Mock()
        mock_connection.stream = mock_stream

        self.handler.request.connection = mock_connection

    def test_is_available_returns_true_for_unix_socket(self):
        self._setup_unix_socket()

        self.assertTrue(self.provider.is_available())

    def test_is_available_returns_false_for_tcp_socket(self):
        self._setup_tcp_socket()

        self.assertFalse(self.provider.is_available())

    def test_get_unix_socket_user_extracts_username(self):
        self._setup_unix_socket(uid=1000, username="alice")

        username = self.provider._get_unix_socket_user()

        self.assertEqual(username, "alice")

    def test_get_unix_socket_user_treats_root_as_superuser(self):
        """Test _get_unix_socket_user treats UID 0 as SUPERUSER."""
        self._setup_unix_socket(uid=0)

        username = self.provider._get_unix_socket_user()

        self.assertEqual(username, SUPERUSER)

    def test_get_unix_socket_user_returns_none_for_tcp(self):
        self._setup_tcp_socket()

        username = self.provider._get_unix_socket_user()

        self.assertIsNone(username)

    async def test_auth_user_success_with_regular_user(self):
        self._setup_unix_socket(uid=1000, username="testuser")
        expected_user = AuthUser("testuser", ["testgroup"])
        self.lib_auth_provider.login_user.return_value = expected_user

        result = await self.provider.auth_user()

        self.assertEqual(result, expected_user)
        self.lib_auth_provider.login_user.assert_called_once_with("testuser")

    async def test_auth_user_success_with_root(self):
        self._setup_unix_socket(uid=0)  # Root user
        expected_user = AuthUser(SUPERUSER, ["haclient"])
        self.lib_auth_provider.login_user.return_value = expected_user

        result = await self.provider.auth_user()

        self.assertEqual(result, expected_user)
        # Root should be treated as SUPERUSER
        self.lib_auth_provider.login_user.assert_called_once_with(SUPERUSER)

    async def test_auth_user_raises_when_login_fails(self):
        self._setup_unix_socket(uid=1000, username="testuser")
        self.lib_auth_provider.login_user.return_value = None

        with self.assertRaises(NotAuthorizedException):
            await self.provider.auth_user()

    async def test_auth_user_raises_when_not_unix_socket(self):
        self._setup_tcp_socket()

        with self.assertRaises(NotAuthorizedException):
            await self.provider.auth_user()

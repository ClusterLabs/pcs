"""
This module reimplements the AuthProviders from pcs.daemon.auth module.

This new approach tries to simplify the auth provider structure, and use
composition over inheritance:
    - Each auth provider should only use one method for auth
    - AuthProviderMulti should be used when multiple auth methods are needed
"""

import pwd
import socket
import struct
from typing import Optional, Sequence, cast

from tornado.http1connection import HTTP1Connection
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler

from pcs.daemon.app.auth import NotAuthorizedException
from pcs.lib.auth.const import SUPERUSER
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser


class ApiAuthProviderInterface:
    """
    Interface for authentication providers used in API and UI handlers.

    All authentication providers must implement this interface to provide
    a consistent authentication contract across different auth methods
    (socket, session, token, password, etc.).
    """

    def is_available(self) -> bool:
        """
        Check if this authentication provider can handle the current request.

        This method should check if the necessary credentials or conditions
        are present for this provider to attempt authentication. For example:
        - SocketAuthProvider: checks if request came via unix socket
        - SessionAuthProvider: checks if session cookie is present

        Returns:
            True if this provider can attempt authentication for this request,
            False otherwise.

        Note:
            This method should not perform the actual authentication, only
            check if the preconditions are met. It should be lightweight
            and idempotent.
        """
        raise NotImplementedError()

    async def auth_user(self) -> AuthUser:
        """
        Authenticate the user and return the authenticated user object.

        This method performs the actual authentication using the credentials
        or session available in the current request. It should only be called
        if is_available() returns True.

        Returns:
            AuthUser object containing the authenticated username and groups.

        Raises:
            NotAuthorizedException: If authentication fails (invalid credentials,
                                   expired session, etc.)

        Note:
            Providers must NOT implement fallback logic to other auth methods.
            Each provider should only handle its own authentication mechanism.
            Fallback orchestration is handled by AuthProviderMulti.
        """
        raise NotImplementedError()


class ApiAuthProviderFactoryInterface:
    """
    Factory interface for creating authentication provider instances.
    """

    def __init__(self, lib_auth_provider: AuthProvider):
        self._lib_auth_provider = lib_auth_provider

    def create(self, handler: RequestHandler) -> ApiAuthProviderInterface:
        """
        Create an authentication provider instance.

        Args:
            handler: Tornado request handler for accessing request data

        Returns:
            ApiAuthProviderInterface implementation configured for this request
        """
        raise NotImplementedError()


class AuthProviderMulti(ApiAuthProviderInterface):
    """
    Orchestrates multiple authentication providers with explicit fallback logic.

    This provider tries multiple authentication methods in order and uses the
    first one that is available. This replaces the implicit fallback logic that
    was previously embedded within individual providers.
    """

    def __init__(self, providers: Sequence[ApiAuthProviderInterface]) -> None:
        """
        Initialize the multi-provider with a list of providers.

        Args:
            providers: Ordered sequence of providers to try
        """
        self._providers = providers
        self._first_available_provider: Optional[ApiAuthProviderInterface] = (
            None
        )

    def is_available(self) -> bool:
        """
        Check if any of the configured providers is available. Cache the first
        available provider.
        """
        for provider in self._providers:
            if provider.is_available():
                self._first_available_provider = provider
                return True
        return False

    async def auth_user(self) -> AuthUser:
        if self._first_available_provider is not None:
            return await self._first_available_provider.auth_user()

        if not self.is_available():
            # No providers available
            raise NotAuthorizedException()

        return await self._first_available_provider.auth_user()


class AuthProviderMultiFactory(ApiAuthProviderFactoryInterface):
    """
    Factory for creating AuthProviderMulti instances.

    This factory composes other factories to create a multi-provider that
    tries multiple authentication methods in sequence.
    """

    def __init__(
        self,
        factories: Sequence[ApiAuthProviderFactoryInterface],
    ) -> None:
        self._factories = factories

    def create(self, handler: RequestHandler) -> ApiAuthProviderInterface:
        return AuthProviderMulti(
            [factory.create(handler) for factory in self._factories]
        )


class UnixSocketAuthProvider(ApiAuthProviderInterface):
    """
    Authentication provider for Unix socket connections.

    Authenticates users based on Unix socket peer credentials (SO_PEERCRED).
    This provider only works when the request comes over a Unix domain socket.

    Special handling:
    - UID 0 (root) is treated as the cluster SUPERUSER
    - Extracts username from system user database via pwd.getpwuid()
    """

    def __init__(
        self, handler: RequestHandler, lib_auth_provider: AuthProvider
    ) -> None:
        self._handler = handler
        self._lib_auth_provider = lib_auth_provider

    def _is_unix_socket_used(self) -> bool:
        """
        Check if the request came over a Unix domain socket.

        Returns:
            True if connection is via Unix socket, False otherwise
        """
        # For whatever reason, handler.request.connection is typed as
        # HTTPConnection in tornado. That class, however, doesn't have stream
        # attribute. In reality, HTTP1Connection is probably used.
        return (
            cast(
                HTTP1Connection, self._handler.request.connection
            ).stream.socket.family
            == socket.AF_UNIX
        )

    def _get_unix_socket_user(self) -> Optional[str]:
        """
        Extract username from Unix socket peer credentials.

        Returns:
            Username of the peer process, or None if not a Unix socket

        Note:
            UID 0 (root) is treated as SUPERUSER
        """
        if not self._is_unix_socket_used():
            return None

        # It is not cached to prevent inappropriate cache when handler is (in
        # hypothetical future) somehow reused. The responsibility for cache is
        # left to the place, that uses it.
        # For whatever reason, handler.request.connection is typed as
        # HTTPConnection in tornado. That class, however, doesn't have stream
        # attribute. In reality, HTTP1Connection is probably used.
        credentials = cast(
            HTTP1Connection, self._handler.request.connection
        ).stream.socket.getsockopt(
            socket.SOL_SOCKET,
            socket.SO_PEERCRED,
            struct.calcsize("3i"),
        )
        dummy_pid, uid, dummy_gid = struct.unpack("3i", credentials)
        if uid == 0:
            # treat root as cluster superuser
            return SUPERUSER

        return pwd.getpwuid(uid).pw_name

    def is_available(self) -> bool:
        return self._is_unix_socket_used()

    async def auth_user(self) -> AuthUser:
        username = self._get_unix_socket_user()
        if username:
            auth_user = await IOLoop.current().run_in_executor(
                executor=None,
                func=lambda: self._lib_auth_provider.login_user(username),
            )
            if auth_user:
                return auth_user
        raise NotAuthorizedException()


class UnixSocketAuthProviderFactory(ApiAuthProviderFactoryInterface):
    def create(self, handler: RequestHandler) -> UnixSocketAuthProvider:
        return UnixSocketAuthProvider(handler, self._lib_auth_provider)

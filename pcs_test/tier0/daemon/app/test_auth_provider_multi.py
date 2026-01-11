from unittest import IsolatedAsyncioTestCase, TestCase, mock

from pcs.daemon.app.auth import NotAuthorizedException
from pcs.daemon.app.auth_provider import (
    ApiAuthProviderFactoryInterface,
    ApiAuthProviderInterface,
    AuthProviderMulti,
    AuthProviderMultiFactory,
)
from pcs.lib.auth.types import AuthUser


class MockAuthProvider(ApiAuthProviderInterface):
    """Mock auth provider for testing."""

    def __init__(
        self,
        is_available_result: bool = True,
        auth_user_result: AuthUser = None,
        should_raise: bool = False,
    ):
        self._is_available_result = is_available_result
        self._auth_user_result = auth_user_result or AuthUser(
            "testuser", ["testgroup"]
        )
        self._should_raise = should_raise
        self.is_available_called = False
        self.auth_user_called = False

    def is_available(self) -> bool:
        self.is_available_called = True
        return self._is_available_result

    async def auth_user(self) -> AuthUser:
        self.auth_user_called = True
        if self._should_raise:
            raise NotAuthorizedException()
        return self._auth_user_result


class AuthProviderMultiTest(IsolatedAsyncioTestCase):
    def test_is_available_returns_true_on_first(self):
        provider1 = MockAuthProvider(is_available_result=True)
        provider2 = MockAuthProvider(is_available_result=True)

        multi = AuthProviderMulti([provider1, provider2])

        self.assertTrue(multi.is_available())
        self.assertTrue(provider1.is_available_called)
        self.assertFalse(provider2.is_available_called)

    def test_is_available_returns_true_on_next(self):
        provider1 = MockAuthProvider(is_available_result=False)
        provider2 = MockAuthProvider(is_available_result=False)
        provider3 = MockAuthProvider(is_available_result=True)

        multi = AuthProviderMulti([provider1, provider2, provider3])

        self.assertTrue(multi.is_available())
        self.assertTrue(provider1.is_available_called)
        self.assertTrue(provider2.is_available_called)
        self.assertTrue(provider3.is_available_called)

    def test_is_available_returns_false(self):
        provider1 = MockAuthProvider(is_available_result=False)
        provider2 = MockAuthProvider(is_available_result=False)

        multi = AuthProviderMulti([provider1, provider2])

        self.assertFalse(multi.is_available())
        self.assertTrue(provider1.is_available_called)
        self.assertTrue(provider2.is_available_called)

    async def test_auth_user_first_available_provider(self):
        user1 = AuthUser("user1", ["group1"])
        user2 = AuthUser("user2", ["group2"])
        provider1 = MockAuthProvider(
            is_available_result=True, auth_user_result=user1
        )
        provider2 = MockAuthProvider(
            is_available_result=True, auth_user_result=user2
        )

        multi = AuthProviderMulti([provider1, provider2])

        result = await multi.auth_user()

        self.assertEqual(result, user1)
        self.assertTrue(provider1.is_available_called)
        self.assertTrue(provider1.auth_user_called)
        # Second provider should not be checked or used
        self.assertFalse(provider2.is_available_called)
        self.assertFalse(provider2.auth_user_called)

    async def test_auth_user_falls_back_to_second_provider(self):
        user2 = AuthUser("user2", ["group2"])
        provider1 = MockAuthProvider(is_available_result=False)
        provider2 = MockAuthProvider(
            is_available_result=True, auth_user_result=user2
        )

        multi = AuthProviderMulti([provider1, provider2])

        result = await multi.auth_user()

        self.assertEqual(result, user2)
        self.assertTrue(provider1.is_available_called)
        self.assertFalse(provider1.auth_user_called)
        self.assertTrue(provider2.is_available_called)
        self.assertTrue(provider2.auth_user_called)

    async def test_no_providers_available(self):
        provider1 = MockAuthProvider(is_available_result=False)
        provider2 = MockAuthProvider(is_available_result=False)

        multi = AuthProviderMulti([provider1, provider2])

        with self.assertRaises(NotAuthorizedException):
            await multi.auth_user()


class MockAuthProviderFactory(ApiAuthProviderFactoryInterface):
    """Mock factory for creating mock providers."""

    def __init__(self, provider: MockAuthProvider):
        self.provider = provider
        self.create_called = False

    def create(self, handler):
        del handler
        self.create_called = True
        return self.provider


class AuthProviderMultiFactoryTest(TestCase):
    def test_factory_creates_providers(self):
        provider1 = MockAuthProvider()
        provider2 = MockAuthProvider()
        provider3 = MockAuthProvider()
        factory1 = MockAuthProviderFactory(provider1)
        factory2 = MockAuthProviderFactory(provider2)
        factory3 = MockAuthProviderFactory(provider3)

        multi_factory = AuthProviderMultiFactory([factory1, factory2, factory3])

        handler = mock.Mock()

        result = multi_factory.create(handler)

        self.assertIsInstance(result, AuthProviderMulti)
        self.assertEqual(len(result._providers), 3)
        self.assertEqual(result._providers[0], provider1)
        self.assertEqual(result._providers[1], provider2)
        self.assertEqual(result._providers[2], provider3)

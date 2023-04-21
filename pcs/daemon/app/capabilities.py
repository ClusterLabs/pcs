import json
from typing import Iterable

from tornado.web import HTTPError

from pcs.common.capabilities import Capability
from pcs.daemon.app.auth import (
    LegacyTokenAuthenticationHandler,
    NotAuthorizedException,
    TokenAuthProvider,
)
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from .common import (
    BaseHandler,
    RoutesType,
)


def _capabilities_to_str(capabilities: Iterable[Capability]) -> str:
    return json.dumps(
        {
            "pcsd_capabilities": [feat.code for feat in capabilities],
        }
    )


class LegacyCapabilitiesHandler(LegacyTokenAuthenticationHandler):
    _capabilities: Iterable[Capability]

    def initialize(
        self, auth_provider: AuthProvider, capabilities: Iterable[Capability]
    ) -> None:
        # pylint: disable=arguments-differ
        super().initialize(auth_provider)
        self._capabilities = capabilities

    async def _handle_request(self) -> None:
        self.write(_capabilities_to_str(self._capabilities))


class CapabilitiesHandler(BaseHandler):
    _auth_provider: TokenAuthProvider
    _capabilities: Iterable[Capability]

    def initialize(
        self, auth_provider: AuthProvider, capabilities: Iterable[Capability]
    ) -> None:
        super().initialize()
        self._auth_provider = TokenAuthProvider(self, auth_provider)
        self._capabilities = capabilities

    async def get_auth_user(self) -> AuthUser:
        try:
            return await self._auth_provider.auth_by_token()
        except NotAuthorizedException as e:
            raise HTTPError(401) from e

    async def get(self) -> None:
        await self.get_auth_user()
        self.add_header("Content-Type", "application/json")
        self.write(_capabilities_to_str(self._capabilities))


def get_routes(
    auth_provider: AuthProvider, capabilities: Iterable[Capability]
) -> RoutesType:
    """
    Returns mapping of URL routes to functions
    """
    params = dict(auth_provider=auth_provider, capabilities=capabilities)
    return [
        ("/remote/capabilities", LegacyCapabilitiesHandler, params),
        ("/capabilities", CapabilitiesHandler, params),
    ]

import json
from collections.abc import Iterable

from tornado.web import HTTPError

from pcs.common.capabilities import Capability
from pcs.daemon.app.auth_provider import (
    ApiAuthProviderFactoryInterface,
    ApiAuthProviderInterface,
    NotAuthorizedException,
)

from .common import BaseHandler, LegacyApiHandler, RoutesType


def _capabilities_to_str(capabilities: Iterable[Capability]) -> str:
    return json.dumps(
        {
            "pcsd_capabilities": [feat.code for feat in capabilities],
        }
    )


class LegacyCapabilitiesHandler(LegacyApiHandler):
    _auth_provider: ApiAuthProviderInterface
    _capabilities: Iterable[Capability]

    def initialize(
        self,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
        capabilities: Iterable[Capability],
    ) -> None:
        self._auth_provider = api_auth_provider_factory.create(self)
        self._capabilities = capabilities

    async def prepare(self) -> None:
        try:
            await self._auth_provider.auth_user()
        except NotAuthorizedException as e:
            raise self.unauthorized() from e

    async def _handle_request(self) -> None:
        self.write(_capabilities_to_str(self._capabilities))


class CapabilitiesHandler(BaseHandler):
    _auth_provider: ApiAuthProviderInterface
    _capabilities: Iterable[Capability]

    def initialize(
        self,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
        capabilities: Iterable[Capability],
    ) -> None:
        super().initialize()
        self._auth_provider = api_auth_provider_factory.create(self)
        self._capabilities = capabilities

    async def prepare(self) -> None:
        try:
            await self._auth_provider.auth_user()
        except NotAuthorizedException as e:
            raise HTTPError(401) from e

    async def get(self) -> None:
        self.add_header("Content-Type", "application/json")
        self.write(_capabilities_to_str(self._capabilities))


def get_routes(
    api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    capabilities: Iterable[Capability],
) -> RoutesType:
    """
    Returns mapping of URL routes to functions
    """
    params = dict(
        api_auth_provider_factory=api_auth_provider_factory,
        capabilities=capabilities,
    )
    return [
        ("/remote/capabilities", LegacyCapabilitiesHandler, params),
        ("/capabilities", CapabilitiesHandler, params),
    ]

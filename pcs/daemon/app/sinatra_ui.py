from pcs.daemon import ruby_pcsd
from pcs.daemon.app.auth import NotAuthorizedException
from pcs.daemon.app.auth_provider import (
    ApiAuthProviderFactoryInterface,
    ApiAuthProviderInterface,
)
from pcs.daemon.app.common import LegacyApiHandler, RoutesType
from pcs.daemon.app.sinatra_common import SinatraMixin
from pcs.daemon.app.ui_common import AjaxMixin


class SinatraAjaxProtected(LegacyApiHandler, SinatraMixin, AjaxMixin):
    """
    SinatraAjaxProtected handles urls that calls the ajax Sinatra GUI functions.
    It allows to use this urls only for ajax calls.
    """

    __auth_provider: ApiAuthProviderInterface

    def initialize(
        self,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    ) -> None:
        self.initialize_sinatra(ruby_pcsd_wrapper)
        self.__auth_provider = api_auth_provider_factory.create(self)

    def prepare(self) -> None:
        if not self.is_ajax:
            raise self.unauthorized()
        if not self.__auth_provider.can_handle_request():
            raise self.unauthorized()

    async def _handle_request(self):
        try:
            auth_user = await self.__auth_provider.auth_user()
        except NotAuthorizedException as e:
            raise self.unauthorized() from e

        result = await self.ruby_pcsd_wrapper.request(auth_user, self.request)
        self.send_sinatra_result(result)


def get_routes(
    api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
) -> RoutesType:
    return [
        # The protection by session was moved from ruby code to python code
        # (tornado).
        (
            r"/.*",
            SinatraAjaxProtected,
            dict(
                ruby_pcsd_wrapper=ruby_pcsd_wrapper,
                api_auth_provider_factory=api_auth_provider_factory,
            ),
        ),
    ]

from typing import Optional

from tornado.locks import Lock

from pcs.daemon import log, ruby_pcsd
from pcs.daemon.app.auth_provider import (
    ApiAuthProviderFactoryInterface,
    ApiAuthProviderInterface,
    NotAuthorizedException,
)
from pcs.daemon.app.common import (
    LegacyApiHandler,
    RoutesType,
    get_legacy_desired_user_from_request,
)
from pcs.daemon.app.sinatra_common import SinatraMixin
from pcs.daemon.http_server import HttpsServerManage
from pcs.lib.auth.tools import get_effective_user
from pcs.lib.auth.types import AuthUser


class SinatraRemote(LegacyApiHandler, SinatraMixin):
    """
    SinatraRemote is handler for urls which should be directed to the Sinatra
    remote (non-GUI) functions.
    """

    _auth_provider: ApiAuthProviderInterface
    _effective_user: Optional[AuthUser]

    def initialize(
        self,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
    ) -> None:
        self._auth_provider = api_auth_provider_factory.create(self)
        self.initialize_sinatra(ruby_pcsd_wrapper)

    async def prepare(self) -> None:
        try:
            real_user = await self._auth_provider.auth_user()
        except NotAuthorizedException as e:
            raise self.unauthorized() from e

        # ignore the desired user for non-root users
        if not real_user.is_superuser:
            self._effective_user = real_user
            return

        # allow root user to lower their privileges
        desired_user = get_legacy_desired_user_from_request(self, log.pcsd)
        self._effective_user = get_effective_user(real_user, desired_user)

    @property
    def effective_user(self) -> AuthUser:
        if self._effective_user is None:
            raise self.unauthorized()
        return self._effective_user

    async def _handle_request(self) -> None:
        result = await self.ruby_pcsd_wrapper.request(
            self.effective_user, self.request
        )
        self.send_sinatra_result(result)


class SyncConfigMutualExclusive(SinatraRemote):
    """
    SyncConfigMutualExclusive handles urls which should be directed to the
    Sinatra remote (non-GUI) functions that can not run at the same time as
    config synchronization. The exclusivity is achieved by sync_config_lock.
    """

    __sync_config_lock: Lock

    def initialize(  # type: ignore[override]
        self,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
        sync_config_lock: Lock,
    ) -> None:
        super().initialize(api_auth_provider_factory, ruby_pcsd_wrapper)
        self.__sync_config_lock = sync_config_lock

    async def _handle_request(self) -> None:
        async with self.__sync_config_lock:
            await super()._handle_request()


class SetCerts(SinatraRemote):
    """
    SetCerts handles url for setting new certificate and key. It calls the
    Sinatra for setting certificate and key and in the case of the success it
    will take care of notify of http sever about this change.
    """

    __https_server_manage: HttpsServerManage

    def initialize(  # type: ignore[override]
        self,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
        https_server_manage: HttpsServerManage,
    ) -> None:
        super().initialize(api_auth_provider_factory, ruby_pcsd_wrapper)
        self.__https_server_manage = https_server_manage

    async def _handle_request(self) -> None:
        result = await self.ruby_pcsd_wrapper.request(
            self.effective_user, self.request
        )
        if result.status == 200:
            self.__https_server_manage.reload_certs()
        self.send_sinatra_result(result)


def get_routes(
    api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
    sync_config_lock: Lock,
    https_server_manage: HttpsServerManage,
) -> RoutesType:
    sinatra_remote_options = dict(
        api_auth_provider_factory=api_auth_provider_factory,
        ruby_pcsd_wrapper=ruby_pcsd_wrapper,
    )

    return [
        # Urls protected by tokens. It is still done by ruby pcsd.
        (r"/run_pcs", SinatraRemote, sinatra_remote_options),
        (
            r"/remote/set_certs",
            SetCerts,
            dict(
                **sinatra_remote_options,
                https_server_manage=https_server_manage,
            ),
        ),
        (
            r"/remote/set_configs",
            SyncConfigMutualExclusive,
            dict(**sinatra_remote_options, sync_config_lock=sync_config_lock),
        ),
        (r"/remote/.*", SinatraRemote, sinatra_remote_options),
    ]

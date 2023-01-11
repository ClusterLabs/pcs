from typing import Optional

from tornado.locks import Lock

from pcs.daemon import ruby_pcsd
from pcs.daemon.app.auth import (
    LegacyTokenAuthenticationHandler,
    TokenAuthProvider,
)
from pcs.daemon.app.sinatra_common import SinatraMixin
from pcs.daemon.http_server import HttpsServerManage
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser


class SinatraRemote(LegacyTokenAuthenticationHandler, SinatraMixin):
    """
    SinatraRemote is handler for urls which should be directed to the Sinatra
    remote (non-GUI) functions.
    """

    _token_auth_provider: TokenAuthProvider
    _auth_user: Optional[AuthUser]

    def initialize(
        self, ruby_pcsd_wrapper: ruby_pcsd.Wrapper, auth_provider: AuthProvider
    ) -> None:
        # pylint: disable=arguments-differ
        super().initialize(auth_provider)
        self.initialize_sinatra(ruby_pcsd_wrapper)

    async def _handle_request(self):
        result = await self.ruby_pcsd_wrapper.request(
            self.auth_user, self.request
        )
        self.send_sinatra_result(result)


class SyncConfigMutualExclusive(SinatraRemote):
    """
    SyncConfigMutualExclusive handles urls which should be directed to the
    Sinatra remote (non-GUI) functions that can not run at the same time as
    config synchronization. The exclusivity is achieved by sync_config_lock.
    """

    __sync_config_lock: Lock

    def initialize(
        self,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
        auth_provider: AuthProvider,
        sync_config_lock: Lock,
    ) -> None:
        # pylint: disable=arguments-differ
        super().initialize(ruby_pcsd_wrapper, auth_provider)
        self.__sync_config_lock = sync_config_lock

    async def _handle_request(self):
        async with self.__sync_config_lock:
            await super()._handle_request()


class SetCerts(SinatraRemote):
    """
    SetCerts handles url for setting new certificate and key. It calls the
    Sinatra for setting certificate and key and in the case of the success it
    will take care of notify of http sever about this change.
    """

    __https_server_manage: HttpsServerManage

    def initialize(
        self,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
        auth_provider: AuthProvider,
        https_server_manage: HttpsServerManage,
    ):
        # pylint: disable=arguments-differ
        super().initialize(ruby_pcsd_wrapper, auth_provider)
        self.__https_server_manage = https_server_manage

    async def _handle_request(self):
        result = await self.ruby_pcsd_wrapper.request(
            self.auth_user, self.request
        )
        if result.status == 200:
            self.__https_server_manage.reload_certs()
        self.send_sinatra_result(result)


def get_routes(
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
    sync_config_lock: Lock,
    https_server_manage: HttpsServerManage,
    auth_provider: AuthProvider,
):
    sinatra_remote_options = dict(
        ruby_pcsd_wrapper=ruby_pcsd_wrapper, auth_provider=auth_provider
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
            r"/remote/(set_sync_options|set_configs)",
            SyncConfigMutualExclusive,
            dict(**sinatra_remote_options, sync_config_lock=sync_config_lock),
        ),
        (r"/remote/.*", SinatraRemote, sinatra_remote_options),
    ]

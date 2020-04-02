from tornado.locks import Lock

from pcs.daemon import ruby_pcsd
from pcs.daemon.app.sinatra_common import Sinatra
from pcs.daemon.http_server import HttpsServerManage
from pcs.daemon.auth import authorize_user


class SinatraRemote(Sinatra):
    """
    SinatraRemote is handler for urls which should be directed to the Sinatra
    remote (non-GUI) functions.
    """

    async def handle_sinatra_request(self):
        result = await self.ruby_pcsd_wrapper.request_remote(self.request)
        self.send_sinatra_result(result)

    async def get(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()

    async def post(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()


class SyncConfigMutualExclusive(SinatraRemote):
    """
    SyncConfigMutualExclusive handles urls which should be directed to the
    Sinatra remote (non-GUI) functions that can not run at the same time as
    config synchronization. The exclusivity is achived by sync_config_lock.
    """

    def initialize(
        self, sync_config_lock: Lock, ruby_pcsd_wrapper: ruby_pcsd.Wrapper
    ):
        # pylint: disable=arguments-differ, attribute-defined-outside-init
        super().initialize(ruby_pcsd_wrapper)
        self.__sync_config_lock = sync_config_lock

    async def get(self, *args, **kwargs):
        async with self.__sync_config_lock:
            await super().get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        async with self.__sync_config_lock:
            await super().get(*args, **kwargs)


class SetCerts(SinatraRemote):
    """
    SetCerts handles url for setting new certificate and key. It calls the
    Sinatra for setting certificate and key and in the case of the success it
    will take care of notify of http sever about this change.
    """

    def initialize(
        self,
        ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
        https_server_manage: HttpsServerManage,
    ):
        # pylint: disable=arguments-differ, attribute-defined-outside-init
        super().initialize(ruby_pcsd_wrapper)
        self.__https_server_manage = https_server_manage

    async def handle_sinatra_request(self):
        result = await self.ruby_pcsd_wrapper.request_remote(self.request)
        if result.status == 200:
            self.__https_server_manage.reload_certs()
        self.send_sinatra_result(result)


class Auth(SinatraRemote):
    async def auth(self):
        user_auth_info = await authorize_user(
            self.get_body_argument("username"),
            self.get_body_argument("password"),
        )
        if user_auth_info.is_authorized:
            await self.handle_sinatra_request()

    async def post(self, *args, **kwargs):
        await self.auth()

    async def get(self, *args, **kwargs):
        await self.auth()


def get_routes(
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
    sync_config_lock: Lock,
    https_server_manage: HttpsServerManage,
):
    ruby_wrapper = dict(ruby_pcsd_wrapper=ruby_pcsd_wrapper)
    lock = dict(sync_config_lock=sync_config_lock)
    server_manage = dict(https_server_manage=https_server_manage)

    return [
        # Urls protected by tokens. It is still done by ruby pcsd.
        (r"/run_pcs", SinatraRemote, ruby_wrapper),
        (r"/remote/set_certs", SetCerts, {**ruby_wrapper, **server_manage}),
        (
            r"/remote/(set_sync_options|set_configs)",
            SyncConfigMutualExclusive,
            {**ruby_wrapper, **lock},
        ),
        (r"/remote/auth", Auth, ruby_wrapper),
        (r"/remote/.*", SinatraRemote, ruby_wrapper),
    ]

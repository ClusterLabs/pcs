from pcs.daemon import (
    ruby_pcsd,
    session,
)
from pcs.daemon.app import session as app_session
from pcs.daemon.app.sinatra_common import Sinatra
from pcs.daemon.app.ui_common import AjaxMixin
from pcs.daemon.auth import check_user_groups


class SinatraAjaxProtected(app_session.Mixin, Sinatra, AjaxMixin):
    # pylint: disable=too-many-ancestors
    """
    SinatraAjaxProtected handles urls that calls the ajax Sinatra GUI functions.
    It allows to use this urls only for ajax calls.
    """

    def initialize(self, session_storage, ruby_pcsd_wrapper):
        # pylint: disable=arguments-differ
        app_session.Mixin.initialize(self, session_storage)
        Sinatra.initialize(self, ruby_pcsd_wrapper)

    async def handle_sinatra_request(self):
        self.init_session()
        if self.session.is_authenticated:
            self.session_refresh_auth(
                await check_user_groups(self.session.username),
                sign_rejection=True,
            )

        # TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()
        if not self.is_authorized:
            raise self.unauthorized()

        result = await self.ruby_pcsd_wrapper.request_gui(
            self.request,
            self.session.username,
            self.session.groups,
        )
        self.send_sinatra_result(result)

    async def get(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()

    async def post(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()

    @property
    def is_authorized(self):
        # User is authorized only to perform ajax calls to prevent CSRF attack.
        return self.is_ajax and self.session.is_authenticated


def get_routes(
    session_storage: session.Storage,
    ruby_pcsd_wrapper: ruby_pcsd.Wrapper,
):
    ruby_wrapper = dict(ruby_pcsd_wrapper=ruby_pcsd_wrapper)
    sessions = dict(session_storage=session_storage)
    return [
        # The protection by session was moved from ruby code to python code
        # (tornado).
        (r"/.*", SinatraAjaxProtected, {**sessions, **ruby_wrapper}),
    ]

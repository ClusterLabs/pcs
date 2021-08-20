from pcs.daemon import ruby_pcsd, session
from pcs.daemon.app import session as app_session
from pcs.daemon.app.sinatra_common import Sinatra
from pcs.daemon.app.ui_common import AjaxMixin


class SinatraGui(app_session.Mixin, Sinatra):
    """
    SinatraGui is base class for handlers which calls the Sinatra GUI functions.
    It adds work with session.
    It adds default GET and POST handlers with hook before Sinatra is called.
    """

    can_use_sinatra = True

    def initialize(self, session_storage, ruby_pcsd_wrapper):
        # pylint: disable=arguments-differ
        app_session.Mixin.initialize(self, session_storage)
        Sinatra.initialize(self, ruby_pcsd_wrapper)
        # add security related headers to all responses
        self.enhance_headers()

    def before_sinatra_use(self):
        pass

    async def handle_sinatra_request(self):
        await self.init_session()
        self.before_sinatra_use()
        if self.can_use_sinatra:
            result = await self.ruby_pcsd_wrapper.request_gui(
                self.request,
                self.session.username,
                self.session.groups,
                self.session.is_authenticated,
            )
            self.send_sinatra_result(result)

    async def get(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()

    async def post(self, *args, **kwargs):
        del args, kwargs
        await self.handle_sinatra_request()


class SinatraAjaxProtected(SinatraGui, AjaxMixin):
    # pylint: disable=too-many-ancestors
    """
    SinatraAjaxProtected handles urls that calls the ajax Sinatra GUI functions.
    It allows to use this urls only for ajax calls.
    """

    @property
    def is_authorized(self):
        # User is authorized only to perform ajax calls to prevent CSRF attack.
        return self.is_ajax and self.session.is_authenticated

    def before_sinatra_use(self):
        # TODO this is for sinatra compatibility, review it.
        if self.was_sid_in_request_cookies():
            self.put_request_cookies_sid_to_response_cookies_sid()
        if not self.is_authorized:
            raise self.unauthorized()


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

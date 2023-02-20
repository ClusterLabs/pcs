from pcs.daemon import ruby_pcsd
from pcs.daemon.app.common import BaseHandler


class Sinatra(BaseHandler):
    """
    Sinatra is base class for handlers which calls the Sinatra via wrapper.
    It accept ruby wrapper during initialization. It also provides method for
    transformation result from sinatra to http response.
    """

    def initialize(self, ruby_pcsd_wrapper: ruby_pcsd.Wrapper):
        # pylint: disable=arguments-differ, attribute-defined-outside-init
        self.__ruby_pcsd_wrapper = ruby_pcsd_wrapper

    def send_sinatra_result(self, result: ruby_pcsd.SinatraResult):
        for name, value in result.headers.items():
            self.set_header(name, value)
        # make sure that security related headers, which need to be present in
        # all responses, are not overridden by sinatra
        self.set_default_headers()
        if result.status == 401 and result.body == b'{"notauthorized":"true"}':
            self.set_header_content_security_policy_extended()
        self.set_status(result.status)
        self.write(result.body)

    @property
    def ruby_pcsd_wrapper(self):
        return self.__ruby_pcsd_wrapper

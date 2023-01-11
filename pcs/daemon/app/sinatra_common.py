from pcs.daemon import ruby_pcsd


class SinatraMixin:
    """
    Sinatra is base class for handlers which calls the Sinatra via wrapper.
    It accept ruby wrapper during initialization. It also provides method for
    transformation result from sinatra to http response.
    """

    __ruby_pcsd_wrapper: ruby_pcsd.Wrapper

    def initialize_sinatra(self, ruby_pcsd_wrapper: ruby_pcsd.Wrapper):
        self.__ruby_pcsd_wrapper = ruby_pcsd_wrapper

    def send_sinatra_result(self, result: ruby_pcsd.SinatraResult):
        for name, value in result.headers.items():
            self.set_header(name, value)
        # make sure that security related headers, which need to be present in
        # all responses, are not overridden by sinatra
        self.set_default_headers()
        self.set_status(result.status)
        self.write(result.body)

    @property
    def ruby_pcsd_wrapper(self):
        return self.__ruby_pcsd_wrapper

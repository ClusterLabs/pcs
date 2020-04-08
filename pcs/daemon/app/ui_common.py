import hashlib

from tornado.web import Finish, StaticFileHandler

from pcs.daemon.app.common import EnhanceHeadersMixin


class AjaxMixin:
    """
    AjaxMixin adds methods for an ajax request detection and common unauthorized
    response.
    """

    @property
    def is_ajax(self):
        return (
            self.request.headers.get("X-Requested-With", default=None)
            == "XMLHttpRequest"
        )

    def unauthorized(self):
        self.set_status(401)
        self.write('{"notauthorized":"true"}')
        return Finish()


class StaticFile(EnhanceHeadersMixin, StaticFileHandler):
    # abstract method `data_received` does need to be overriden. This
    # method should be implemented to handle streamed request data.
    # BUT static files are not streamed SO:
    # pylint: disable=abstract-method
    def initialize(self, path, default_filename=None):
        # pylint: disable=arguments-differ
        super().initialize(path, default_filename)
        # In ruby server the header X-Content-Type-Options was sent and we
        # keep it here to keep compatibility for simplifying testing. There is
        # no another special reason for it. So, maybe, it can be removed in
        # future.
        self.set_header_nosniff_content_type()
        self.set_strict_transport_security()

    @classmethod
    def get_content_version(cls, abspath: str) -> str:
        """
        Returns a version string for the resource at the given path.

        Overriding tornado method. Original method uses hashlib.md5 which
        doesn't work with FIPS.
        """
        data = cls.get_content(abspath)
        hasher = hashlib.sha1()
        if isinstance(data, bytes):
            hasher.update(data)
        else:
            for chunk in data:
                hasher.update(chunk)
        return hasher.hexdigest()

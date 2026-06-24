from tornado.web import StaticFileHandler

from pcs.daemon.app.common import EnhanceHeadersMixin


class AjaxMixin:
    @property
    def is_ajax(self) -> bool:
        request = self.request  # type: ignore[attr-defined]
        return (
            request.headers.get("X-Requested-With", default=None)
            == "XMLHttpRequest"
        )


class StaticFile(EnhanceHeadersMixin, StaticFileHandler):
    # abstract method `data_received` does need to be overridden. This
    # method should be implemented to handle streamed request data.
    # BUT static files are not streamed SO:
    # pylint: disable=abstract-method
    def initialize(
        self, path: str, default_filename: str | None = None
    ) -> None:
        super().initialize(path, default_filename)
        # allow static files to be cached
        self.clear_header_cache_control()

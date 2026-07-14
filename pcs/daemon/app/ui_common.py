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
    def initialize(
        self, path: str, default_filename: str | None = None
    ) -> None:
        super().initialize(path, default_filename)
        # allow static files to be cached
        self.clear_header_cache_control()

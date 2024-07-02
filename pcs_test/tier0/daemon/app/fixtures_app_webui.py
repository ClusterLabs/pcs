try:
    from pcs.daemon.app import webui
except ImportError:
    # You need to skip tests in tests that uses AppTest in the case webui
    # is not there.
    webui = None

from pcs_test.tier0.daemon.app import fixtures_app


class AppTest(fixtures_app.AppTest):
    def setUp(self):
        self.session_storage = webui.session.Storage(lifetime_seconds=10)
        super().setUp()

    def fetch(self, path, raise_error=False, **kwargs):
        if "sid" in kwargs:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"][
                "Cookie"
            ] = f"{webui.auth.PCSD_SESSION}={kwargs['sid']}"
            del kwargs["sid"]

        return super().fetch(path, raise_error=raise_error, **kwargs)

    def create_login_session(self):
        return self.session_storage.login(fixtures_app.USER)

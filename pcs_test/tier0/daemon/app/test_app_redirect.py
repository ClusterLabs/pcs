from pcs_test.tier0.daemon.app.fixtures_app import AppTest
from pcs.daemon.app.common import RedirectHandler

MANAGE = "/manage"

class RedirectTest(AppTest):
    def get_routes(self):
        return [(r"/", RedirectHandler, dict(url=MANAGE))]

    def test_redirects_to_given_location(self):
        response = self.get('/')
        self.assert_headers_contains(response.headers, {"Location": MANAGE})
        self.assertEqual(response.code, 301)

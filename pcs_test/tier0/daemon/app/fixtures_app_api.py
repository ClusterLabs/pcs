from typing import Any, Optional

from tornado.httputil import HTTPHeaders
from tornado.testing import AsyncHTTPTestCase

from pcs.common import reports
from pcs.common.reports.dto import ReportItemDto
from pcs.common.tools import bin_to_str
from pcs.daemon.app.api_v0_tools import SimplifiedResult


class ApiTestBase(AsyncHTTPTestCase):
    """
    Base class for API handler tests with common assertion utilities
    """

    maxDiff = None

    def assert_body(self, val1, val2):
        """
        Assert that two values are equal, converting bytes to str for better diff output
        """

        # TestCase.assertEqual doesn't print full diff when instances of bytes
        # don't match. We want to see the whole diff, so we transform bytes to
        # str. As a bonus, we dont need to specify expected value as bytes.
        def to_str(value):
            return bin_to_str(value) if isinstance(value, bytes) else value

        return self.assertEqual(to_str(val1), to_str(val2))

    def assert_headers(self, headers: HTTPHeaders) -> None:
        """
        Assert that response headers contain required security headers and no banned headers
        """
        banned_headers = {"Server"}
        required_headers = {
            "Cache-Control": "no-store, no-cache",
            "Content-Security-Policy": "frame-ancestors 'self'; default-src 'self'",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "Strict-Transport-Security": "max-age=63072000",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "X-Xss-Protection": "1; mode=block",
        }
        required_real_headers = [
            hdr for hdr in headers.get_all() if hdr[0] in required_headers
        ]
        banned_real_headers = {
            hdr[0] for hdr in headers.get_all() if hdr[0] in banned_headers
        }
        self.assertEqual(
            sorted(required_headers.items()),
            sorted(required_real_headers),
            "Required headers are not present",
        )
        self.assertEqual(
            sorted(banned_real_headers), [], "Banned headers are present"
        )

    @staticmethod
    def result_success(
        result: Any = None, reports: Optional[list[ReportItemDto]] = None
    ) -> SimplifiedResult:
        """
        Create a successful SimplifiedResult for testing
        """
        return SimplifiedResult(True, result, reports or [])

    @staticmethod
    def result_failure(
        result: Any = None,
        report_items: Optional[list[ReportItemDto]] = None,
    ) -> SimplifiedResult:
        """
        Create a failed SimplifiedResult for testing
        """
        return SimplifiedResult(False, result, report_items or [])

    def assert_error_with_report(self, url, **kwargs):
        """
        Test that the handler returns http 400 and report items in body.
        This method requires self.mock_process_request to be set up.
        """
        # The actual report items don't matter, we can pick any simple report item.
        self.mock_process_request.return_value = self.result_failure(
            "some error",
            [
                reports.ReportItem.error(
                    reports.messages.StonithUnfencingFailed("an error"),
                    context=reports.ReportItemContext("node1"),
                ).to_dto()
            ],
        )
        response = self.fetch(url, **kwargs)
        self.assert_body(
            response.body, "Error: node1: Unfencing failed:\nan error"
        )
        self.assertEqual(response.code, 400)

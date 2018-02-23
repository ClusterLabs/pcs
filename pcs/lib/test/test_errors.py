from pcs.test.tools.pcs_unittest import TestCase

from pcs.lib import errors


class LibraryEnvErrorTest(TestCase):
    def test_can_sign_solved_reports(self):
        e = errors.LibraryEnvError("first", "second", "third")
        for report in e.args:
            if report == "second":
                e.sign_processed(report)

        self.assertEqual(["first", "third"], e.unprocessed)

class ReportListAnalyzerSelectSeverities(TestCase):
    def setUp(self):
        self.severities = [
            errors.ReportItemSeverity.WARNING,
            errors.ReportItemSeverity.INFO,
            errors.ReportItemSeverity.DEBUG,
        ]

    def assert_select_reports(self, all_reports, expected_errors):
        self.assertEqual(
            expected_errors,
            errors.ReportListAnalyzer(all_reports)
                .reports_with_severities(self.severities)
        )

    def test_returns_empty_on_no_reports(self):
        self.assert_select_reports([], [])

    def test_returns_empty_on_reports_with_other_severities(self):
        self.assert_select_reports([errors.ReportItem.error("ERR")], [])

    def test_returns_selection_of_desired_severities(self):
        err = errors.ReportItem.error("ERR")
        warn = errors.ReportItem.warning("WARN")
        info = errors.ReportItem.info("INFO")
        debug = errors.ReportItem.debug("DEBUG")
        self.assert_select_reports(
            [
                err,
                warn,
                info,
                debug,
            ],
            [
                warn,
                info,
                debug,
            ]
        )

class ReportListAnalyzerErrorList(TestCase):
    def assert_select_reports(self, all_reports, expected_errors):
        self.assertEqual(
            expected_errors,
            errors.ReportListAnalyzer(all_reports).error_list
        )

    def test_returns_empty_on_no_reports(self):
        self.assert_select_reports([], [])

    def test_returns_empty_on_no_errors(self):
        self.assert_select_reports([errors.ReportItem.warning("WARN")], [])

    def test_returns_only_errors_on_mixed_content(self):
        err = errors.ReportItem.error("ERR")
        self.assert_select_reports(
            [errors.ReportItem.warning("WARN"), err],
            [err]
        )

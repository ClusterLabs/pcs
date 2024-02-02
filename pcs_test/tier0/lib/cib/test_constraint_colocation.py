from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.cib.constraint import colocation

from pcs_test.tools.assertions import assert_raise_library_error


class IsColocationConstraint(TestCase):
    def test_colocation_constraint_true(self):
        self.assertTrue(
            colocation.is_colocation_constraint(etree.Element("rsc_colocation"))
        )

    def test_colocation_constraint_false(self):
        self.assertFalse(
            colocation.is_colocation_constraint(etree.Element("colocation"))
        )


# Patch check_new_id_applicable is always desired when working with
# prepare_options_with_set. Patched function raises when id not applicable
# and do nothing when applicable - in this case tests do no actions with it
@mock.patch("pcs.lib.cib.constraint.colocation.check_new_id_applicable")
class PrepareOptionsWithSetTest(TestCase):
    def setUp(self):
        self.cib = "cib"
        self.resource_set_list = "resource_set_list"
        self.prepare = lambda options: colocation.prepare_options_with_set(
            self.cib,
            options,
            self.resource_set_list,
        )

    @mock.patch("pcs.lib.cib.constraint.colocation.constraint.create_id")
    def test_complete_id(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        options = {"score": "1"}
        expected_options = options.copy()
        expected_options.update({"id": "generated_id"})
        self.assertEqual(expected_options, self.prepare(options))
        mock_create_id.assert_called_once_with(
            self.cib, "colocation", self.resource_set_list
        )

    def test_refuse_invalid_id(self, mock_check_new_id_applicable):
        mock_check_new_id_applicable.side_effect = Exception()
        invalid_id = "invalid_id"
        self.assertRaises(
            Exception,
            lambda: self.prepare(
                {
                    "score": "1",
                    "id": invalid_id,
                }
            ),
        )
        mock_check_new_id_applicable.assert_called_once_with(
            self.cib, "constraint id", invalid_id
        )

    def test_refuse_bad_score(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {
                    "score": "bad",
                    "id": "id",
                }
            ),
            (severities.ERROR, report_codes.INVALID_SCORE, {"score": "bad"}),
        )

    def test_refuse_unknown_attributes(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {
                    "score": "1",
                    "unknown": "value",
                    "id": "id",
                }
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["unknown"],
                    "option_type": None,
                    "allowed": ["id", "score"],
                    "allowed_patterns": [],
                },
            ),
        )

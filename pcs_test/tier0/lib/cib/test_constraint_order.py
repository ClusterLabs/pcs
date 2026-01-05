from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.cib.constraint import order
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import BOOLEAN_VALUES

from pcs_test.tools.assertions import assert_raise_library_error


class IsOrderConstraint(TestCase):
    def test_order_constraint_true(self):
        self.assertTrue(order.is_order_constraint(etree.Element("rsc_order")))

    def test_order_constraint_false(self):
        self.assertFalse(order.is_order_constraint(etree.Element("order")))


# Patch check_new_id_applicable is always desired when working with
# prepare_options_with_set. Patched function raises when id not applicable
# and do nothing when applicable - in this case tests do no actions with it
@mock.patch("pcs.lib.cib.constraint.order.check_new_id_applicable")
class PrepareOptionsWithSetTest(TestCase):
    def setUp(self):
        self.cib = "cib"
        self.resource_set_list = "resource_set_list"
        self.prepare = lambda options: order.prepare_options_with_set(
            self.cib,
            options,
            self.resource_set_list,
        )

    @mock.patch("pcs.lib.cib.constraint.order.constraint.create_id")
    def test_complete_id(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        options = {"symmetrical": "true", "kind": "Optional"}
        expected_options = options.copy()
        expected_options.update({"id": "generated_id"})
        self.assertEqual(expected_options, self.prepare(options))
        mock_create_id.assert_called_once_with(
            self.cib, "order", self.resource_set_list
        )

    def test_refuse_invalid_id(self, mock_check_new_id_applicable):
        mock_check_new_id_applicable.side_effect = LibraryError()
        invalid_id = "invalid_id"
        self.assertRaises(
            LibraryError,
            lambda: self.prepare(
                {
                    "symmetrical": "true",
                    "kind": "Optional",
                    "id": invalid_id,
                }
            ),
        )
        mock_check_new_id_applicable.assert_called_once_with(
            self.cib, "constraint id", invalid_id
        )

    def test_refuse_unknown_kind(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {
                    "symmetrical": "true",
                    "kind": "unknown",
                    "id": "id",
                }
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "allowed_values": ("Optional", "Mandatory", "Serialize"),
                    "option_value": "unknown",
                    "option_name": "kind",
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
            ),
        )

    def test_refuse_unknown_symmetrical(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {
                    "symmetrical": "unknown",
                    "kind": "Optional",
                    "id": "id",
                }
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "allowed_values": BOOLEAN_VALUES,
                    "option_value": "unknown",
                    "option_name": "symmetrical",
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
            ),
        )

    def test_refuse_unknown_attributes(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {
                    "symmetrical": "unknown",
                    "kind": "Optional",
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
                    "allowed": ["id", "kind", "symmetrical"],
                    "allowed_patterns": [],
                },
            ),
        )

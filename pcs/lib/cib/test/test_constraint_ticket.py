from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial
from pcs.test.tools.pcs_unittest import TestCase

from pcs.common import report_codes
from pcs.lib.cib.constraint import ticket
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.pcs_mock import mock


@mock.patch("pcs.lib.cib.constraint.ticket.tools.check_new_id_applicable")
class PrepareOptionsPlainTest(TestCase):
    def setUp(self):
        self.cib = "cib"
        self.prepare = partial(ticket.prepare_options_plain, self.cib)

    @mock.patch("pcs.lib.cib.constraint.ticket._create_id")
    def test_prepare_correct_options(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        self.assertEqual(
            {
                'id': 'generated_id',
                'loss-policy': 'fence',
                'rsc': 'resourceA',
                'rsc-role': 'Master',
                'ticket': 'ticket_key'
            },
            self.prepare(
                {"loss-policy": "fence", "rsc-role": "master"},
                "ticket_key",
                "resourceA",
            )
        )

    @mock.patch("pcs.lib.cib.constraint.ticket._create_id")
    def test_does_not_include_role_if_not_presented(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        self.assertEqual(
            {
                'id': 'generated_id',
                'loss-policy': 'fence',
                'rsc': 'resourceA',
                'ticket': 'ticket_key'
            },
            self.prepare(
                {"loss-policy": "fence", "rsc-role": ""},
                "ticket_key",
                "resourceA",
            )
        )

    def test_refuse_unknown_attributes(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"unknown": "nonsense", "rsc-role": "master"},
                "ticket_key",
                "resourceA",
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option_name": "unknown",
                    "option_type": None,
                    "allowed": ["id", "loss-policy", "rsc", "rsc-role", "ticket"],
                }
            ),
        )

    def test_refuse_bad_role(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"id": "id", "rsc-role": "bad_role"}, "ticket_key", "resourceA"
            ),
            (severities.ERROR, report_codes.INVALID_OPTION_VALUE, {
                'allowed_values': ('Stopped', 'Started', 'Master', 'Slave'),
                'option_value': 'bad_role',
                'option_name': 'rsc-role',
            }),
        )

    def test_refuse_missing_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"id": "id", "rsc-role": "master"}, "", "resourceA"
            ),
            (
                severities.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {
                    "option_name": "ticket"
                }
            ),
        )

    def test_refuse_missing_resource_id(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"id": "id", "rsc-role": "master"}, "ticket_key", ""
            ),
            (
                severities.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {
                    "option_name": "rsc",
                }
            ),
        )


    def test_refuse_unknown_lost_policy(self, mock_check_new_id_applicable):
        assert_raise_library_error(
            lambda: self.prepare(
                { "loss-policy": "unknown", "ticket": "T", "id": "id"},
                "ticket_key",
                "resourceA",
            ),
            (severities.ERROR, report_codes.INVALID_OPTION_VALUE, {
                'allowed_values': ('fence', 'stop', 'freeze', 'demote'),
                'option_value': 'unknown',
                'option_name': 'loss-policy',
            }),
        )

    @mock.patch("pcs.lib.cib.constraint.ticket._create_id")
    def test_complete_id(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        options = {"loss-policy": "freeze", "ticket": "T", "rsc-role": "Master"}
        ticket_key = "ticket_key"
        resource_id = "resourceA"
        expected_options = options.copy()
        expected_options.update({
            "id": "generated_id",
            "rsc": resource_id,
            "rsc-role": "Master",
            "ticket": ticket_key,
        })
        self.assertEqual(expected_options, self.prepare(
            options,
            ticket_key,
            resource_id,
        ))
        mock_create_id.assert_called_once_with(
            self.cib,
            ticket_key,
            resource_id,
            "Master",
        )


#Patch check_new_id_applicable is always desired when working with
#prepare_options_with_set. Patched function raises when id not applicable
#and do nothing when applicable - in this case tests do no actions with it
@mock.patch("pcs.lib.cib.constraint.ticket.tools.check_new_id_applicable")
class PrepareOptionsWithSetTest(TestCase):
    def setUp(self):
        self.cib = "cib"
        self.resource_set_list = "resource_set_list"
        self.prepare = lambda options: ticket.prepare_options_with_set(
            self.cib,
            options,
            self.resource_set_list,
        )

    @mock.patch("pcs.lib.cib.constraint.ticket.constraint.create_id")
    def test_complete_id(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        options = {"loss-policy": "freeze", "ticket": "T"}
        expected_options = options.copy()
        expected_options.update({"id": "generated_id"})
        self.assertEqual(expected_options, self.prepare(options))
        mock_create_id.assert_called_once_with(
            self.cib,
            ticket.TAG_NAME,
            self.resource_set_list
        )

    def test_refuse_invalid_id(self, mock_check_new_id_applicable):
        class SomeException(Exception):
            pass
        mock_check_new_id_applicable.side_effect = SomeException()
        invalid_id = "invalid_id"
        self.assertRaises(SomeException, lambda: self.prepare({
            "loss-policy": "freeze",
            "ticket": "T",
            "id": invalid_id,
        }))
        mock_check_new_id_applicable.assert_called_once_with(
            self.cib,
            ticket.DESCRIPTION,
            invalid_id
        )

    def test_refuse_unknown_lost_policy(self, _):
        assert_raise_library_error(
            lambda: self.prepare({
                "loss-policy": "unknown",
                "ticket": "T",
                "id": "id",
            }),
            (severities.ERROR, report_codes.INVALID_OPTION_VALUE, {
                'allowed_values': ('fence', 'stop', 'freeze', 'demote'),
                'option_value': 'unknown',
                'option_name': 'loss-policy',
            }),
        )

    def test_refuse_missing_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare({"loss-policy": "stop", "id": "id"}),
            (
                severities.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {"option_name": "ticket"}
            )
        )

    def test_refuse_empty_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare({
                "loss-policy": "stop",
                "id": "id",
                "ticket": " "
            }),
            (
                severities.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {"option_name": "ticket"}
            )
        )

class Element(object):
    def __init__(self, attrib):
        self.attrib = attrib

    def update(self, attrib):
        self.attrib.update(attrib)
        return self


class AreDuplicatePlain(TestCase):
    def setUp(self):
        self.first = Element({
            "ticket": "ticket_key",
            "rsc": "resurceA",
            "rsc-role": "Master"
        })
        self.second = Element({
            "ticket": "ticket_key",
            "rsc": "resurceA",
            "rsc-role": "Master"
        })

    def test_returns_true_for_duplicate_elements(self):
        self.assertTrue(ticket.are_duplicate_plain(self.first, self.second))

    def test_returns_false_for_different_ticket(self):
        self.assertFalse(ticket.are_duplicate_plain(
            self.first,
            self.second.update({"ticket": "X"})
        ))

    def test_returns_false_for_different_resource(self):
        self.assertFalse(ticket.are_duplicate_plain(
            self.first,
            self.second.update({"rsc": "Y"})
        ))

    def test_returns_false_for_different_role(self):
        self.assertFalse(ticket.are_duplicate_plain(
            self.first,
            self.second.update({"rsc-role": "Z"})
        ))

    def test_returns_false_for_different_elements(self):
        self.second.update({
            "ticket": "X",
            "rsc": "Y",
            "rsc-role": "Z"
        })
        self.assertFalse(ticket.are_duplicate_plain(self.first, self.second))

@mock.patch("pcs.lib.cib.constraint.ticket.constraint.have_duplicate_resource_sets")
class AreDuplicateWithResourceSet(TestCase):
    def test_returns_true_for_duplicate_elements(
        self, mock_have_duplicate_resource_sets
    ):
        mock_have_duplicate_resource_sets.return_value = True
        self.assertTrue(ticket.are_duplicate_with_resource_set(
            Element({"ticket": "ticket_key"}),
            Element({"ticket": "ticket_key"}),
        ))

    def test_returns_false_for_different_elements(
        self, mock_have_duplicate_resource_sets
    ):
        mock_have_duplicate_resource_sets.return_value = True
        self.assertFalse(ticket.are_duplicate_with_resource_set(
            Element({"ticket": "ticket_key"}),
            Element({"ticket": "X"}),
        ))

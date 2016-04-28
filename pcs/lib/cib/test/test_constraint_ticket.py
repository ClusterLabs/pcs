from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial
from unittest import TestCase

from pcs.lib import error_codes
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
                {"loss-policy": "fence"},
                "ticket_key",
                "resourceA",
                "master"
            )
        )

    def test_refuse_unknown_attributes(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"unknown": "nonsense"},
                "ticket_key",
                "resourceA",
                "master"
            ),
            (
                severities.ERROR,
                error_codes.INVALID_OPTION,
                {
                    'allowed_raw': ['id', 'loss-policy', 'rsc', 'rsc-role', 'ticket'],
                    'option': 'unknown',
                }
            ),
        )

    def test_refuse_bad_role(self, _):
        assert_raise_library_error(
            lambda: self.prepare(
                {"id": "id"}, "ticket_key", "resourceA", "bad_role"
            ),
            (
                severities.ERROR, error_codes.VALUE_OUT_OF_SET, {
                    'allowed_values': 'Stopped, Started, Master, Slave',
                    'allowed_values_raw': (
                        'Stopped', 'Started', 'Master', 'Slave'
                    ),
                    'value': 'bad_role',
                    'set_type': 'rsc-role'
                }
            ),
        )

    def test_refuse_unknown_lost_policy(self, mock_check_new_id_applicable):
        assert_raise_library_error(
            lambda: self.prepare(
                { "loss-policy": "unknown", "ticket": "T", "id": "id"},
                "ticket_key",
                "resourceA",
                "master"
            ),
            (severities.ERROR, error_codes.VALUE_OUT_OF_SET, {
                'allowed_values': 'fence, stop, freeze, demote',
                'allowed_values_raw': ('fence', 'stop', 'freeze', 'demote'),
                'value': 'unknown',
                'set_type': 'loss-policy value'
            }),
        )

    @mock.patch("pcs.lib.cib.constraint.ticket._create_id")
    def test_complete_id(self, mock_create_id, _):
        mock_create_id.return_value = "generated_id"
        options = {"loss-policy": "freeze", "ticket": "T"}
        ticket_key = "ticket_key"
        resource_id = "resourceA"
        resource_role = "Master"
        expected_options = options.copy()
        expected_options.update({
            "id": "generated_id",
            "rsc": resource_id,
            "rsc-role": resource_role,
            "ticket": ticket_key,
        })
        self.assertEqual(expected_options, self.prepare(
            options,
            ticket_key,
            resource_id,
            resource_role,
        ))
        mock_create_id.assert_called_once_with(
            self.cib,
            ticket_key,
            resource_id,
            resource_role,
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
            (severities.ERROR, error_codes.VALUE_OUT_OF_SET, {
                'allowed_values': 'fence, stop, freeze, demote',
                'allowed_values_raw': ('fence', 'stop', 'freeze', 'demote'),
                'value': 'unknown',
                'set_type': 'loss-policy value'
            }),
        )

    def test_refuse_missing_ticket(self, _):
        assert_raise_library_error(
            lambda: self.prepare({"loss-policy": "stop", "id": "id"}),
            (
                severities.ERROR,
                error_codes.REQUIRED_OPTION_IS_MISSING,
                {"name": "ticket"}
            )
        )


class Element(object):
    def __init__(self, attrib):
        self.attrib = attrib

class AreDuplicitPlain(TestCase):
    def test_returns_true_for_duplicit_elements(self):
        self.assertTrue(ticket.are_duplicit_plain(
            Element({
                "ticket": "ticket_key",
                "rsc": "resurceA",
                "rsc-role": "Master"
            }),
            Element({
                "ticket": "ticket_key",
                "rsc": "resurceA",
                "rsc-role": "Master"
            }),
        ))

    def test_returns_false_for_different_elements(self):
        self.assertFalse(ticket.are_duplicit_plain(
            Element({
                "ticket": "ticket_key",
                "rsc": "resurceA",
                "rsc-role": "Master"
            }),
            Element({
                "ticket": "X",
                "rsc": "Y",
                "rsc-role": "Z"
            }),
        ))

@mock.patch("pcs.lib.cib.constraint.ticket.constraint.have_duplicit_resource_sets")
class AreDuplicitWithResourceSet(TestCase):
    def test_returns_true_for_duplicit_elements(
        self, mock_have_duplicit_resource_sets
    ):
        mock_have_duplicit_resource_sets.return_value = True
        self.assertTrue(ticket.are_duplicit_with_resource_set(
            Element({"ticket": "ticket_key"}),
            Element({"ticket": "ticket_key"}),
        ))

    def test_returns_false_for_different_elements(
        self, mock_have_duplicit_resource_sets
    ):
        mock_have_duplicit_resource_sets.return_value = True
        self.assertFalse(ticket.are_duplicit_with_resource_set(
            Element({"ticket": "ticket_key"}),
            Element({"ticket": "X"}),
        ))

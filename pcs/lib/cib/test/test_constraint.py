from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial
from unittest import TestCase

from lxml import etree

from pcs.lib import error_codes
from pcs.lib.cib.constraint import constraint
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import(
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs.test.tools.pcs_mock import mock


def fixture_element(tag, id):
    element = mock.MagicMock()
    element.tag = tag
    element.attrib = {"id": id}
    return element

@mock.patch("pcs.lib.cib.constraint.constraint.find_parent")
@mock.patch("pcs.lib.cib.constraint.constraint.resource.find_by_id")
class FindValidResourceId(TestCase):
    def setUp(self):
        self.cib = "cib"
        self.find = partial(
            constraint.find_valid_resource_id,
            self.cib,
            can_repair_to_clone=False,
            in_clone_allowed=False,
        )

    def test_raises_when_element_not_found(self, mock_find_by_id, _):
        mock_find_by_id.return_value = None
        assert_raise_library_error(
            lambda: self.find(id="resourceA"),
            (
                severities.ERROR,
                error_codes.RESOURCE_DOES_NOT_EXIST,
                {"resource_id": "resourceA"}
            ),
        )

    def test_return_same_id_when_resource_is_clone(self, mock_find_by_id, _):
        mock_find_by_id.return_value = fixture_element("clone", "resourceA")
        self.assertEqual("resourceA", self.find(id="resourceA"))


    def test_return_same_id_when_is_primitive_but_not_in_clone(
         self, mock_find_by_id, mock_find_parent
    ):
        mock_find_by_id.return_value = fixture_element("primitive", "resourceA")
        mock_find_parent.return_value = None

        self.assertEqual("resourceA", self.find(id="resourceA"))

    def test_refuse_when_resource_is_in_clone(
         self, mock_find_by_id, mock_find_parent
    ):
        mock_find_by_id.return_value = fixture_element("primitive", "resourceA")
        mock_find_parent.return_value = fixture_element("clone", "clone_id")

        assert_raise_library_error(
            lambda: self.find(id="resourceA"),
            (
                severities.ERROR,
                error_codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                {
                    "resource_id": "resourceA",
                    "parent_type": "clone",
                    "parent_id": "clone_id",
                },
                True
            ),
        )

    def test_return_clone_id_when_repair_allowed(
         self, mock_find_by_id, mock_find_parent
    ):
        mock_find_by_id.return_value = fixture_element("primitive", "resourceA")
        mock_find_parent.return_value = fixture_element("clone", "clone_id")

        self.assertEqual(
            "clone_id",
            self.find(can_repair_to_clone=True, id="resourceA")
        )

    def test_return_resource_id_when_in_clone_allowed(
         self, mock_find_by_id, mock_find_parent
    ):
        mock_find_by_id.return_value = fixture_element("primitive", "resourceA")
        mock_find_parent.return_value = fixture_element("clone", "clone_id")

        self.assertEqual(
            "resourceA",
            self.find(in_clone_allowed=True, id="resourceA")
        )

class PrepareResourceSetListTest(TestCase):
    @mock.patch("pcs.lib.cib.constraint.constraint.resource_set.prepare_set")
    def test_correctly_propagete_sets_to_prepare_set(self, mock_prepare_set):
        mock_prepare_set.side_effect = lambda _, resource_set: {
            "id1": {"ids": ["E", "F"], "options": {"id": "id1"}},
            "id2": {"ids": ["G", "H"], "options": {"id": "id2"}},
        }[resource_set["options"]["id"]]

        self.assertEqual(
            [
                {"ids": ["E", "F"], "options": {"id": "id1"}},
                {"ids": ["G", "H"], "options": {"id": "id2"}},
            ],
            constraint.prepare_resource_set_list(
                "cib", "can_repair_to_clone", "in_clone_allowed", [
                    {"ids": ["A", "B"], "options": {"id": "id1"}},
                    {"ids": ["C", "D"], "options": {"id": "id2"}},
                ]
            )
        )

    @mock.patch(
        "pcs.lib.cib.constraint.constraint.find_valid_resource_id"
    )
    def test_correctly_prepare_and_use_find_valid_resource_id(
        self, mock_find_id
    ):
        repair_map = {
            "A": "E",
            "B": "F",
            "C": "G",
            "D": "H",
        }
        mock_find_id.side_effect = lambda cib, repair, clone, id: repair_map[id]
        self.assertEqual(
            [
                {"ids": ["E", "F"], "options": {}},
                {"ids": ["G", "H"], "options": {}},
            ],
            constraint.prepare_resource_set_list(
                "cib", "can_repair_to_clone", "in_clone_allowed", [
                    {"ids": ["A", "B"], "options": {}},
                    {"ids": ["C", "D"], "options": {}},
                ]
            )
        )
        expected_calls = [
            mock.call("cib", "can_repair_to_clone", "in_clone_allowed", id)
            for id in sorted(list(repair_map.keys()))
        ]
        self.assertEqual(mock_find_id.call_count, len(expected_calls))
        mock_find_id.assert_has_calls(expected_calls)

class PrepareOptionsTest(TestCase):
    def test_refuse_unknown_option(self):
        assert_raise_library_error(
            lambda: constraint.prepare_options(
                ("a", ), {"b": "c"}, mock.MagicMock(), mock.MagicMock()
            ),
            (severities.ERROR, error_codes.INVALID_OPTION, {
                'allowed_raw': ['a', 'id'],
                'option': 'b',
                'allowed': 'a, id'
            }),
        )

    def test_complete_id(self):
        mock_create_id = mock.MagicMock()
        mock_create_id.return_value = "new-id"
        self.assertEqual({"id": "new-id"}, constraint.prepare_options(
            ("a",), {}, mock_create_id, mock.MagicMock()
        ))

    def test_has_no_side_efect_on_input_options(self):
        mock_create_id = mock.MagicMock()
        mock_create_id.return_value = "new-id"
        options = {"a": "b"}
        self.assertEqual(
            {"id": "new-id", "a": "b"},
            constraint.prepare_options(
                ("a",),
                options,
                mock_create_id, mock.MagicMock()
            )
        )
        self.assertEqual({"a": "b"}, options)


    def test_refuse_invalid_id(self):
        class SomeException(Exception):
            pass
        mock_validate_id = mock.MagicMock()
        mock_validate_id.side_effect = SomeException()
        self.assertRaises(
            SomeException,
            lambda: constraint.prepare_options(
                ("a", ), {"id": "invalid"}, mock.MagicMock(), mock_validate_id
            ),
        )
        mock_validate_id.assert_called_once_with("invalid")

class CreateIdTest(TestCase):
    @mock.patch(
        "pcs.lib.cib.constraint.constraint.resource_set.extract_id_set_list"
    )
    @mock.patch("pcs.lib.cib.constraint.constraint.find_unique_id")
    def test_create_id_from_resource_set_list(self, mock_find_id, mock_extract):
        mock_extract.return_value = [["A", "B"], ["C"]]
        mock_find_id.return_value = "some_id"
        self.assertEqual(
            "some_id",
            constraint.create_id("cib", "PREFIX", "resource_set_list")
        )
        mock_extract.assert_called_once_with("resource_set_list")
        mock_find_id.assert_called_once_with("cib", "pcs_PREFIX_set_A_B_set_C")

def fixture_constraint_section(return_value):
    constraint_section = mock.MagicMock()
    constraint_section.findall = mock.MagicMock()
    constraint_section.findall.return_value = return_value
    return constraint_section

@mock.patch("pcs.lib.cib.constraint.constraint.export_with_set")
class CheckIsWithoutDuplicationTest(TestCase):
    def test_raises_when_duplicate_element_found(self, export_with_set):
        export_with_set.return_value = "exported_duplicate_element"
        element = mock.MagicMock()
        element.tag = "constraint_type"

        assert_raise_library_error(
            lambda: constraint.check_is_without_duplication(
                fixture_constraint_section(["duplicate_element"]), element,
                are_duplicate=lambda e1, e2: True,
                export_element=constraint.export_with_set,
            ),
            (
                severities.ERROR,
                error_codes.DUPLICATE_CONSTRAINTS_EXIST,
                {
                    'constraint_info_list': ['exported_duplicate_element'],
                    'type': 'constraint_type'
                },
                True
            ),
        )
    def test_success_when_no_duplication_found(self, export_with_set):
        export_with_set.return_value = "exported_duplicate_element"
        element = mock.MagicMock()
        element.tag = "constraint_type"
        #no exception raised
        constraint.check_is_without_duplication(
            fixture_constraint_section([]), element,
            are_duplicate=lambda e1, e2: True,
            export_element=constraint.export_with_set,
        )


class CreateWithSetTest(TestCase):
    def test_put_new_constraint_to_constraint_section(self):
        constraint_section = etree.Element("constraints")
        constraint.create_with_set(
            constraint_section,
            "ticket",
            {"a": "b"},
            [{"ids": ["A", "B"], "options": {"c": "d"}}]
        )
        assert_xml_equal(etree.tostring(constraint_section).decode(), """
            <constraints>
                <ticket a="b">
                    <resource_set c="d" id="pcs_rsc_set_A_B">
                        <resource_ref id="A"/>
                        <resource_ref id="B"/>
                    </resource_set>
                </ticket>
            </constraints>
        """)

    def test_refuse_empty_resource_set_list(self):
        constraint_section = etree.Element("constraints")
        assert_raise_library_error(
            lambda: constraint.create_with_set(
                constraint_section,
                "ticket",
                {"a": "b"},
                []
            ),
            (severities.ERROR, error_codes.EMPTY_RESOURCE_SET_LIST, {})
        )

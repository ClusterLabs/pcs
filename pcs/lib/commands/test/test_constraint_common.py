from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from lxml import etree

from pcs.common import report_codes
from pcs.lib.commands.constraint import common as constraint
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import(
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock


def fixture_cib_and_constraints():
    cib = etree.Element("cib")
    resources_section = etree.SubElement(cib, "resources")
    for id in ("A", "B", "E", "F"):
        etree.SubElement(resources_section, "primitive").attrib["id"] = id
    constraint_section = etree.SubElement(
        etree.SubElement(cib, "configuration"),
        "constraints"
    )
    return cib, constraint_section

def fixture_env(cib):
    env = mock.MagicMock()
    env.get_cib = mock.Mock()
    env.get_cib.return_value = cib
    env.push_cib = mock.Mock()
    env.report_processor = MockLibraryReportProcessor()
    return env

class CreateWithSetTest(TestCase):
    def setUp(self):
        self.cib, self.constraint_section = fixture_cib_and_constraints()
        self.env = fixture_env(self.cib)
        self.independent_cib = etree.XML(etree.tostring(self.cib))

    def create(self, duplication_alowed=False):
        constraint.create_with_set(
            "rsc_some",
            lambda cib, options, resource_set_list: options,
            self.env,
            [
                {"ids": ["A", "B"], "options": {"role": "Master"}},
                {"ids": ["E", "F"], "options": {"action": "start"}},
            ],
            {"id":"some_id", "symmetrical": "true"},
            duplication_alowed=duplication_alowed
        )

    def test_put_new_constraint_to_constraint_section(self):
        self.create()
        self.env.push_cib.assert_called_once_with(self.cib)
        self.independent_cib.find(".//constraints").append(etree.XML("""
            <rsc_some id="some_id" symmetrical="true">
                  <resource_set id="pcs_rsc_set_A_B" role="Master">
                      <resource_ref id="A"></resource_ref>
                      <resource_ref id="B"></resource_ref>
                  </resource_set>
                  <resource_set action="start" id="pcs_rsc_set_E_F">
                      <resource_ref id="E"></resource_ref>
                      <resource_ref id="F"></resource_ref>
                  </resource_set>
            </rsc_some>
        """))
        assert_xml_equal(
            etree.tostring(self.independent_cib).decode(),
            etree.tostring(self.cib).decode()
        )

    def test_refuse_duplicate(self):
        self.create()
        self.env.push_cib.assert_called_once_with(self.cib)
        assert_raise_library_error(self.create, (
            severities.ERROR,
            report_codes.DUPLICATE_CONSTRAINTS_EXIST,
            {
                'constraint_type': 'rsc_some',
                'constraint_info_list': [{
                    'options': {'symmetrical': 'true', 'id': 'some_id'},
                    'resource_sets': [
                        {
                            'ids': ['A', 'B'],
                            'options':{'role':'Master', 'id':'pcs_rsc_set_A_B'}
                        },
                        {
                            'ids': ['E', 'F'],
                            'options':{'action':'start', 'id':'pcs_rsc_set_E_F'}
                        }
                    ],
                }]
            },
            report_codes.FORCE_CONSTRAINT_DUPLICATE
        ))

    def test_put_duplicate_constraint_when_duplication_allowed(self):
        self.create()
        self.create(duplication_alowed=True)
        expected_calls = [
            mock.call(self.cib),
            mock.call(self.cib),
        ]
        self.assertEqual(self.env.push_cib.call_count, len(expected_calls))
        self.env.push_cib.assert_has_calls(expected_calls)

        constraint_section = self.independent_cib.find(".//constraints")
        constraint_section.append(etree.XML("""
            <rsc_some id="some_id" symmetrical="true">
                <resource_set id="pcs_rsc_set_A_B" role="Master">
                    <resource_ref id="A"></resource_ref>
                    <resource_ref id="B"></resource_ref>
                </resource_set>
                <resource_set action="start" id="pcs_rsc_set_E_F">
                    <resource_ref id="E"></resource_ref>
                    <resource_ref id="F"></resource_ref>
                </resource_set>
            </rsc_some>
        """))
        constraint_section.append(etree.XML("""
            <rsc_some id="some_id" symmetrical="true">
                <resource_set id="pcs_rsc_set_A_B-1" role="Master">
                    <resource_ref id="A"></resource_ref>
                    <resource_ref id="B"></resource_ref>
                </resource_set>
                <resource_set action="start" id="pcs_rsc_set_E_F-1">
                    <resource_ref id="E"></resource_ref>
                    <resource_ref id="F"></resource_ref>
                </resource_set>
            </rsc_some>
        """))
        assert_xml_equal(
            etree.tostring(self.independent_cib).decode(),
            etree.tostring(self.cib).decode()
        )

class ShowTest(TestCase):
    def setUp(self):
        self.cib, self.constraint_section = fixture_cib_and_constraints()
        self.env = fixture_env(self.cib)

    def create(self, tag_name, resource_set_list):
        constraint.create_with_set(
            tag_name,
            lambda cib, options, resource_set_list: options,
            self.env,
            resource_set_list,
            {"id":"some_id", "symmetrical": "true"},
        )

    def test_returns_export_of_found_elements(self):
        tag_name = "rsc_some"
        self.create(tag_name, [
            {"ids": ["A", "B"], "options": {"role": "Master"}},
        ])
        self.create(tag_name, [
            {"ids": ["E", "F"], "options": {"action": "start"}},
        ])
        etree.SubElement(self.constraint_section, tag_name).attrib.update({
            "id": "plain1", "is_plain": "true"
        })

        is_plain = lambda element: element.attrib.has_key("is_plain")

        self.assertEqual(
            constraint.show(tag_name, is_plain, self.env), {
            'plain': [{"options": {'id': 'plain1', 'is_plain': 'true'}}],
            'with_resource_sets': [
                {
                    'resource_sets': [{
                        'ids': ['A', 'B'],
                        'options': {'role': 'Master', 'id': 'pcs_rsc_set_A_B'},
                    }],
                    'options': {'symmetrical': 'true', 'id': 'some_id'}
                },
                {
                    'options': {'symmetrical': 'true', 'id': 'some_id'},
                    'resource_sets': [{
                        'ids': ['E', 'F'],
                        'options': {'action': 'start', 'id': 'pcs_rsc_set_E_F'}
                    }]
                }
            ]
        })

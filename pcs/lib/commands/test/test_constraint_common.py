from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from lxml import etree

from pcs.lib import error_codes
from pcs.lib.commands.constraint import common as constraint
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import(
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs.test.tools.pcs_mock import mock


def fixture_cib_and_constraints():
    cib = etree.Element("cib")
    resources_section = etree.SubElement(cib, "resources")
    for id in ("A", "B", "E", "F"):
        etree.SubElement(resources_section, "primitive").attrib["id"] = id
    constraint_section = etree.SubElement(cib, "constraints")
    return cib, constraint_section

def fixture_env(cib):
    env = mock.MagicMock()
    env.get_cib = mock.Mock()
    env.get_cib.return_value = cib
    env.push_cib = mock.Mock()
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
                {"ids": ["A", "B"], "attrib": {"role": "Master"}},
                {"ids": ["E", "F"], "attrib": {"action": "start"}},
            ],
            {"id":"some_id", "symmetrical": "true"},
            duplication_alowed=duplication_alowed
        )

    def test_put_new_constraint_to_constraint_section(self):
        self.create()
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
        assert_raise_library_error(self.create, (
            severities.ERROR, error_codes.DUPLICIT_CONSTRAINTS_EXIST, {
                'type': 'rsc_some',
                'constraint_info_list': [{
                    'attrib': {'symmetrical': 'true', 'id': 'some_id'},
                    'resource_sets': [
                        {
                            'ids': ['A', 'B'],
                            'attrib': {'role':'Master', 'id':'pcs_rsc_set_A_B'}
                        },
                        {
                            'ids': ['E', 'F'],
                            'attrib': {'action':'start', 'id':'pcs_rsc_set_E_F'}
                        }
                    ],
                }]
            }
        ))

    def test_put_duplicit_constraint_when_duplication_allowed(self):
        self.create()
        self.create(duplication_alowed=True)

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
            {"ids": ["A", "B"], "attrib": {"role": "Master"}},
        ])
        self.create(tag_name, [
            {"ids": ["E", "F"], "attrib": {"action": "start"}},
        ])
        etree.SubElement(self.constraint_section, tag_name).attrib.update({
            "id": "plain1", "is_plain": "true"
        })

        is_plain = lambda element: element.attrib.has_key("is_plain")

        self.assertEqual(
            constraint.show(tag_name, is_plain, self.env), {
            'plain': [{"attrib": {'id': 'plain1', 'is_plain': 'true'}}],
            'with_resource_sets': [
                {
                    'resource_sets': [{
                        'ids': ['A', 'B'],
                        'attrib': {'role': 'Master', 'id': 'pcs_rsc_set_A_B'},
                    }],
                    'attrib': {'symmetrical': 'true', 'id': 'some_id'}
                },
                {
                     'attrib': {'symmetrical': 'true', 'id': 'some_id'},
                    'resource_sets': [{
                        'ids': ['E', 'F'],
                        'attrib': {'action': 'start', 'id': 'pcs_rsc_set_E_F'}
                    }]
                }
            ]
        })

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil

from lxml import etree

from pcs.test.tools.assertions import AssertPcsMixin, assert_xml_equal
from pcs.test.tools.misc import  get_test_resource as rc
from pcs.test.tools.pcs_runner import PcsRunner
from pcs.test.tools.pcs_unittest import TestCase


def xml_format(xml_string):
    line_list = xml_string.splitlines()
    reindented_lines = [line_list[0]]
    for line in line_list[1:]:
        leading_spaces = len(line) - len(line.lstrip()) - 4
        #current indent is 2 spaces desired is 4 spaces
        indent = " " * 2 * leading_spaces
        new_line = indent + line.strip()
        max_line_len = 80 - 12 #12 is indent in this file ;)
        if new_line.endswith(">") and len(new_line) > max_line_len:
            last_space = new_line[:max_line_len].rfind(" ")
            if last_space:
                closing = "/>" if new_line.endswith("/>") else ">"
                splited_line = [
                    new_line[:last_space],
                    indent + "   " + new_line[last_space : -1 * len(closing)],
                    indent + closing
                ]
                reindented_lines.extend(splited_line)
                continue
        #append not splited line
        reindented_lines.append(new_line)

    return "\n".join(reindented_lines)

class AssertPcsEffectMixin(AssertPcsMixin):
    def assert_resources_xml_in_cib(self, expected_xml_resources):
        xml = etree.tostring(
            etree.parse(self.temp_cib).findall(".//resources")[0]
        )
        try:
            assert_xml_equal(xml.decode(), expected_xml_resources)
        except AssertionError as e:
            raise AssertionError(
                "{0}\n\nCopy format ;)\n{1}".format(e.message, xml_format(xml))
            )

    def assert_effect_single(self, command, expected_xml, output=""):
        self.assert_pcs_success(command, output)
        self.assert_resources_xml_in_cib(expected_xml)

    def assert_effect(self, alternative_cmds, expected_xml, output=""):
        alternative_list = (
            alternative_cmds if isinstance(alternative_cmds, list)
            else [alternative_cmds]
        )
        cib_content = open(self.temp_cib).read()
        for alternative in alternative_list[:-1]:
            self.assert_effect_single(alternative, expected_xml, output)
            open(self.temp_cib, "w").write(cib_content)

        self.assert_effect_single(alternative_list[-1], expected_xml, output)

class ResourceTest(TestCase, AssertPcsEffectMixin):
    temp_cib = rc("temp-cib.xml")
    def setUp(self):
        shutil.copy(rc('cib-empty-1.2.xml'), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)

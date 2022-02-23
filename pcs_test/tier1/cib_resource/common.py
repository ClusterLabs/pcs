from unittest import TestCase

from lxml import etree

from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


def get_cib_resources(cib):
    return etree.tostring(etree.parse(cib).findall(".//resources")[0])


class ResourceTest(TestCase, get_assert_pcs_effect_mixin(get_cib_resources)):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_resource_common")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

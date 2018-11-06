import shutil
from unittest import TestCase
from lxml import etree

from pcs.test.tools.cib import get_assert_pcs_effect_mixin
from pcs.test.tools.misc import  get_test_resource as rc
from pcs.test.tools.pcs_runner import PcsRunner

def get_cib_resources(cib):
    return etree.tostring(etree.parse(cib).findall(".//resources")[0])

class ResourceTest(
    TestCase,
    get_assert_pcs_effect_mixin(get_cib_resources)
):
    empty_cib = rc("cib-empty.xml")
    temp_cib = rc("temp-cib.xml")

    def setUp(self):
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)

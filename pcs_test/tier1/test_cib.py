from textwrap import dedent
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner
from pcs_test.tools.xml import str_to_etree


class ElementDescription(AssertPcsMixin, TestCase):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_element_description")
        write_file_to_tmpfile(get_test_resource("cib-all.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def assert_description_in_cib(self, xpath, expected_description=None):
        self.temp_cib.seek(0)
        xpath_result = str_to_etree(self.temp_cib.read()).xpath(xpath)
        cib_description = xpath_result[0] if xpath_result else None
        self.assertEqual(cib_description, expected_description)

    def test_usage(self):
        self.assert_pcs_fail(
            ["cib", "element", "description"],
            stderr_start=dedent("""
                Usage: pcs cib <command>
                    element description <element-id>
            """),
        )

    def test_add_description(self):
        # primitive resource without description
        xpath = "//primitive[@id='R6']/@description"
        self.assert_description_in_cib(xpath, None)

        description = "My description"
        self.assert_pcs_success(
            ["cib", "element", "description", "R6", description],
            stdout_full="",
            stderr_full="",
        )

        self.assert_description_in_cib(xpath, description)

    def test_remove_description(self):
        # alert with description
        xpath = "//alert[@id='alert-all']/@description"
        self.assert_description_in_cib(xpath, "alert all options")

        self.assert_pcs_success(
            ["cib", "element", "description", "alert-all", ""],
            stdout_full="",
            stderr_full="",
        )

        self.assert_description_in_cib(xpath, None)

    def test_show_description(self):
        self.assert_pcs_success(
            ["cib", "element", "description", "alert-all"],
            stdout_full="alert all options\n",
            stderr_full="",
        )

    def test_show_description_no_description(self):
        self.assert_pcs_success(
            ["cib", "element", "description", "R6"],
            stdout_full="",
            stderr_full="",
        )

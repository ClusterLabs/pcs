from textwrap import dedent
from unittest import TestCase

from lxml import etree

from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
    skip_unless_pacemaker_supports_rsc_and_op_rules,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


empty_cib = rc("cib-empty-2.0.xml")
empty_cib_rules = rc("cib-empty-3.4.xml")


class TestDefaultsMixin:
    def setUp(self):
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier1_cib_options")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        # pylint: disable=invalid-name
        self.temp_cib.close()


class DefaultsSetAddMixin(TestDefaultsMixin):
    cli_command = ""
    cib_tag = ""

    def test_no_args(self):
        self.assert_effect(
            f"{self.cli_command} set-add",
            dedent(
                f"""\
                <{self.cib_tag}>
                    <meta_attributes id="{self.cib_tag}-meta_attributes"/>
                </{self.cib_tag}>
            """
            ),
            output=(
                "Warning: Defaults do not apply to resources which override "
                "them with their own defined values\n"
            ),
        )

    def test_success(self):
        self.assert_effect(
            (
                f"{self.cli_command} set-add id=mine score=10 "
                "values nam1=val1 nam2=val2 --force"
            ),
            dedent(
                f"""\
                <{self.cib_tag}>
                    <meta_attributes id="mine" score="10">
                        <nvpair id="mine-nam1" name="nam1" value="val1"/>
                        <nvpair id="mine-nam2" name="nam2" value="val2"/>
                    </meta_attributes>
                </{self.cib_tag}>
            """
            ),
            output=(
                "Warning: Defaults do not apply to resources which override "
                "them with their own defined values\n"
            ),
        )

    @skip_unless_pacemaker_supports_rsc_and_op_rules()
    def test_success_rules(self):
        # TODO new pacemaker is needed
        self.assertEqual("TODO", True)


class RscDefaultsSetAdd(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//rsc_defaults")[0]
        )
    ),
    DefaultsSetAddMixin,
    TestCase,
):
    cli_command = "resource defaults"
    cib_tag = "rsc_defaults"


class OpDefaultsSetAdd(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//op_defaults")[0]
        )
    ),
    DefaultsSetAddMixin,
    TestCase,
):
    cli_command = "resource op defaults"
    cib_tag = "op_defaults"

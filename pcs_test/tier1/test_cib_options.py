from textwrap import dedent
from unittest import TestCase

from lxml import etree

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
    skip_unless_pacemaker_supports_rsc_and_op_rules,
    write_data_to_tmpfile,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner
from pcs_test.tools.xml import XmlManipulation


empty_cib = rc("cib-empty-2.0.xml")
empty_cib_rules = rc("cib-empty-3.4.xml")


class TestDefaultsMixin:
    def setUp(self):
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier1_cib_options")
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        # pylint: disable=invalid-name
        self.temp_cib.close()


class DefaultsConfigMixin(TestDefaultsMixin, AssertPcsMixin):
    cli_command = ""
    prefix = ""

    def setUp(self):
        super().setUp()
        xml_rsc = """
            <rsc_defaults>
                <meta_attributes id="rsc-set1" score="10">
                    <nvpair id="rsc-set1-nv1" name="name1" value="rsc1"/>
                    <nvpair id="rsc-set1-nv2" name="name2" value="rsc2"/>
                </meta_attributes>
                <meta_attributes id="rsc-setA">
                    <nvpair id="rsc-setA-nv1" name="name1" value="rscA"/>
                    <nvpair id="rsc-setA-nv2" name="name2" value="rscB"/>
                </meta_attributes>
            </rsc_defaults>
        """
        xml_op = """
            <op_defaults>
                <meta_attributes id="op-set1" score="10">
                    <nvpair id="op-set1-nv1" name="name1" value="op1"/>
                    <nvpair id="op-set1-nv2" name="name2" value="op2"/>
                </meta_attributes>
                <meta_attributes id="op-setA">
                    <nvpair id="op-setA-nv1" name="name1" value="opA"/>
                    <nvpair id="op-setA-nv2" name="name2" value="opB"/>
                </meta_attributes>
            </op_defaults>
        """
        xml_manip = XmlManipulation.from_file(empty_cib)
        xml_manip.append_to_first_tag_name("configuration", xml_rsc, xml_op)
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    def test_success(self):
        self.assert_pcs_success(
            self.cli_command,
            stdout_full=dedent(
                f"""\
                Meta Attrs: {self.prefix}-set1 score=10
                  name1={self.prefix}1
                  name2={self.prefix}2
                Meta Attrs: {self.prefix}-setA
                  name1={self.prefix}A
                  name2={self.prefix}B
            """
            ),
        )


class RscDefaultsConfig(
    DefaultsConfigMixin, TestCase,
):
    cli_command = "resource defaults"
    prefix = "rsc"


class OpDefaultsConfig(
    DefaultsConfigMixin, TestCase,
):
    cli_command = "resource op defaults"
    prefix = "op"


class DefaultsSetCreateMixin(TestDefaultsMixin):
    cli_command = ""
    cib_tag = ""

    def setUp(self):
        super().setUp()
        write_file_to_tmpfile(empty_cib, self.temp_cib)

    def test_no_args(self):
        self.assert_effect(
            f"{self.cli_command} set create",
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
                f"{self.cli_command} set create id=mine score=10 "
                "meta nam1=val1 nam2=val2 --force"
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


class RscDefaultsSetCreate(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//rsc_defaults")[0]
        )
    ),
    DefaultsSetCreateMixin,
    TestCase,
):
    cli_command = "resource defaults"
    cib_tag = "rsc_defaults"


class OpDefaultsSetCreate(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//op_defaults")[0]
        )
    ),
    DefaultsSetCreateMixin,
    TestCase,
):
    cli_command = "resource op defaults"
    cib_tag = "op_defaults"


class DefaultsSetDeleteMixin(TestDefaultsMixin, AssertPcsMixin):
    cli_command = ""
    prefix = ""
    cib_tag = ""

    def setUp(self):
        super().setUp()
        xml_rsc = """
            <rsc_defaults>
                <meta_attributes id="rsc-set1" />
                <meta_attributes id="rsc-set2" />
                <meta_attributes id="rsc-set3" />
                <meta_attributes id="rsc-set4" />
            </rsc_defaults>
        """
        xml_op = """
            <op_defaults>
                <meta_attributes id="op-set1" />
                <meta_attributes id="op-set2" />
                <meta_attributes id="op-set3" />
                <meta_attributes id="op-set4" />
            </op_defaults>
        """
        xml_manip = XmlManipulation.from_file(empty_cib)
        xml_manip.append_to_first_tag_name("configuration", xml_rsc, xml_op)
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    def test_success(self):
        self.assert_effect(
            [
                f"{self.cli_command} set delete {self.prefix}-set1 "
                f"{self.prefix}-set3",
                f"{self.cli_command} set remove {self.prefix}-set1 "
                f"{self.prefix}-set3",
            ],
            dedent(
                f"""\
                <{self.cib_tag}>
                    <meta_attributes id="{self.prefix}-set2" />
                    <meta_attributes id="{self.prefix}-set4" />
                </{self.cib_tag}>
            """
            ),
        )


class RscDefaultsSetDelete(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//rsc_defaults")[0]
        )
    ),
    DefaultsSetDeleteMixin,
    TestCase,
):
    cli_command = "resource defaults"
    prefix = "rsc"
    cib_tag = "rsc_defaults"


class OpDefaultsSetDelete(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//op_defaults")[0]
        )
    ),
    DefaultsSetDeleteMixin,
    TestCase,
):
    cli_command = "resource op defaults"
    prefix = "op"
    cib_tag = "op_defaults"


class DefaultsSetUpdateMixin(TestDefaultsMixin, AssertPcsMixin):
    cli_command = ""
    prefix = ""
    cib_tag = ""

    def test_success_legacy(self):
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        warnings = (
            "Warning: This command is deprecated and will be removed. "
            f"Please use 'pcs {self.cli_command} set update' instead.\n"
            "Warning: Defaults do not apply to resources which override "
            "them with their own defined values\n"
        )

        self.assert_effect(
            f"{self.cli_command} name1=value1 name2=value2 name3=value3",
            dedent(
                f"""\
                <{self.cib_tag}>
                    <meta_attributes id="{self.cib_tag}-meta_attributes">
                        <nvpair id="{self.cib_tag}-meta_attributes-name1"
                            name="name1" value="value1"
                        />
                        <nvpair id="{self.cib_tag}-meta_attributes-name2"
                            name="name2" value="value2"
                        />
                        <nvpair id="{self.cib_tag}-meta_attributes-name3"
                            name="name3" value="value3"
                        />
                    </meta_attributes>
                </{self.cib_tag}>
            """
            ),
            output=warnings,
        )

        self.assert_effect(
            f"{self.cli_command} name2=value2A name3=",
            dedent(
                f"""\
                <{self.cib_tag}>
                    <meta_attributes id="{self.cib_tag}-meta_attributes">
                        <nvpair id="{self.cib_tag}-meta_attributes-name1"
                            name="name1" value="value1"
                        />
                        <nvpair id="{self.cib_tag}-meta_attributes-name2"
                            name="name2" value="value2A"
                        />
                    </meta_attributes>
                </{self.cib_tag}>
            """
            ),
            output=warnings,
        )

        self.assert_effect(
            f"{self.cli_command} name1= name2=",
            dedent(
                f"""\
                <{self.cib_tag}>
                    <meta_attributes id="{self.cib_tag}-meta_attributes" />
                </{self.cib_tag}>
            """
            ),
            output=warnings,
        )

    def test_success(self):
        xml = f"""
            <{self.cib_tag}>
                <meta_attributes id="my-set">
                    <nvpair id="my-set-name1" name="name1" value="value1" />
                    <nvpair id="my-set-name2" name="name2" value="value2" />
                    <nvpair id="my-set-name3" name="name3" value="value3" />
                </meta_attributes>
            </{self.cib_tag}>
        """
        xml_manip = XmlManipulation.from_file(empty_cib)
        xml_manip.append_to_first_tag_name("configuration", xml)
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)
        warnings = (
            "Warning: Defaults do not apply to resources which override "
            "them with their own defined values\n"
        )

        self.assert_effect(
            f"{self.cli_command} set update my-set meta name2=value2A name3=",
            dedent(
                f"""\
                <{self.cib_tag}>
                    <meta_attributes id="my-set">
                        <nvpair id="my-set-name1" name="name1" value="value1" />
                        <nvpair id="my-set-name2" name="name2" value="value2A" />
                    </meta_attributes>
                </{self.cib_tag}>
            """
            ),
            output=warnings,
        )

        self.assert_effect(
            f"{self.cli_command} set update my-set meta name1= name2=",
            dedent(
                f"""\
                <{self.cib_tag}>
                    <meta_attributes id="my-set" />
                </{self.cib_tag}>
            """
            ),
            output=warnings,
        )


class RscDefaultsSetUpdate(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//rsc_defaults")[0]
        )
    ),
    DefaultsSetUpdateMixin,
    TestCase,
):
    cli_command = "resource defaults"
    prefix = "rsc"
    cib_tag = "rsc_defaults"


class OpDefaultsSetUpdate(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//op_defaults")[0]
        )
    ),
    DefaultsSetUpdateMixin,
    TestCase,
):
    cli_command = "resource op defaults"
    prefix = "op"
    cib_tag = "op_defaults"


class DefaultsSetUsageMixin(TestDefaultsMixin, AssertPcsMixin):
    cli_command = ""

    def test_no_args(self):
        self.assert_pcs_fail(
            f"{self.cli_command} set",
            stdout_start=f"\nUsage: pcs {self.cli_command} set...\n",
        )

    def test_bad_command(self):
        self.assert_pcs_fail(
            f"{self.cli_command} set bad-command",
            stdout_start=f"\nUsage: pcs {self.cli_command} set ...\n",
        )


class RscDefaultsSetUsage(
    DefaultsSetUsageMixin, TestCase,
):
    cli_command = "resource defaults"


class OpDefaultsSetUsage(
    DefaultsSetUsageMixin, TestCase,
):
    cli_command = "resource op defaults"

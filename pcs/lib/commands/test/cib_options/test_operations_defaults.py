from unittest import TestCase

from pcs.lib.commands import cib_options
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools import fixture
from pcs.common import report_codes

FIXTURE_INITIAL_DEFAULTS = """
    <op_defaults>
        <meta_attributes id="op_defaults-options">
            <nvpair id="op_defaults-options-a" name="a" value="b"/>
            <nvpair id="op_defaults-options-b" name="b" value="c"/>
        </meta_attributes>
    </op_defaults>
"""

class SetOperationsDefaults(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(optional_in_conf=FIXTURE_INITIAL_DEFAULTS)

    def tearDown(self):
        self.env_assist.assert_reports([
            fixture.warn(report_codes.DEFAULTS_CAN_BE_OVERRIDEN)
        ])

    def assert_options_produces_op_defaults_xml(self, options, op_defaults_xml):
        self.config.env.push_cib(
            replace={
                "./configuration/op_defaults/meta_attributes": op_defaults_xml
            }
        )
        cib_options.set_operations_defaults(self.env_assist.get_env(), options)

    def test_change(self):
        self.assert_options_produces_op_defaults_xml(
            {
                "a": "B",
                "b": "C",
            },
            """
                <meta_attributes id="op_defaults-options">
                    <nvpair id="op_defaults-options-a" name="a" value="B"/>
                    <nvpair id="op_defaults-options-b" name="b" value="C"/>
                </meta_attributes>
            """
        )

    def test_add(self):
        self.assert_options_produces_op_defaults_xml(
            {"c": "d"},
            """
                <meta_attributes id="op_defaults-options">
                    <nvpair id="op_defaults-options-a" name="a" value="b"/>
                    <nvpair id="op_defaults-options-b" name="b" value="c"/>
                    <nvpair id="op_defaults-options-c" name="c" value="d"/>
                </meta_attributes>
            """
        )

    def test_remove(self):
        self.config.env.push_cib(
            remove=
                "./configuration/op_defaults/meta_attributes/nvpair[@name='a']"
        )
        cib_options.set_operations_defaults(
            self.env_assist.get_env(),
            {"a": ""},
        )

    def test_add_when_section_does_not_exists(self):
        (self.config
            .remove("runner.cib.load")
            .runner.cib.load()
            .env.push_cib(
                optional_in_conf="""
                    <op_defaults>
                        <meta_attributes id="op_defaults-options">
                            <nvpair id="op_defaults-options-a" name="a"
                                value="b"
                            />
                        </meta_attributes>
                    </op_defaults>
                """
            )
        )
        cib_options.set_operations_defaults(
            self.env_assist.get_env(),
            {"a": "b"},
        )

    def test_keep_section_when_empty(self):
        self.config.env.push_cib(remove="./configuration/op_defaults//nvpair")
        cib_options.set_operations_defaults(
            self.env_assist.get_env(),
            {
                "a": "",
                "b": "",
            }
        )

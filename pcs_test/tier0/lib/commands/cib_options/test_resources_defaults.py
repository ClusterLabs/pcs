from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common import report_codes
from pcs.lib.commands import cib_options

FIXTURE_INITIAL_DEFAULTS = """
    <rsc_defaults>
        <meta_attributes id="rsc_defaults-options">
            <nvpair id="rsc_defaults-options-a" name="a" value="b"/>
            <nvpair id="rsc_defaults-options-b" name="b" value="c"/>
        </meta_attributes>
    </rsc_defaults>
"""

class SetResourcesDefaults(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def tearDown(self):
        self.env_assist.assert_reports([
            fixture.warn(report_codes.DEFAULTS_CAN_BE_OVERRIDEN)
        ])

    def test_change(self):
        self.config.runner.cib.load(optional_in_conf=FIXTURE_INITIAL_DEFAULTS)
        self.config.env.push_cib(optional_in_conf="""
            <rsc_defaults>
                <meta_attributes id="rsc_defaults-options">
                    <nvpair id="rsc_defaults-options-a" name="a" value="B"/>
                    <nvpair id="rsc_defaults-options-b" name="b" value="C"/>
                </meta_attributes>
            </rsc_defaults>
        """)
        cib_options.set_resources_defaults(
            self.env_assist.get_env(),
            {
                "a": "B",
                "b": "C",
            }
        )

    def test_add(self):
        self.config.runner.cib.load(optional_in_conf=FIXTURE_INITIAL_DEFAULTS)
        self.config.env.push_cib(optional_in_conf="""
            <rsc_defaults>
                <meta_attributes id="rsc_defaults-options">
                    <nvpair id="rsc_defaults-options-a" name="a" value="b"/>
                    <nvpair id="rsc_defaults-options-b" name="b" value="c"/>
                    <nvpair id="rsc_defaults-options-c" name="c" value="d"/>
                </meta_attributes>
            </rsc_defaults>
        """)
        cib_options.set_resources_defaults(
            self.env_assist.get_env(),
            {"c": "d"},
        )

    def test_remove(self):
        self.config.runner.cib.load(optional_in_conf=FIXTURE_INITIAL_DEFAULTS)
        self.config.env.push_cib(
            remove=
                "./configuration/rsc_defaults/meta_attributes/nvpair[@name='a']"
        )
        cib_options.set_resources_defaults(
            self.env_assist.get_env(),
            {"a": ""},
        )

    def test_add_section_if_missing(self):
        self.config.runner.cib.load()
        self.config.env.push_cib(optional_in_conf="""
            <rsc_defaults>
                <meta_attributes id="rsc_defaults-options">
                    <nvpair id="rsc_defaults-options-a" name="a" value="A"/>
                </meta_attributes>
            </rsc_defaults>
        """)
        cib_options.set_resources_defaults(
            self.env_assist.get_env(),
            {"a": "A",}
        )

    def test_add_meta_if_missing(self):
        self.config.runner.cib.load(optional_in_conf="<rsc_defaults />")
        self.config.env.push_cib(optional_in_conf="""
            <rsc_defaults>
                <meta_attributes id="rsc_defaults-options">
                    <nvpair id="rsc_defaults-options-a" name="a" value="A"/>
                </meta_attributes>
            </rsc_defaults>
        """)
        cib_options.set_resources_defaults(
            self.env_assist.get_env(),
            {"a": "A",}
        )

    def test_dont_add_section_if_only_removing(self):
        self.config.runner.cib.load()
        cib_options.set_resources_defaults(
            self.env_assist.get_env(),
            {
                "a": "",
                "b": "",
            }
        )

    def test_dont_add_meta_if_only_removing(self):
        self.config.runner.cib.load(optional_in_conf="<rsc_defaults />")
        self.config.env.push_cib(optional_in_conf="<rsc_defaults />")
        cib_options.set_resources_defaults(
            self.env_assist.get_env(),
            {
                "a": "",
                "b": "",
            }
        )

    def test_keep_section_when_empty(self):
        self.config.runner.cib.load(optional_in_conf=FIXTURE_INITIAL_DEFAULTS)
        self.config.env.push_cib(remove="./configuration/rsc_defaults//nvpair")
        cib_options.set_resources_defaults(
            self.env_assist.get_env(),
            {
                "a": "",
                "b": "",
            }
        )

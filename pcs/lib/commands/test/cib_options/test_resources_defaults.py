from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.lib.commands import cib_options
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.pcs_unittest import TestCase
from pcs.test.tools import fixture
from pcs.common import report_codes

FIXTURE_INITIAL_DEFAULTS = """
    <rsc_defaults>
        <meta_attributes id="rsc_defaults-options">
            <nvpair id="rsc_defaults-options-a" name="a" value="b"/>
            <nvpair id="rsc_defaults-options-b" name="b" value="c"/>
        </meta_attributes>
    </rsc_defaults>
"""

class SetResourcesDefaults(TestCase):
    def assert_options_produces_rsc_defaults_xml(
        self, options, rsc_defaults_xml
    ):
        env_assist, config = get_env_tools(test_case=self)
        (config
            .runner.cib.load(optional_in_conf=FIXTURE_INITIAL_DEFAULTS)
            .env.push_cib(optional_in_conf=rsc_defaults_xml)
        )
        cib_options.set_resources_defaults(env_assist.get_env(), options)
        env_assist.assert_reports([
            fixture.warn(report_codes.DEFAULTS_CAN_BE_OVERRIDEN)
        ])

    def test_change(self):
        self.assert_options_produces_rsc_defaults_xml(
            {
                "a": "B",
                "b": "C",
            },
            """
                <rsc_defaults>
                    <meta_attributes id="rsc_defaults-options">
                        <nvpair id="rsc_defaults-options-a" name="a" value="B"/>
                        <nvpair id="rsc_defaults-options-b" name="b" value="C"/>
                    </meta_attributes>
                </rsc_defaults>
            """
        )

    def test_add(self):
        self.assert_options_produces_rsc_defaults_xml(
            {"c": "d"},
            """
                <rsc_defaults>
                    <meta_attributes id="rsc_defaults-options">
                        <nvpair id="rsc_defaults-options-a" name="a" value="b"/>
                        <nvpair id="rsc_defaults-options-b" name="b" value="c"/>
                        <nvpair id="rsc_defaults-options-c" name="c" value="d"/>
                    </meta_attributes>
                </rsc_defaults>
            """
        )

    def test_remove(self):
        self.assert_options_produces_rsc_defaults_xml(
            {"a": ""},
            """
                <rsc_defaults>
                    <meta_attributes id="rsc_defaults-options">
                        <nvpair id="rsc_defaults-options-b" name="b" value="c"/>
                    </meta_attributes>
                </rsc_defaults>
            """
        )

    def test_add_when_section_does_not_exists(self):
        env_assist, config = get_env_tools(test_case=self)
        (config
            .runner.cib.load()
            .env.push_cib(
                optional_in_conf="""
                    <rsc_defaults>
                        <meta_attributes id="rsc_defaults-options">
                            <nvpair id="rsc_defaults-options-a" name="a"
                                value="b"
                            />
                        </meta_attributes>
                    </rsc_defaults>
                """
            )
        )
        cib_options.set_resources_defaults(env_assist.get_env(), {"a": "b"})
        env_assist.assert_reports([
            fixture.warn(report_codes.DEFAULTS_CAN_BE_OVERRIDEN)
        ])

    def test_remove_section_when_empty(self):
        env_assist, config = get_env_tools(test_case=self)
        (config
            .runner.cib.load(optional_in_conf=FIXTURE_INITIAL_DEFAULTS)
            .env.push_cib(remove=".//rsc_defaults")
        )
        cib_options.set_resources_defaults(
            env_assist.get_env(),
            {
                "a": "",
                "b": "",
            }
        )
        env_assist.assert_reports([
            fixture.warn(report_codes.DEFAULTS_CAN_BE_OVERRIDEN)
        ])

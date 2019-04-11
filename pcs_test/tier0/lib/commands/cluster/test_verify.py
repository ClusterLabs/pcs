from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common import report_codes
from pcs.lib.commands.cluster import verify


CRM_VERIFY_ERROR_REPORT = "someting wrong\nsomething else wrong"

BAD_FENCING_TOPOLOGY = """
    <fencing-topology>
        <fencing-level devices="FX" index="2" target="node1" id="fl-node1-2"/>
    </fencing-topology>
"""

BAD_FENCING_TOPOLOGY_REPORTS = [
    fixture.error(
        report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
        stonith_ids=["FX"],
    ),
    fixture.error(
        report_codes.NODE_NOT_FOUND,
        node="node1",
        searched_types=[],
    ),
]


class CibAsWholeValid(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.verify()

    def test_success_on_valid(self):
        (self.config
            .runner.cib.load()
            .runner.pcmk.load_state()
        )
        verify(self.env_assist.get_env())

    def test_fail_on_invalid_fence_topology(self):
        (self.config
            .runner.cib.load(optional_in_conf=BAD_FENCING_TOPOLOGY)
            .runner.pcmk.load_state()
        )
        self.env_assist.assert_raise_library_error(
            lambda: verify(self.env_assist.get_env()),
            list(BAD_FENCING_TOPOLOGY_REPORTS)
        )


class CibAsWholeInvalid(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.verify(stderr=CRM_VERIFY_ERROR_REPORT)

    def assert_raises_invalid_cib_content(self, extra_reports=None):
        extra_reports = extra_reports if extra_reports else []
        self.env_assist.assert_raise_library_error(
            lambda: verify(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.INVALID_CIB_CONTENT,
                    report=CRM_VERIFY_ERROR_REPORT,
                ),
            ] + extra_reports,
        )

    def test_fail_immediately_on_unloadable_cib(self):
        self.config.runner.cib.load(returncode=1)
        self.assert_raises_invalid_cib_content()

    def test_continue_on_loadable_cib(self):
        (self.config
            .runner.cib.load()
            .runner.pcmk.load_state()
        )
        self.assert_raises_invalid_cib_content()

    def test_add_following_errors(self):
        #More fencing topology tests are provided by tests of
        #pcs.lib.commands.fencing_topology
        (self.config
            .runner.cib.load(optional_in_conf=BAD_FENCING_TOPOLOGY)
            .runner.pcmk.load_state()
        )
        self.assert_raises_invalid_cib_content(
            list(BAD_FENCING_TOPOLOGY_REPORTS)
        )

class CibIsMocked(TestCase):
    def test_success_on_valid_cib(self):
        cib_tempfile = "/fake/tmp/file"
        env_assist, config = get_env_tools(test_case=self)
        (config
            .env.set_cib_data("<cib/>", cib_tempfile=cib_tempfile)
            .runner.pcmk.verify(cib_tempfile=cib_tempfile)
            .runner.cib.load()
            .runner.pcmk.load_state()
        )
        verify(env_assist.get_env())

class VerboseMode(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.verify(verbose=True)

    def test_success_on_valid_cib(self):
        (self.config
            .runner.cib.load()
            .runner.pcmk.load_state()
        )
        verify(self.env_assist.get_env(), verbose=True)

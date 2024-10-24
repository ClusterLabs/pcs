from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common.reports import codes as report_codes
from pcs.lib.commands.cluster import verify

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc

CRM_VERIFY_ERROR_REPORT_LINES = [
    "something wrong\nsomething else wrong\n",
    "  Use -V -V for more detail\n",
]

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

BAD_RESOURCES = """
    <resources>
        <bundle id="bundle-bad">
            <rkt image="pcs:test" />
        </bundle>
    </resources>
"""
BAD_RESOURCES_REPORTS = [
    fixture.error(
        report_codes.RESOURCE_BUNDLE_UNSUPPORTED_CONTAINER_TYPE,
        bundle_id="bundle-bad",
        supported_container_types=["docker", "podman"],
        updating_options=False,
    ),
]


class AssertInvalidCibMixin:
    def assert_raises_invalid_cib_content(
        self,
        report,
        extra_reports=None,
        can_be_more_verbose=True,
        verbose=False,
    ):
        extra_reports = extra_reports if extra_reports else []
        self.env_assist.assert_raise_library_error(
            lambda: verify(self.env_assist.get_env(), verbose)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_CIB_CONTENT,
                    report=report,
                    can_be_more_verbose=can_be_more_verbose,
                ),
            ]
            + extra_reports,
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class CibAsWholeValid(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.verify()

    def test_success_on_valid(self):
        self.config.runner.cib.load().runner.pcmk.load_state()
        verify(self.env_assist.get_env())

    def test_fail_on_invalid_fence_topology(self):
        self.config.runner.cib.load(
            optional_in_conf=BAD_FENCING_TOPOLOGY
        ).runner.pcmk.load_state()
        self.env_assist.assert_raise_library_error(
            lambda: verify(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(BAD_FENCING_TOPOLOGY_REPORTS)

    def test_fail_on_invalid_bundle_containers(self):
        self.config.runner.cib.load(
            resources=BAD_RESOURCES
        ).runner.pcmk.load_state()
        self.env_assist.assert_raise_library_error(
            lambda: verify(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(BAD_RESOURCES_REPORTS)


class CibAsWholeInvalid(TestCase, AssertInvalidCibMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.verify(
            stderr="".join(CRM_VERIFY_ERROR_REPORT_LINES)
        )

    def test_fail_immediately_on_unloadable_cib(self):
        self.config.runner.cib.load(returncode=1)
        self.assert_raises_invalid_cib_content(CRM_VERIFY_ERROR_REPORT_LINES[0])

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_continue_on_loadable_cib(self):
        self.config.runner.cib.load().runner.pcmk.load_state()
        self.assert_raises_invalid_cib_content(CRM_VERIFY_ERROR_REPORT_LINES[0])

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_add_following_errors(self):
        # More fencing topology tests are provided by tests of
        # pcs.lib.commands.fencing_topology
        self.config.runner.cib.load(
            resources=BAD_RESOURCES, optional_in_conf=BAD_FENCING_TOPOLOGY
        ).runner.pcmk.load_state()
        self.assert_raises_invalid_cib_content(
            CRM_VERIFY_ERROR_REPORT_LINES[0],
            extra_reports=BAD_FENCING_TOPOLOGY_REPORTS + BAD_RESOURCES_REPORTS,
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class CibIsMocked(TestCase, AssertInvalidCibMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.cib_tempfile = "/fake/tmp/file"
        self.cmd_env = dict(CIB_file=self.cib_tempfile)
        self.config.env.set_cib_data("<cib/>", cib_tempfile=self.cib_tempfile)

    def test_success_on_valid_cib(self):
        self.config.runner.pcmk.verify(
            cib_tempfile=self.cib_tempfile, env=self.cmd_env
        )
        self.config.runner.cib.load(env=self.cmd_env)
        self.config.runner.pcmk.load_state(env=self.cmd_env)
        verify(self.env_assist.get_env())

    def test_fail_on_invalid_cib(self):
        self.config.runner.pcmk.verify(
            stderr="".join(CRM_VERIFY_ERROR_REPORT_LINES),
            cib_tempfile=self.cib_tempfile,
            env=self.cmd_env,
        )
        self.config.runner.cib.load(env=self.cmd_env)
        self.config.runner.pcmk.load_state(env=self.cmd_env)
        self.assert_raises_invalid_cib_content(CRM_VERIFY_ERROR_REPORT_LINES[0])


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class VerboseMode(TestCase, AssertInvalidCibMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success_on_valid_cib(self):
        self.config.runner.pcmk.verify(verbose=True)
        self.config.runner.cib.load()
        self.config.runner.pcmk.load_state()
        verify(self.env_assist.get_env(), verbose=True)

    def test_fail_on_invalid_cib(self):
        self.config.runner.pcmk.verify(
            stderr=CRM_VERIFY_ERROR_REPORT_LINES[0],
            verbose=True,
        )
        self.config.runner.cib.load()
        self.config.runner.pcmk.load_state()
        self.assert_raises_invalid_cib_content(
            CRM_VERIFY_ERROR_REPORT_LINES[0],
            can_be_more_verbose=False,
            verbose=True,
        )

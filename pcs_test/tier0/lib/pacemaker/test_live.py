# pylint: disable=too-many-lines
from unittest import TestCase, mock

from lxml import etree

import pcs.lib.pacemaker.live as lib
from pcs import settings
from pcs.common.reports import codes as report_codes
from pcs.common.tools import Version
from pcs.common.types import CibRuleInEffectStatus
from pcs.lib.external import CommandRunner
from pcs.lib.resource_agent import ResourceAgentName

from pcs_test.tools import fixture, fixture_crm_mon
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
    assert_xml_equal,
    start_tag_error_text,
)
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import TmpFileCall, TmpFileMock
from pcs_test.tools.custom_mock import get_runner_mock as get_runner
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import XmlManipulation, etree_to_str

_EXITCODE_NOT_CONNECTED = 102


class GetClusterStatusMixin(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self._xml_summary = etree_to_str(
            etree.parse(rc("crm_mon.minimal.xml")).find("summary")
        )

    def fixture_xml(self, transformed=False):
        as_xml = "--as-xml" if transformed else "--output-as xml"
        return f"""
            <pacemaker-result api-version="2.3" request="crm_mon {as_xml}">
              {self._xml_summary}
              <nodes />
              <resources />
              <status code="0" message="OK" />
            </pacemaker-result>
        """


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class GetClusterStatusXml(GetClusterStatusMixin, TestCase):
    # pylint: disable=protected-access
    def test_success(self):
        self.config.runner.pcmk.load_state(stdout=self.fixture_xml())
        env = self.env_assist.get_env()
        assert_xml_equal(
            self.fixture_xml(), lib._get_cluster_status_xml(env.cmd_runner())
        )

    def test_error(self):
        self.config.runner.pcmk.load_state(
            stdout=fixture_crm_mon.error_xml(
                1, "an error", ["This is an error message", "And one more"]
            ),
            returncode=1,
        )
        env = self.env_assist.get_env()
        assert_raise_library_error(
            lambda: lib._get_cluster_status_xml(env.cmd_runner()),
            fixture.error(
                report_codes.CRM_MON_ERROR,
                reason="an error\nThis is an error message\nAnd one more",
            ),
        )

    def test_error_not_xml(self):
        self.config.runner.pcmk.load_state(
            stdout="stdout text",
            stderr="stderr text",
            returncode=1,
        )
        env = self.env_assist.get_env()
        assert_raise_library_error(
            lambda: lib._get_cluster_status_xml(env.cmd_runner()),
            fixture.error(
                report_codes.CRM_MON_ERROR,
                reason="stderr text\nstdout text",
            ),
        )

    def test_error_invalid_xml(self):
        self.config.runner.pcmk.load_state(stdout="<xml/>", returncode=1)
        env = self.env_assist.get_env()
        assert_raise_library_error(
            lambda: lib._get_cluster_status_xml(env.cmd_runner()),
            fixture.error(report_codes.BAD_CLUSTER_STATE_FORMAT),
        )

    def test_error_not_connected(self):
        self.config.runner.pcmk.load_state(
            stdout=fixture_crm_mon.error_xml_not_connected(),
            returncode=_EXITCODE_NOT_CONNECTED,
        )
        env = self.env_assist.get_env()
        with self.assertRaises(lib.PacemakerNotConnectedException) as cm:
            lib._get_cluster_status_xml(env.cmd_runner())
        assert_report_item_list_equal(
            cm.exception.args,
            [
                fixture.error(
                    report_codes.CRM_MON_ERROR,
                    reason=(
                        "Not connected\n"
                        "crm_mon: Error: cluster is not available on this node"
                    ),
                ),
            ],
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class GetClusterStatusDom(GetClusterStatusMixin, TestCase):
    def test_success(self):
        self.config.runner.pcmk.load_state(stdout=self.fixture_xml())
        env = self.env_assist.get_env()
        assert_xml_equal(
            self.fixture_xml(),
            etree_to_str(lib.get_cluster_status_dom(env.cmd_runner())),
        )

    def test_not_xml(self):
        self.config.runner.pcmk.load_state(
            stdout="<pacemaker-result> not an xml"
        )
        env = self.env_assist.get_env()
        assert_raise_library_error(
            lambda: lib.get_cluster_status_dom(env.cmd_runner()),
            fixture.error(report_codes.BAD_CLUSTER_STATE_FORMAT),
        )

    def test_invalid_xml(self):
        self.config.runner.pcmk.load_state(stdout="<pacemaker-result/>")
        env = self.env_assist.get_env()
        assert_raise_library_error(
            lambda: lib.get_cluster_status_dom(env.cmd_runner()),
            fixture.error(report_codes.BAD_CLUSTER_STATE_FORMAT),
        )


class GetClusterStatusText(TestCase):
    def setUp(self):
        self.mock_fencehistory_supported = mock.patch(
            "pcs.lib.pacemaker.live.is_fence_history_supported_status",
            return_value=True,
        )
        self.mock_fencehistory_supported.start()
        self.expected_stdout = "cluster status"
        self.expected_stderr = ""
        self.expected_retval = 0

    def tearDown(self):
        self.mock_fencehistory_supported.stop()

    def get_runner(self, stdout=None, stderr=None, retval=None):
        return get_runner(
            self.expected_stdout if stdout is None else stdout,
            self.expected_stderr if stderr is None else stderr,
            self.expected_retval if retval is None else retval,
        )

    def test_success_minimal(self):
        mock_runner = self.get_runner()
        real_status, warnings = lib.get_cluster_status_text(
            mock_runner, False, False
        )

        mock_runner.run.assert_called_once_with(
            [settings.crm_mon_exec, "--one-shot", "--inactive"]
        )
        self.assertEqual(self.expected_stdout, real_status)
        self.assertEqual(warnings, [])

    def test_success_verbose(self):
        mock_runner = self.get_runner()
        real_status, warnings = lib.get_cluster_status_text(
            mock_runner, False, True
        )

        mock_runner.run.assert_called_once_with(
            [
                settings.crm_mon_exec,
                "--one-shot",
                "--inactive",
                "--show-detail",
                "--show-node-attributes",
                "--failcounts",
                "--fence-history=3",
            ]
        )
        self.assertEqual(self.expected_stdout, real_status)
        self.assertEqual(warnings, [])

    def test_success_no_fence_history(self):
        self.mock_fencehistory_supported.stop()
        self.mock_fencehistory_supported = mock.patch(
            "pcs.lib.pacemaker.live.is_fence_history_supported_status",
            return_value=False,
        )
        self.mock_fencehistory_supported.start()

        mock_runner = self.get_runner()
        real_status, warnings = lib.get_cluster_status_text(
            mock_runner, False, True
        )

        mock_runner.run.assert_called_once_with(
            [
                settings.crm_mon_exec,
                "--one-shot",
                "--inactive",
                "--show-detail",
                "--show-node-attributes",
                "--failcounts",
            ]
        )
        self.assertEqual(self.expected_stdout, real_status)
        self.assertEqual(warnings, [])

    def test_success_hide_inactive(self):
        mock_runner = self.get_runner()
        real_status, warnings = lib.get_cluster_status_text(
            mock_runner, True, False
        )

        mock_runner.run.assert_called_once_with(
            [settings.crm_mon_exec, "--one-shot"]
        )
        self.assertEqual(self.expected_stdout, real_status)
        self.assertEqual(warnings, [])

    def test_success_hide_inactive_verbose(self):
        mock_runner = self.get_runner()
        real_status, warnings = lib.get_cluster_status_text(
            mock_runner, True, True
        )

        mock_runner.run.assert_called_once_with(
            [
                settings.crm_mon_exec,
                "--one-shot",
                "--show-detail",
                "--show-node-attributes",
                "--failcounts",
                "--fence-history=3",
            ]
        )
        self.assertEqual(self.expected_stdout, real_status)
        self.assertEqual(warnings, [])

    def test_error(self):
        mock_runner = self.get_runner("stdout", "stderr", 1)
        assert_raise_library_error(
            lambda: lib.get_cluster_status_text(mock_runner, False, False),
            (
                fixture.error(
                    report_codes.CRM_MON_ERROR, reason="stderr\nstdout"
                )
            ),
        )
        mock_runner.run.assert_called_once_with(
            [settings.crm_mon_exec, "--one-shot", "--inactive"]
        )

    def test_warnings(self):
        mock_runner = self.get_runner(
            stderr="msgA\nDEBUG: msgB\nmsgC\nDEBUG: msgd\n"
        )
        real_status, warnings = lib.get_cluster_status_text(
            mock_runner, False, False
        )

        mock_runner.run.assert_called_once_with(
            [settings.crm_mon_exec, "--one-shot", "--inactive"]
        )
        self.assertEqual(self.expected_stdout, real_status)
        self.assertEqual(warnings, ["msgA", "msgC"])

    def test_warnings_verbose(self):
        mock_runner = self.get_runner(
            stderr="msgA\nDEBUG: msgB\nmsgC\nDEBUG: msgd\n"
        )
        real_status, warnings = lib.get_cluster_status_text(
            mock_runner, False, True
        )

        mock_runner.run.assert_called_once_with(
            [
                settings.crm_mon_exec,
                "--one-shot",
                "--inactive",
                "--show-detail",
                "--show-node-attributes",
                "--failcounts",
                "--fence-history=3",
            ]
        )
        self.assertEqual(self.expected_stdout, real_status)
        self.assertEqual(
            warnings, ["msgA", "DEBUG: msgB", "msgC", "DEBUG: msgd"]
        )


class GetCibXmlTest(TestCase):
    def test_success(self):
        expected_stdout = "<xml />"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        real_xml = lib.get_cib_xml(mock_runner)

        mock_runner.run.assert_called_once_with(
            [settings.cibadmin_exec, "--local", "--query"]
        )
        self.assertEqual(expected_stdout, real_xml)

    def test_error(self):
        # pylint: disable=no-self-use
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        assert_raise_library_error(
            lambda: lib.get_cib_xml(mock_runner),
            (
                fixture.error(
                    report_codes.CIB_LOAD_ERROR,
                    reason=expected_stderr + "\n" + expected_stdout,
                )
            ),
        )

        mock_runner.run.assert_called_once_with(
            [settings.cibadmin_exec, "--local", "--query"]
        )

    def test_success_scope(self):
        expected_stdout = "<xml />"
        expected_stderr = ""
        expected_retval = 0
        scope = "test_scope"
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        real_xml = lib.get_cib_xml(mock_runner, scope)

        mock_runner.run.assert_called_once_with(
            [
                settings.cibadmin_exec,
                "--local",
                "--query",
                "--scope={0}".format(scope),
            ]
        )
        self.assertEqual(expected_stdout, real_xml)

    def test_scope_error(self):
        # pylint: disable=no-self-use
        expected_stdout = "some info"
        # yes, the numbers do not match, tested and verified with
        # pacemaker-2.0.0-1.fc29.1.x86_64
        expected_stderr = (
            "Call cib_query failed (-6): No such device or address"
        )
        expected_retval = 105
        scope = "test_scope"
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        assert_raise_library_error(
            lambda: lib.get_cib_xml(mock_runner, scope=scope),
            (
                fixture.error(
                    report_codes.CIB_LOAD_ERROR_SCOPE_MISSING,
                    scope=scope,
                    reason=expected_stderr + "\n" + expected_stdout,
                )
            ),
        )

        mock_runner.run.assert_called_once_with(
            [
                settings.cibadmin_exec,
                "--local",
                "--query",
                "--scope={0}".format(scope),
            ]
        )


class GetCibTest(TestCase):
    # pylint: disable=no-self-use
    def test_success(self):
        xml = "<xml />"
        assert_xml_equal(xml, str(XmlManipulation((lib.get_cib(xml)))))

    @mock.patch("pcs.lib.pacemaker.live.xml_fromstring")
    def test_invalid_xml(self, xml_fromstring_mock):
        reason = "custom reason"
        xml_fromstring_mock.side_effect = etree.XMLSyntaxError(reason, 1, 1, 1)
        xml = "<invalid><xml />"
        assert_raise_library_error(
            lambda: lib.get_cib(xml),
            fixture.error(
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                reason=f"{reason} (line 1)",
            ),
        )
        xml_fromstring_mock.assert_called_once_with(xml)


class Verify(TestCase):
    def test_run_on_live_cib(self):
        runner = get_runner()
        self.assertEqual(lib.verify(runner), ("", "", 0, False))
        runner.run.assert_called_once_with(
            [settings.crm_verify_exec, "--live-check"],
        )

    def test_run_on_mocked_cib(self):
        fake_tmp_file = "/fake/tmp/file"
        runner = get_runner(env_vars={"CIB_file": fake_tmp_file})

        self.assertEqual(lib.verify(runner), ("", "", 0, False))
        runner.run.assert_called_once_with(
            [settings.crm_verify_exec, "--xml-file", fake_tmp_file],
        )

    def test_run_verbose(self):
        runner = get_runner()
        self.assertEqual(lib.verify(runner, verbose=True), ("", "", 0, False))
        runner.run.assert_called_once_with(
            [settings.crm_verify_exec, "-V", "-V", "--live-check"],
        )

    def test_run_verbose_on_mocked_cib(self):
        fake_tmp_file = "/fake/tmp/file"
        runner = get_runner(env_vars={"CIB_file": fake_tmp_file})

        self.assertEqual(lib.verify(runner, verbose=True), ("", "", 0, False))
        runner.run.assert_called_once_with(
            [settings.crm_verify_exec, "-V", "-V", "--xml-file", fake_tmp_file],
        )

    @staticmethod
    def get_in_out_filtered_stderr():
        in_stderr = (
            (
                "Errors found during check: config not valid\n",
                "  -V may provide more details\n",
            ),
            (
                "Warnings found during check: config may not be valid\n",
                "  Use -V -V for more detail\n",
            ),
            (
                "some output\n",
                "another output\n",
                "-V -V -V more details...\n",
            ),
            (
                "some output\n",
                "before-V -V -V in the middle more detailafter\n",
                "another output\n",
            ),
        )
        out_stderr = [
            [line for line in input_lines if "-V" not in line]
            for input_lines in in_stderr
        ]
        return zip(in_stderr, out_stderr, strict=False)

    @staticmethod
    def get_in_out_unfiltered_data():
        in_out_data = (
            ("no verbose option in stderr\n",),
            (
                "some output\n",
                "Options '-V -V' do not match\n",
                "because line missing 'more details'\n",
            ),
        )
        return zip(in_out_data, in_out_data, strict=False)

    def subtest_filter_stderr_and_can_be_more_verbose(
        self,
        in_out_tuple_list,
        can_be_more_verbose,
        verbose=False,
    ):
        fake_tmp_file = "/fake/tmp/file"
        runner = get_runner(env_vars={"CIB_file": fake_tmp_file})
        for in_stderr, out_stderr in in_out_tuple_list:
            with self.subTest(in_stderr=in_stderr, out_stderr=out_stderr):
                runner = get_runner(
                    stderr="".join(in_stderr),
                    returncode=78,
                    env_vars={"CIB_file": fake_tmp_file},
                )
                self.assertEqual(
                    lib.verify(runner, verbose=verbose),
                    ("", "".join(out_stderr), 78, can_be_more_verbose),
                )
                args = [settings.crm_verify_exec]
                if verbose:
                    args.extend(["-V", "-V"])
                args.extend(["--xml-file", fake_tmp_file])
                runner.run.assert_called_once_with(args)

    def test_error_can_be_more_verbose(self):
        self.subtest_filter_stderr_and_can_be_more_verbose(
            self.get_in_out_filtered_stderr(),
            True,
        )

    def test_error_cannot_be_more_verbose(self):
        self.subtest_filter_stderr_and_can_be_more_verbose(
            self.get_in_out_unfiltered_data(),
            False,
        )

    def test_error_cannot_be_more_verbose_in_verbose_mode(self):
        self.subtest_filter_stderr_and_can_be_more_verbose(
            (
                list(self.get_in_out_filtered_stderr())
                + list(self.get_in_out_unfiltered_data())
            ),
            False,
            verbose=True,
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class GetCibVerificationErrors(TestCase):
    fixture_ok = """
        <pacemaker-result api-version="2.38"
            request="crm_verify --live-check --output-as=xml"
        >
          <status code="0" message="OK"/>
        </pacemaker-result>
    """

    def test_run_on_live_cib(self):
        runner = get_runner(self.fixture_ok)
        self.assertEqual(lib.get_cib_verification_errors(runner), [])
        runner.run.assert_called_once_with(
            [settings.crm_verify_exec, "--output-as", "xml", "--live-check"],
        )

    def test_run_on_mocked_cib(self):
        fake_tmp_file = "/fake/tmp/file"
        runner = get_runner(
            self.fixture_ok, env_vars={"CIB_file": fake_tmp_file}
        )

        self.assertEqual(lib.get_cib_verification_errors(runner), [])
        runner.run.assert_called_once_with(
            [
                settings.crm_verify_exec,
                "--output-as",
                "xml",
                "--xml-file",
                fake_tmp_file,
            ],
        )

    def test_errors_present(self):
        fixture_errors = """
            <pacemaker-result api-version="2.38"
                request="crm_verify --live-check --output-as=xml"
            >
              <status code="78" message="Invalid configuration">
                <errors>
                  <error>error: Somewthing wrong with &lt;clone&gt; bad-clone</error>
                  <error>error: CIB did not pass schema validation</error>
                  <error>Configuration invalid (with errors)</error>
                </errors>
              </status>
            </pacemaker-result>
        """
        runner = get_runner(fixture_errors)
        self.assertEqual(
            lib.get_cib_verification_errors(runner),
            [
                "error: Somewthing wrong with <clone> bad-clone",
                "error: CIB did not pass schema validation",
                "Configuration invalid (with errors)",
            ],
        )
        runner.run.assert_called_once_with(
            [settings.crm_verify_exec, "--output-as", "xml", "--live-check"],
        )

    def test_not_xml_response(self):
        runner = get_runner("not xml output")
        with self.assertRaises(lib.BadApiResultFormat) as cm:
            lib.get_cib_verification_errors(runner)
        self.assertEqual(cm.exception.pacemaker_response, "not xml output")
        self.assertEqual(
            type(cm.exception.original_exception), etree.XMLSyntaxError
        )

        runner.run.assert_called_once_with(
            [settings.crm_verify_exec, "--output-as", "xml", "--live-check"],
        )


class ReplaceCibConfigurationTest(TestCase):
    # pylint: disable=no-self-use
    def test_success(self):
        xml = "<xml/>"
        expected_stdout = "expected output"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        lib.replace_cib_configuration(
            mock_runner, XmlManipulation.from_str(xml).tree
        )

        mock_runner.run.assert_called_once_with(
            [
                settings.cibadmin_exec,
                "--replace",
                "--verbose",
                "--xml-pipe",
                "--scope",
                "configuration",
            ],
            stdin_string=xml,
        )

    def test_error(self):
        xml = "<xml/>"
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        assert_raise_library_error(
            lambda: lib.replace_cib_configuration(
                mock_runner, XmlManipulation.from_str(xml).tree
            ),
            (
                fixture.error(
                    report_codes.CIB_PUSH_ERROR,
                    reason=expected_stderr,
                    pushed_cib=expected_stdout,
                )
            ),
        )

        mock_runner.run.assert_called_once_with(
            [
                settings.cibadmin_exec,
                "--replace",
                "--verbose",
                "--xml-pipe",
                "--scope",
                "configuration",
            ],
            stdin_string=xml,
        )


class UpgradeCibTest(TestCase):
    # pylint: disable=protected-access
    # pylint: disable=no-self-use
    def test_success(self):
        mock_runner = get_runner("", "", 0)
        lib._upgrade_cib(mock_runner)
        mock_runner.run.assert_called_once_with(
            [settings.cibadmin_exec, "--upgrade", "--force"]
        )

    def test_error(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )
        assert_raise_library_error(
            lambda: lib._upgrade_cib(mock_runner),
            (
                fixture.error(
                    report_codes.CIB_UPGRADE_FAILED,
                    reason=expected_stderr + "\n" + expected_stdout,
                )
            ),
        )
        mock_runner.run.assert_called_once_with(
            [settings.cibadmin_exec, "--upgrade", "--force"]
        )


@mock.patch("pcs.lib.pacemaker.live.get_cib_xml")
@mock.patch("pcs.lib.pacemaker.live._upgrade_cib")
class EnsureCibVersionTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.cib = etree.XML('<cib validate-with="pacemaker-2.3.4"/>')

    def test_same_version(self, mock_upgrade, mock_get_cib):
        actual_cib, was_upgraded = lib.ensure_cib_version(
            self.mock_runner, self.cib, Version(2, 3, 4)
        )
        self.assertEqual(self.cib, actual_cib)
        self.assertFalse(was_upgraded)
        mock_upgrade.assert_not_called()
        mock_get_cib.assert_not_called()

    def test_higher_version(self, mock_upgrade, mock_get_cib):
        actual_cib, was_upgraded = lib.ensure_cib_version(
            self.mock_runner, self.cib, Version(2, 3, 3)
        )
        self.assertEqual(self.cib, actual_cib)
        self.assertFalse(was_upgraded)
        mock_upgrade.assert_not_called()
        mock_get_cib.assert_not_called()

    def test_upgraded_same_version(self, mock_upgrade, mock_get_cib):
        expected_cib = '<cib validate-with="pacemaker-2.3.5"/>'
        mock_get_cib.return_value = expected_cib
        actual_cib, was_upgraded = lib.ensure_cib_version(
            self.mock_runner, self.cib, Version(2, 3, 5)
        )
        assert_xml_equal(expected_cib, etree.tostring(actual_cib).decode())
        self.assertTrue(was_upgraded)
        mock_upgrade.assert_called_once_with(self.mock_runner)
        mock_get_cib.assert_called_once_with(self.mock_runner)

    def test_upgraded_higher_version(self, mock_upgrade, mock_get_cib):
        expected_cib = '<cib validate-with="pacemaker-2.3.6"/>'
        mock_get_cib.return_value = expected_cib
        actual_cib, was_upgraded = lib.ensure_cib_version(
            self.mock_runner, self.cib, Version(2, 3, 5)
        )
        assert_xml_equal(expected_cib, etree.tostring(actual_cib).decode())
        self.assertTrue(was_upgraded)
        mock_upgrade.assert_called_once_with(self.mock_runner)
        mock_get_cib.assert_called_once_with(self.mock_runner)

    def test_upgraded_lower_version(self, mock_upgrade, mock_get_cib):
        mock_get_cib.return_value = etree.tostring(self.cib).decode()
        assert_raise_library_error(
            lambda: lib.ensure_cib_version(
                self.mock_runner, self.cib, Version(2, 3, 5)
            ),
            (
                fixture.error(
                    report_codes.CIB_UPGRADE_FAILED_TO_MINIMAL_REQUIRED_VERSION,
                    required_version="2.3.5",
                    current_version="2.3.4",
                )
            ),
        )
        mock_upgrade.assert_called_once_with(self.mock_runner)
        mock_get_cib.assert_called_once_with(self.mock_runner)

    def test_upgraded_lower_version_dont_fail(self, mock_upgrade, mock_get_cib):
        expected_cib = '<cib validate-with="pacemaker-2.3.4"/>'
        mock_get_cib.return_value = expected_cib
        actual_cib, was_upgraded = lib.ensure_cib_version(
            self.mock_runner,
            self.cib,
            Version(2, 3, 5),
            fail_if_version_not_met=False,
        )
        assert_xml_equal(expected_cib, etree.tostring(actual_cib).decode())
        self.assertFalse(was_upgraded)
        mock_upgrade.assert_called_once_with(self.mock_runner)
        mock_get_cib.assert_called_once_with(self.mock_runner)

    def test_cib_parse_error(self, mock_upgrade, mock_get_cib):
        mock_get_cib.return_value = "not xml"
        assert_raise_library_error(
            lambda: lib.ensure_cib_version(
                self.mock_runner, self.cib, Version(2, 3, 5)
            ),
            (
                fixture.error(
                    report_codes.CIB_UPGRADE_FAILED,
                    reason=start_tag_error_text(),
                )
            ),
        )
        mock_upgrade.assert_called_once_with(self.mock_runner)
        mock_get_cib.assert_called_once_with(self.mock_runner)


class SimulateCibXml(TestCase):
    def setUp(self):
        tmp_file_patcher = mock.patch("pcs.lib.tools.get_tmp_file")
        self.addCleanup(tmp_file_patcher.stop)
        self.tmp_file_mock_obj = TmpFileMock()
        self.addCleanup(self.tmp_file_mock_obj.assert_all_done)
        tmp_file_mock = tmp_file_patcher.start()
        tmp_file_mock.side_effect = (
            self.tmp_file_mock_obj.get_mock_side_effect()
        )

    def test_success(self):
        orig_cib_data = "orig cib"
        cib_file_name = "new_cib_file.tmp"
        transitions_file_name = "transitions.tmp"
        new_cib_data = "new cib data"
        transitions_data = "transitions data"
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall(cib_file_name, new_content=new_cib_data),
                TmpFileCall(
                    transitions_file_name, new_content=transitions_data
                ),
            ]
        )

        expected_stdout = "simulate output"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        result = lib.simulate_cib_xml(mock_runner, orig_cib_data)
        self.assertEqual(result[0], expected_stdout)
        self.assertEqual(result[1], transitions_data)
        self.assertEqual(result[2], new_cib_data)

        mock_runner.run.assert_called_once_with(
            [
                settings.crm_simulate_exec,
                "--simulate",
                "--save-output",
                cib_file_name,
                "--save-graph",
                transitions_file_name,
                "--xml-pipe",
            ],
            stdin_string=orig_cib_data,
        )

    def test_error_creating_cib(self):
        err_msg = "some error"
        self.tmp_file_mock_obj.set_calls(
            [TmpFileCall("a file", orig_content=OSError(1, err_msg))]
        )
        mock_runner = get_runner()
        assert_raise_library_error(
            lambda: lib.simulate_cib_xml(mock_runner, "<cib />"),
            fixture.error(
                report_codes.CIB_SIMULATE_ERROR,
                reason=err_msg,
            ),
        )
        mock_runner.run.assert_not_called()

    def test_error_creating_transitions(self):
        err_msg = "some error"
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall("cib_file"),
                TmpFileCall("transitions", orig_content=OSError(1, err_msg)),
            ]
        )
        mock_runner = get_runner()
        assert_raise_library_error(
            lambda: lib.simulate_cib_xml(mock_runner, "<cib />"),
            fixture.error(
                report_codes.CIB_SIMULATE_ERROR,
                reason=err_msg,
            ),
        )
        mock_runner.run.assert_not_called()

    def test_error_running_simulate(self):
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall("cib_file"),
                TmpFileCall("transitions_file"),
            ]
        )
        expected_stdout = "some stdout"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        assert_raise_library_error(
            lambda: lib.simulate_cib_xml(mock_runner, "<cib />"),
            fixture.error(
                report_codes.CIB_SIMULATE_ERROR,
                reason="some error",
            ),
        )

    def test_error_reading_cib(self):
        err_msg = "some error"
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall("cib_file", new_content=OSError(1, err_msg)),
                TmpFileCall("transitions", new_content=""),
            ]
        )

        expected_stdout = "simulate output"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        assert_raise_library_error(
            lambda: lib.simulate_cib_xml(mock_runner, "<cib />"),
            fixture.error(
                report_codes.CIB_SIMULATE_ERROR,
                reason=err_msg,
            ),
        )

    def test_error_reading_transitions(self):
        err_msg = "some error"
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall("cib_file", new_content=""),
                TmpFileCall("transitions", new_content=OSError(1, err_msg)),
            ]
        )

        expected_stdout = "simulate output"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        assert_raise_library_error(
            lambda: lib.simulate_cib_xml(mock_runner, "<cib />"),
            fixture.error(
                report_codes.CIB_SIMULATE_ERROR,
                reason=err_msg,
            ),
        )


@mock.patch("pcs.lib.pacemaker.live.simulate_cib_xml")
class SimulateCib(TestCase):
    def setUp(self):
        self.runner = "mock runner"
        self.cib_xml = "<cib/>"
        self.cib = etree.fromstring(self.cib_xml)
        self.simulate_output = "  some output  "
        self.transitions = "<transitions/>"
        self.new_cib = "<new-cib/>"

    def test_success(self, mock_simulate):
        mock_simulate.return_value = (
            self.simulate_output,
            self.transitions,
            self.new_cib,
        )
        result = lib.simulate_cib(self.runner, self.cib)
        self.assertEqual(result[0], "some output")
        assert_xml_equal(self.transitions, etree_to_str(result[1]))
        assert_xml_equal(self.new_cib, etree_to_str(result[2]))
        mock_simulate.assert_called_once_with(self.runner, self.cib_xml)

    def test_invalid_cib(self, mock_simulate):
        mock_simulate.return_value = (
            self.simulate_output,
            "bad transitions",
            self.new_cib,
        )
        assert_raise_library_error(
            lambda: lib.simulate_cib(self.runner, self.cib),
            fixture.error(
                report_codes.CIB_SIMULATE_ERROR,
                reason=(
                    "Start tag expected, '<' not found, line 1, column 1 "
                    "(<string>, line 1)"
                ),
            ),
        )

    def test_invalid_transitions(self, mock_simulate):
        mock_simulate.return_value = (
            self.simulate_output,
            self.transitions,
            "bad new cib",
        )
        assert_raise_library_error(
            lambda: lib.simulate_cib(self.runner, self.cib),
            fixture.error(
                report_codes.CIB_SIMULATE_ERROR,
                reason=(
                    "Start tag expected, '<' not found, line 1, column 1 "
                    "(<string>, line 1)"
                ),
            ),
        )


class GetLocalNodeName(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        expected_name = "node-name"
        self.config.runner.pcmk.local_node_name(node_name=expected_name)
        env = self.env_assist.get_env()
        real_name = lib.get_local_node_name(env.cmd_runner())
        self.assertEqual(expected_name, real_name)

    def test_error(self):
        self.config.runner.pcmk.local_node_name(
            stdout="some info", stderr="some error", returncode=1
        )
        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.get_local_node_name(env.cmd_runner()),
            [
                fixture.error(
                    report_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
                    force_code=None,
                    reason="some error\nsome info",
                )
            ],
            expected_in_processor=False,
        )

    def test_error_not_connected(self):
        stderr = (
            "error: Could not connect to controller: Transport endpoint is "
            "not connected\n"
        )
        self.config.runner.pcmk.local_node_name(
            stderr=stderr,
            returncode=_EXITCODE_NOT_CONNECTED,
        )
        env = self.env_assist.get_env()
        with self.assertRaises(lib.PacemakerNotConnectedException) as cm:
            lib.get_local_node_name(env.cmd_runner())
        assert_report_item_list_equal(
            cm.exception.args,
            [
                (
                    fixture.error(
                        report_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
                        reason=stderr.strip(),
                    )
                ),
            ],
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class GetLocalNodeStatusTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.nodes_xml = """
            <nodes>
                <node id="1" name="name_1" />
                <node id="2" name="name_2" />
                <node id="3" name="name_3" />
                <node id="4" name="name_4" />
            </nodes>
        """

    def test_offline_status(self):
        self.config.runner.pcmk.load_state(
            stdout=fixture_crm_mon.error_xml_not_connected(),
            returncode=_EXITCODE_NOT_CONNECTED,
        )

        env = self.env_assist.get_env()
        real_status = lib.get_local_node_status(env.cmd_runner())
        self.assertEqual(dict(offline=True), real_status)

    def test_offline_node_name(self):
        self.config.runner.pcmk.load_state(nodes=self.nodes_xml)
        self.config.runner.pcmk.local_node_name(
            stderr=(
                "error: Could not connect to controller: Transport endpoint is "
                "not connected\n"
            ),
            returncode=_EXITCODE_NOT_CONNECTED,
        )

        env = self.env_assist.get_env()
        real_status = lib.get_local_node_status(env.cmd_runner())
        self.assertEqual(dict(offline=True), real_status)

    def test_invalid_status(self):
        self.config.runner.pcmk.load_state(stdout="invalid xml")

        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.get_local_node_status(env.cmd_runner()),
            [
                fixture.error(
                    report_codes.BAD_CLUSTER_STATE_FORMAT, force_code=None
                )
            ],
            expected_in_processor=False,
        )

    def test_success(self):
        self.config.runner.pcmk.load_state(
            nodes=self.nodes_xml
        ).runner.pcmk.local_node_name(node_name="name_2")

        env = self.env_assist.get_env()
        real_status = lib.get_local_node_status(env.cmd_runner())
        self.assertEqual("2", real_status.get("id"))

    def test_node_not_in_status(self):
        self.config.runner.pcmk.load_state(
            nodes=self.nodes_xml
        ).runner.pcmk.local_node_name(node_name="name_X")

        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.get_local_node_status(env.cmd_runner()),
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    force_code=None,
                    node="name_X",
                    searched_types=[],
                )
            ],
            expected_in_processor=False,
        )

    def test_error_getting_node_name(self):
        self.config.runner.pcmk.load_state(
            nodes=self.nodes_xml
        ).runner.pcmk.local_node_name(
            stdout="some info", stderr="some error", returncode=1
        )

        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.get_local_node_status(env.cmd_runner()),
            [
                fixture.error(
                    report_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
                    force_code=None,
                    reason="some error\nsome info",
                )
            ],
            expected_in_processor=False,
        )


class RemoveNode(TestCase):
    # pylint: disable=no-self-use
    def test_success(self):
        mock_runner = get_runner("", "", 0)
        lib.remove_node(mock_runner, "NODE_NAME")
        mock_runner.run.assert_called_once_with(
            [settings.crm_node_exec, "--force", "--remove", "NODE_NAME"]
        )

    def test_error(self):
        expected_stderr = "expected stderr"
        mock_runner = get_runner("", expected_stderr, 1)
        assert_raise_library_error(
            lambda: lib.remove_node(mock_runner, "NODE_NAME"),
            (
                fixture.error(
                    report_codes.NODE_REMOVE_IN_PACEMAKER_FAILED,
                    node="",
                    node_list_to_remove=["NODE_NAME"],
                    reason=expected_stderr,
                )
            ),
        )


class ResourceRestart(TestCase):
    def setUp(self):
        self.stdout = "expected output"
        self.stderr = "expected stderr"
        self.resource = "my_resource"
        self.node = "my_node"
        self.timeout = "10m"
        self.env_assist, self.config = get_env_tools(test_case=self)

    def assert_output(self, real_output):
        self.assertEqual(self.stdout + "\n" + self.stderr, real_output)

    def test_basic(self):
        self.config.runner.pcmk.resource_restart(
            self.resource, stdout=self.stdout, stderr=self.stderr
        )
        env = self.env_assist.get_env()
        lib.resource_restart(env.cmd_runner(), self.resource)

    def test_node(self):
        self.config.runner.pcmk.resource_restart(
            self.resource,
            node=self.node,
            stdout=self.stdout,
            stderr=self.stderr,
        )
        env = self.env_assist.get_env()
        lib.resource_restart(env.cmd_runner(), self.resource, node=self.node)

    def test_timeout(self):
        self.config.runner.pcmk.resource_restart(
            self.resource,
            timeout=self.timeout,
            stdout=self.stdout,
            stderr=self.stderr,
        )
        env = self.env_assist.get_env()
        lib.resource_restart(
            env.cmd_runner(), self.resource, timeout=self.timeout
        )

    def test_all_options(self):
        self.config.runner.pcmk.resource_restart(
            self.resource,
            node=self.node,
            timeout=self.timeout,
            stdout=self.stdout,
            stderr=self.stderr,
        )
        env = self.env_assist.get_env()
        lib.resource_restart(
            env.cmd_runner(),
            self.resource,
            node=self.node,
            timeout=self.timeout,
        )

    def test_error(self):
        self.config.runner.pcmk.resource_restart(
            self.resource, stdout=self.stdout, stderr=self.stderr, returncode=1
        )
        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.resource_restart(env.cmd_runner(), self.resource),
            [
                fixture.error(
                    report_codes.RESOURCE_RESTART_ERROR,
                    reason=(self.stderr + "\n" + self.stdout),
                    resource=self.resource,
                    node=None,
                )
            ],
            expected_in_processor=False,
        )


class ResourceCleanupTest(TestCase):
    def setUp(self):
        self.stdout = "expected output"
        self.stderr = "expected stderr"
        self.resource = "my_resource"
        self.node = "my_node"
        self.env_assist, self.config = get_env_tools(test_case=self)

    def assert_output(self, real_output):
        self.assertEqual(self.stdout + "\n" + self.stderr, real_output)

    def test_basic(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout, stderr=self.stderr
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_cleanup(env.cmd_runner())
        self.assert_output(real_output)

    def test_resource(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout, stderr=self.stderr, resource=self.resource
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_cleanup(
            env.cmd_runner(), resource=self.resource
        )
        self.assert_output(real_output)

    def test_resource_strict(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout,
            stderr=self.stderr,
            resource=self.resource,
            strict=True,
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_cleanup(
            env.cmd_runner(), resource=self.resource, strict=True
        )
        self.assert_output(real_output)

    def test_node(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout, stderr=self.stderr, node=self.node
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_cleanup(env.cmd_runner(), node=self.node)
        self.assert_output(real_output)

    def test_all_options(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout,
            stderr=self.stderr,
            resource=self.resource,
            node=self.node,
            strict=True,
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_cleanup(
            env.cmd_runner(),
            resource=self.resource,
            node=self.node,
            strict=True,
        )
        self.assert_output(real_output)

    def test_error_cleanup(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout, stderr=self.stderr, returncode=1
        )
        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.resource_cleanup(env.cmd_runner()),
            [
                fixture.error(
                    report_codes.RESOURCE_CLEANUP_ERROR,
                    reason=(self.stderr + "\n" + self.stdout),
                    resource=None,
                    node=None,
                )
            ],
            expected_in_processor=False,
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class ResourceRefreshTest(TestCase):
    def setUp(self):
        self.stdout = "expected output"
        self.stderr = "expected stderr"
        self.resource = "my_resource"
        self.node = "my_node"
        self.env_assist, self.config = get_env_tools(test_case=self)

    def assert_output(self, real_output):
        self.assertEqual(self.stdout + "\n" + self.stderr, real_output)

    @staticmethod
    def fixture_status_xml(nodes, resources):
        doc = etree.parse(rc("crm_mon.minimal.xml"))
        doc.find("summary/nodes_configured").set("number", str(nodes))
        doc.find("summary/resources_configured").set("number", str(resources))
        return etree_to_str(doc)

    def test_basic(self):
        self.config.runner.pcmk.load_state(stdout=self.fixture_status_xml(1, 1))
        self.config.runner.pcmk.resource_refresh(
            stdout=self.stdout, stderr=self.stderr
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_refresh(env.cmd_runner())
        self.assert_output(real_output)

    def test_threshold_exceeded(self):
        self.config.runner.pcmk.load_state(
            stdout=self.fixture_status_xml(1000, 1000)
        )
        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.resource_refresh(env.cmd_runner()),
            [
                fixture.error(
                    report_codes.RESOURCE_REFRESH_TOO_TIME_CONSUMING,
                    force_code=report_codes.FORCE,
                    threshold=100,
                )
            ],
            expected_in_processor=False,
        )

    def test_threshold_exceeded_forced(self):
        self.config.runner.pcmk.resource_refresh(
            stdout=self.stdout, stderr=self.stderr
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_refresh(env.cmd_runner(), force=True)
        self.assert_output(real_output)

    def test_resource(self):
        self.config.runner.pcmk.resource_refresh(
            stdout=self.stdout, stderr=self.stderr, resource=self.resource
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_refresh(
            env.cmd_runner(), resource=self.resource
        )
        self.assert_output(real_output)

    def test_resource_strict(self):
        self.config.runner.pcmk.resource_refresh(
            stdout=self.stdout,
            stderr=self.stderr,
            resource=self.resource,
            strict=True,
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_refresh(
            env.cmd_runner(), resource=self.resource, strict=True
        )
        self.assert_output(real_output)

    def test_node(self):
        self.config.runner.pcmk.resource_refresh(
            stdout=self.stdout, stderr=self.stderr, node=self.node
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_refresh(env.cmd_runner(), node=self.node)
        self.assert_output(real_output)

    def test_all_options(self):
        self.config.runner.pcmk.resource_refresh(
            stdout=self.stdout,
            stderr=self.stderr,
            resource=self.resource,
            node=self.node,
            strict=True,
        )

        env = self.env_assist.get_env()
        real_output = lib.resource_refresh(
            env.cmd_runner(),
            resource=self.resource,
            node=self.node,
            strict=True,
        )
        self.assert_output(real_output)

    def test_error_state(self):
        self.config.runner.pcmk.load_state(
            stdout=self.stdout, stderr=self.stderr, returncode=1
        )
        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.resource_refresh(env.cmd_runner()),
            [
                fixture.error(
                    report_codes.CRM_MON_ERROR,
                    reason=(self.stderr + "\n" + self.stdout),
                )
            ],
            expected_in_processor=False,
        )

    def test_error_refresh(self):
        self.config.runner.pcmk.load_state(stdout=self.fixture_status_xml(1, 1))
        self.config.runner.pcmk.resource_refresh(
            stdout=self.stdout, stderr=self.stderr, returncode=1
        )

        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.resource_refresh(env.cmd_runner()),
            [
                fixture.error(
                    report_codes.RESOURCE_REFRESH_ERROR,
                    reason=(self.stderr + "\n" + self.stdout),
                    resource=None,
                    node=None,
                )
            ],
            expected_in_processor=False,
        )


class ResourcesWaitingTest(TestCase):
    # pylint: disable=no-self-use
    def test_wait_success(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        self.assertEqual(None, lib.wait_for_idle(mock_runner, 0))

        mock_runner.run.assert_called_once_with(
            [settings.crm_resource_exec, "--wait"]
        )

    def test_wait_timeout_success(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 0
        timeout = 10
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        self.assertEqual(None, lib.wait_for_idle(mock_runner, timeout))

        mock_runner.run.assert_called_once_with(
            [
                settings.crm_resource_exec,
                "--wait",
                "--timeout={0}".format(timeout),
            ]
        )

    def test_wait_error(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        assert_raise_library_error(
            lambda: lib.wait_for_idle(mock_runner, 0),
            (
                fixture.error(
                    report_codes.WAIT_FOR_IDLE_ERROR,
                    reason=expected_stderr + "\n" + expected_stdout,
                )
            ),
        )

        mock_runner.run.assert_called_once_with(
            [settings.crm_resource_exec, "--wait"]
        )

    def test_wait_error_timeout(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 124
        mock_runner = get_runner(
            expected_stdout, expected_stderr, expected_retval
        )

        assert_raise_library_error(
            lambda: lib.wait_for_idle(mock_runner, 0),
            (
                fixture.error(
                    report_codes.WAIT_FOR_IDLE_TIMED_OUT,
                    reason=expected_stderr + "\n" + expected_stdout,
                )
            ),
        )

        mock_runner.run.assert_called_once_with(
            [settings.crm_resource_exec, "--wait"]
        )


class IsInPcmkToolHelp(TestCase):
    # pylint: disable=protected-access
    def test_all_in_stderr(self):
        mock_runner = get_runner("", "ABCDE", 0)
        self.assertTrue(
            lib._is_in_pcmk_tool_help(mock_runner, "", ["A", "C", "E"])
        )

    def test_all_in_stdout(self):
        mock_runner = get_runner("ABCDE", "", 0)
        self.assertTrue(
            lib._is_in_pcmk_tool_help(mock_runner, "", ["A", "C", "E"])
        )

    def test_some_in_stderr_all_in_stdout(self):
        mock_runner = get_runner("ABCDE", "ABC", 0)
        self.assertTrue(
            lib._is_in_pcmk_tool_help(mock_runner, "", ["A", "C", "E"])
        )

    def test_some_in_stderr_some_in_stdout(self):
        mock_runner = get_runner("CDE", "ABC", 0)
        self.assertFalse(
            lib._is_in_pcmk_tool_help(mock_runner, "", ["A", "C", "E"])
        )


class GetRulesInEffectStatus(TestCase):
    def test_success(self):
        test_data = [
            (1, CibRuleInEffectStatus.UNKNOWN),
            (110, CibRuleInEffectStatus.EXPIRED),
            (0, CibRuleInEffectStatus.IN_EFFECT),
            (111, CibRuleInEffectStatus.NOT_YET_IN_EFFECT),
        ]
        for return_code, response in test_data:
            with self.subTest(return_code=return_code, response=response):
                runner = mock.MagicMock(spec_set=CommandRunner)
                runner.run.return_value = ("", "", return_code)
                self.assertEqual(
                    lib.get_rule_in_effect_status(runner, "mock cib", "ruleid"),
                    response,
                )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class GetResourceDigests(TestCase):
    DIGESTS = {
        "all": "0" * 31 + "1",
        "nonprivate": "0" * 31 + "2",
        "nonreloadable": "0" * 31 + "3",
    }
    CALL_ARGS = [
        settings.crm_resource_exec,
        "--digests",
        "--resource",
        "resource-id",
        "--node",
        "node1",
        "--output-as",
        "xml",
        "opt_name1=opt_value1",
        "opt_name2=opt_value2",
        "CRM_meta_interval=30000",
        "CRM_meta_timeout=10000",
    ]
    CRM_ATTRS = {"interval": "30000", "timeout": "10000"}
    RESOURCE_OPTIONS = {"opt_name1": "opt_value1", "opt_name2": "opt_value2"}
    FIXTURE_PACEMAKER_ERROR_XML = """
        <pacemaker-result api-version="2.9" request="crm_resource">
          <status code="102" message="Not connected">
            <errors>
              <error>crm_resource: Could not connect to the CIB: Transport endpoint is not connected
        Error performing operation: Not connected</error>
            </errors>
          </status>
        </pacemaker-result>

    """
    FIXTURE_PACEMAKER_ERROR = (
        "Not connected\ncrm_resource: Could not connect to the CIB: Transport "
        "endpoint is not connected\n        Error performing operation: Not "
        "connected"
    )

    def assert_command_failure(
        self, stdout="", returncode=0, report_output=None
    ):
        if report_output is None:
            report_output = stdout
        runner = get_runner(stdout=stdout, returncode=returncode)
        assert_raise_library_error(
            lambda: lib.get_resource_digests(
                runner,
                "resource-id",
                "node1",
                self.RESOURCE_OPTIONS,
                self.CRM_ATTRS,
            ),
            (
                fixture.error(
                    report_codes.UNABLE_TO_GET_RESOURCE_OPERATION_DIGESTS,
                    output=report_output,
                )
            ),
        )
        runner.run.assert_called_once_with(self.CALL_ARGS)

    def assert_command_success(
        self,
        digest_types=("all",),
        resource_options=None,
        crm_attrs=None,
        call_args=None,
    ):
        if resource_options is None:
            resource_options = self.RESOURCE_OPTIONS
        if crm_attrs is None:
            crm_attrs = self.CRM_ATTRS
        if call_args is None:
            call_args = self.CALL_ARGS
        runner = get_runner(stdout=self.fixture_digests_xml(digest_types))
        self.assertEqual(
            lib.get_resource_digests(
                runner,
                "resource-id",
                "node1",
                resource_options,
                crm_meta_attributes=crm_attrs,
            ),
            self.fixture_result_dict(digest_types),
        )
        runner.run.assert_called_once_with(call_args)

    def fixture_result_dict(self, digest_types=()):
        result_dict = {k: None for k in self.DIGESTS}
        for digest_type in digest_types:
            result_dict[digest_type] = self.DIGESTS[digest_type]
        return result_dict

    def fixture_digests_xml(self, digest_types=()):
        return """
            <pacemaker-result api-version="2.9" request="crm_resource">
                <digests resource="resource-id" node="node1" task="monitor" interval="0ms">
                    {digests}
                </digests>
                <status code="0" message="OK"/>
            </pacemaker-result>

        """.format(
            digests="\n".join(
                f"""
                <digest type="{digest_type}" hash="{self.DIGESTS[digest_type]}">
                    <parameters/>
                </digest>
                """
                for digest_type in digest_types
            )
        ).strip()

    def test_success(self):
        digest_types = list(self.DIGESTS.keys())
        test_list = [digest_types[0:1], digest_types[0:2], digest_types]
        for tested_digest_types in test_list:
            with self.subTest(tested_digest_types=tested_digest_types):
                self.assert_command_success(digest_types=tested_digest_types)

    def test_success_no_crm_attrs(self):
        self.assert_command_success(crm_attrs={}, call_args=self.CALL_ARGS[:-2])

    def test_success_empty_resource_options(self):
        self.assert_command_success(
            resource_options={}, crm_attrs={}, call_args=self.CALL_ARGS[:-4]
        )

    def test_invalid_xml(self):
        self.assert_command_failure(stdout="invalid_xml")

    def test_not_valid_with_schema(self):
        self.assert_command_failure(stdout="<xml/>")

    def test_pacemaker_error(self):
        self.assert_command_failure(
            stdout=self.FIXTURE_PACEMAKER_ERROR_XML,
            returncode=101,
            report_output=self.FIXTURE_PACEMAKER_ERROR,
        )

    def test_no_digest_found(self):
        self.assert_command_failure(stdout=self.fixture_digests_xml())


class HandleInstanceAttributesValidateViaPcmkTest(TestCase):
    # pylint: disable=protected-access

    def test_valid(self):
        runner = get_runner(
            stdout="""
            <api>
              <result>
                <output source="stdout">
                Some text which will be ignored

                Still ignored
                </output>
              </result>
            </api>
            """
        )
        base_cmd = ["some", "command"]
        (
            is_valid,
            reason,
        ) = lib._handle_instance_attributes_validation_via_pcmk(
            runner,
            base_cmd,
            "result/output",
            {"attr1": "val1", "attr2": "val2"},
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "")
        runner.run.assert_called_once_with(
            base_cmd + ["--option", "attr1=val1", "--option", "attr2=val2"]
        )

    def test_invalid_xml_output(self):
        runner = get_runner(stdout="not xml")
        base_cmd = ["some", "command"]
        (
            is_valid,
            reason,
        ) = lib._handle_instance_attributes_validation_via_pcmk(
            runner,
            base_cmd,
            "result/output",
            {"attr1": "val1", "attr2": "val2"},
        )
        self.assertIsNone(is_valid)
        self.assertEqual(
            reason,
            "Start tag expected, '<' not found, line 1, column 1 (<string>, line 1)",
        )
        runner.run.assert_called_once_with(
            base_cmd + ["--option", "attr1=val1", "--option", "attr2=val2"]
        )

    def test_valid_empty_result(self):
        runner = get_runner(
            stdout="""
            <api>
              <result>
                <output source="stdout">this is ignored</output>
              </result>
            </api>
            """
        )
        base_cmd = ["some", "command"]
        (
            is_valid,
            reason,
        ) = lib._handle_instance_attributes_validation_via_pcmk(
            runner,
            base_cmd,
            "result/output",
            {"attr1": "val1", "attr2": "val2"},
        )
        self.assertTrue(is_valid)
        self.assertEqual(reason, "")
        runner.run.assert_called_once_with(
            base_cmd + ["--option", "attr1=val1", "--option", "attr2=val2"]
        )

    def test_failure_empty_result(self):
        runner = get_runner(
            stdout="""
            <api>
              <result>
                <output source="stdout">this is ignored</output>
              </result>
            </api>
            """,
            returncode=1,
        )
        base_cmd = ["some", "command"]
        (
            is_valid,
            reason,
        ) = lib._handle_instance_attributes_validation_via_pcmk(
            runner,
            base_cmd,
            "result/output",
            {"attr1": "val1", "attr2": "val2"},
        )
        self.assertFalse(is_valid)
        self.assertEqual(reason, "")
        runner.run.assert_called_once_with(
            base_cmd + ["--option", "attr1=val1", "--option", "attr2=val2"]
        )

    def test_failure(self):
        runner = get_runner(
            stdout="""
            <api>
              <result>
                <output source="stderr">first line</output>
                <output source="stdout">
                Some text which will be ignored

                Still ignored
                </output>
                <output source="stderr">
                Important output
                and another line
                </output>
              </result>
            </api>
            """,
            returncode=1,
        )
        base_cmd = ["some", "command"]
        (
            is_valid,
            reason,
        ) = lib._handle_instance_attributes_validation_via_pcmk(
            runner,
            base_cmd,
            "result/output",
            {"attr1": "val1", "attr2": "val2"},
        )
        self.assertFalse(is_valid)
        self.assertEqual(
            reason,
            "first line\nImportant output\nand another line",
        )
        runner.run.assert_called_once_with(
            base_cmd + ["--option", "attr1=val1", "--option", "attr2=val2"]
        )

    def test_valid_with_result(self):
        runner = get_runner(
            stdout="""
            <api>
              <result>
                <output source="stderr">first line</output>
                <output source="stdout">
                Some text which will be ignored

                Still ignored
                </output>
                <output source="stderr">
                Important output
                and another line
                </output>
              </result>
            </api>
            """
        )
        base_cmd = ["some", "command"]
        (
            is_valid,
            reason,
        ) = lib._handle_instance_attributes_validation_via_pcmk(
            runner,
            base_cmd,
            "result/output",
            {"attr1": "val1", "attr2": "val2"},
        )
        self.assertTrue(is_valid)
        self.assertEqual(
            reason,
            "first line\nImportant output\nand another line",
        )
        runner.run.assert_called_once_with(
            base_cmd + ["--option", "attr1=val1", "--option", "attr2=val2"]
        )


class ValidateResourceInstanceAttributesViaPcmkTest(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.runner = mock.Mock()
        self.attrs = dict(attra="val1", attrb="val2")
        patcher = mock.patch(
            "pcs.lib.pacemaker.live._handle_instance_attributes_validation_via_pcmk"
        )
        self.mock_handler = patcher.start()
        self.addCleanup(patcher.stop)
        self.ret_val = "ret val"
        self.mock_handler.return_value = self.ret_val

    def test_with_provider(self):
        agent = ResourceAgentName(
            standard="ocf", provider="pacemaker", type="Dummy"
        )
        self.assertEqual(
            lib._validate_resource_instance_attributes_via_pcmk(
                self.runner, agent, self.attrs
            ),
            self.ret_val,
        )
        self.mock_handler.assert_called_once_with(
            self.runner,
            [
                settings.crm_resource_exec,
                "--validate",
                "--output-as",
                "xml",
                "--class",
                "ocf",
                "--agent",
                "Dummy",
                "--provider",
                "pacemaker",
            ],
            "./resource-agent-action/command/output",
            self.attrs,
        )

    def test_without_provider(self):
        agent = ResourceAgentName(
            standard="standard", provider=None, type="Agent"
        )
        self.assertEqual(
            lib._validate_resource_instance_attributes_via_pcmk(
                self.runner, agent, self.attrs
            ),
            self.ret_val,
        )
        self.mock_handler.assert_called_once_with(
            self.runner,
            [
                settings.crm_resource_exec,
                "--validate",
                "--output-as",
                "xml",
                "--class",
                "standard",
                "--agent",
                "Agent",
            ],
            "./resource-agent-action/command/output",
            self.attrs,
        )


class ValidateStonithInstanceAttributesViaPcmkTest(TestCase):
    # pylint: disable=protected-access

    def setUp(self):
        self.runner = mock.Mock()
        self.attrs = dict(attra="val1", attrb="val2")
        patcher = mock.patch(
            "pcs.lib.pacemaker.live._handle_instance_attributes_validation_via_pcmk"
        )
        self.mock_handler = patcher.start()
        self.addCleanup(patcher.stop)
        self.ret_val = "ret val"
        self.mock_handler.return_value = self.ret_val

    def test_success(self):
        agent = ResourceAgentName(
            standard="stonith", provider=None, type="Agent"
        )
        self.assertEqual(
            lib._validate_stonith_instance_attributes_via_pcmk(
                self.runner, agent, self.attrs
            ),
            self.ret_val,
        )
        self.mock_handler.assert_called_once_with(
            self.runner,
            [
                settings.stonith_admin_exec,
                "--validate",
                "--output-as",
                "xml",
                "--agent",
                "Agent",
            ],
            "./validate/command/output",
            self.attrs,
        )

from lxml import etree
import os.path
from unittest import mock, TestCase

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
    start_tag_error_text,
)
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.xml import XmlManipulation

from pcs import settings
from pcs.common import report_codes
from pcs.common.tools import Version
import pcs.lib.pacemaker.live as lib
from pcs.lib.errors import ReportItemSeverity as Severity
from pcs.lib.external import CommandRunner

def get_runner(stdout="", stderr="", returncode=0, env_vars=None):
    runner = mock.MagicMock(spec_set=CommandRunner)
    runner.run.return_value = (stdout, stderr, returncode)
    runner.env_vars = env_vars if env_vars else {}
    return runner


class LibraryPacemakerTest(TestCase):
    def path(self, name):
        return os.path.join(settings.pacemaker_binaries, name)

    def crm_mon_cmd(self):
        return [self.path("crm_mon"), "--one-shot", "--as-xml", "--inactive"]

class LibraryPacemakerNodeStatusTest(LibraryPacemakerTest):
    def setUp(self):
        self.status = XmlManipulation.from_file(rc("crm_mon.minimal.xml"))

    def fixture_get_node_status(self, node_name, node_id):
        return {
            "id": node_id,
            "name": node_name,
            "type": "member",
            "online": True,
            "standby": False,
            "standby_onfail": False,
            "maintenance": True,
            "pending": True,
            "unclean": False,
            "shutdown": False,
            "expected_up": True,
            "is_dc": True,
            "resources_running": 7,
        }

    def fixture_add_node_status(self, node_attrs):
        xml_attrs = []
        for name, value in node_attrs.items():
            if value is True:
                value = "true"
            elif value is False:
                value = "false"
            xml_attrs.append('{0}="{1}"'.format(name, value))
        node_xml = "<node {0}/>".format(" ".join(xml_attrs))
        self.status.append_to_first_tag_name("nodes", node_xml)

class GetClusterStatusXmlTest(LibraryPacemakerTest):
    def test_success(self):
        expected_stdout = "<xml />"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        real_xml = lib.get_cluster_status_xml(mock_runner)

        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())
        self.assertEqual(expected_stdout, real_xml)

    def test_error(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.get_cluster_status_xml(mock_runner),
            (
                Severity.ERROR,
                report_codes.CRM_MON_ERROR,
                {
                    "reason": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())

class GetCibXmlTest(LibraryPacemakerTest):
    def test_success(self):
        expected_stdout = "<xml />"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        real_xml = lib.get_cib_xml(mock_runner)

        mock_runner.run.assert_called_once_with(
            [self.path("cibadmin"), "--local", "--query"]
        )
        self.assertEqual(expected_stdout, real_xml)

    def test_error(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.get_cib_xml(mock_runner),
            (
                Severity.ERROR,
                report_codes.CIB_LOAD_ERROR,
                {
                    "reason": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(
            [self.path("cibadmin"), "--local", "--query"]
        )

    def test_success_scope(self):
        expected_stdout = "<xml />"
        expected_stderr = ""
        expected_retval = 0
        scope = "test_scope"
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        real_xml = lib.get_cib_xml(mock_runner, scope)

        mock_runner.run.assert_called_once_with(
            [
                self.path("cibadmin"),
                "--local", "--query", "--scope={0}".format(scope)
            ]
        )
        self.assertEqual(expected_stdout, real_xml)

    def test_scope_error(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 6
        scope = "test_scope"
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.get_cib_xml(mock_runner, scope=scope),
            (
                Severity.ERROR,
                report_codes.CIB_LOAD_ERROR_SCOPE_MISSING,
                {
                    "scope": scope,
                    "reason": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(
            [
                self.path("cibadmin"),
                "--local", "--query", "--scope={0}".format(scope)
            ]
        )

class GetCibTest(LibraryPacemakerTest):
    def test_success(self):
        xml = "<xml />"
        assert_xml_equal(xml, str(XmlManipulation((lib.get_cib(xml)))))

    def test_invalid_xml(self):
        xml = "<invalid><xml />"
        assert_raise_library_error(
            lambda: lib.get_cib(xml),
            (
                Severity.ERROR,
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                {
                }
            )
        )

class Verify(LibraryPacemakerTest):
    def test_run_on_live_cib(self):
        runner = get_runner()
        self.assertEqual(
            lib.verify(runner),
            runner.run.return_value
        )
        runner.run.assert_called_once_with(
            [self.path("crm_verify"), "--live-check"],
        )

    def test_run_on_mocked_cib(self):
        fake_tmp_file = "/fake/tmp/file"
        runner = get_runner(env_vars={"CIB_file": fake_tmp_file})

        self.assertEqual(lib.verify(runner), runner.run.return_value)
        runner.run.assert_called_once_with(
            [self.path("crm_verify"), "--xml-file", fake_tmp_file],
        )

    def test_run_verbose(self):
        runner = get_runner()
        self.assertEqual(
            lib.verify(runner, verbose=True),
            runner.run.return_value
        )
        runner.run.assert_called_once_with(
            [self.path("crm_verify"), "-V", "--live-check"],
        )


class ReplaceCibConfigurationTest(LibraryPacemakerTest):
    def test_success(self):
        xml = "<xml/>"
        expected_stdout = "expected output"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        lib.replace_cib_configuration(
            mock_runner,
            XmlManipulation.from_str(xml).tree
        )

        mock_runner.run.assert_called_once_with(
            [
                self.path("cibadmin"), "--replace", "--verbose", "--xml-pipe",
                "--scope", "configuration"
            ],
            stdin_string=xml
        )

    def test_error(self):
        xml = "<xml/>"
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.replace_cib_configuration(
                    mock_runner,
                    XmlManipulation.from_str(xml).tree
                )
            ,
            (
                Severity.ERROR,
                report_codes.CIB_PUSH_ERROR,
                {
                    "reason": expected_stderr,
                    "pushed_cib": expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(
            [
                self.path("cibadmin"), "--replace", "--verbose", "--xml-pipe",
                "--scope", "configuration"
            ],
            stdin_string=xml
        )

class UpgradeCibTest(TestCase):
    def test_success(self):
        mock_runner = get_runner("", "", 0)
        lib._upgrade_cib(mock_runner)
        mock_runner.run.assert_called_once_with(
            ["/usr/sbin/cibadmin", "--upgrade", "--force"]
        )

    def test_error(self):
        error = "Call cib_upgrade failed (-62): Timer expired"
        mock_runner = get_runner("", error, 62)
        assert_raise_library_error(
            lambda: lib._upgrade_cib(mock_runner),
            (
                Severity.ERROR,
                report_codes.CIB_UPGRADE_FAILED,
                {
                    "reason": error,
                }
            )
        )
        mock_runner.run.assert_called_once_with(
            ["/usr/sbin/cibadmin", "--upgrade", "--force"]
        )

    def test_already_at_latest_schema(self):
        error = ("Call cib_upgrade failed (-211): Schema is already "
            "the latest available")
        mock_runner = get_runner("", error, 211)
        lib._upgrade_cib(mock_runner)
        mock_runner.run.assert_called_once_with(
            ["/usr/sbin/cibadmin", "--upgrade", "--force"]
        )

@mock.patch("pcs.lib.pacemaker.live.get_cib_xml")
@mock.patch("pcs.lib.pacemaker.live._upgrade_cib")
class EnsureCibVersionTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.cib = etree.XML('<cib validate-with="pacemaker-2.3.4"/>')

    def test_same_version(self, mock_upgrade, mock_get_cib):
        self.assertTrue(
            lib.ensure_cib_version(
                self.mock_runner, self.cib, Version(2, 3, 4)
            ) is None
        )
        mock_upgrade.assert_not_called()
        mock_get_cib.assert_not_called()

    def test_higher_version(self, mock_upgrade, mock_get_cib):
        self.assertTrue(
            lib.ensure_cib_version(
                self.mock_runner, self.cib, Version(2, 3, 3)
            ) is None
        )
        mock_upgrade.assert_not_called()
        mock_get_cib.assert_not_called()

    def test_upgraded_same_version(self, mock_upgrade, mock_get_cib):
        upgraded_cib = '<cib validate-with="pacemaker-2.3.5"/>'
        mock_get_cib.return_value = upgraded_cib
        assert_xml_equal(
            upgraded_cib,
            etree.tostring(
                lib.ensure_cib_version(
                    self.mock_runner, self.cib, Version(2, 3, 5)
                )
            ).decode()
        )
        mock_upgrade.assert_called_once_with(self.mock_runner)
        mock_get_cib.assert_called_once_with(self.mock_runner)

    def test_upgraded_higher_version(self, mock_upgrade, mock_get_cib):
        upgraded_cib = '<cib validate-with="pacemaker-2.3.6"/>'
        mock_get_cib.return_value = upgraded_cib
        assert_xml_equal(
            upgraded_cib,
            etree.tostring(
                lib.ensure_cib_version(
                    self.mock_runner, self.cib, Version(2, 3, 5)
                )
            ).decode()
        )
        mock_upgrade.assert_called_once_with(self.mock_runner)
        mock_get_cib.assert_called_once_with(self.mock_runner)

    def test_upgraded_lower_version(self, mock_upgrade, mock_get_cib):
        mock_get_cib.return_value = etree.tostring(self.cib).decode()
        assert_raise_library_error(
            lambda: lib.ensure_cib_version(
                self.mock_runner, self.cib, Version(2, 3, 5)
            ),
            (
                Severity.ERROR,
                report_codes.CIB_UPGRADE_FAILED_TO_MINIMAL_REQUIRED_VERSION,
                {
                    "required_version": "2.3.5",
                    "current_version": "2.3.4"
                }
            )
        )
        mock_upgrade.assert_called_once_with(self.mock_runner)
        mock_get_cib.assert_called_once_with(self.mock_runner)

    def test_cib_parse_error(self, mock_upgrade, mock_get_cib):
        mock_get_cib.return_value = "not xml"
        assert_raise_library_error(
            lambda: lib.ensure_cib_version(
                self.mock_runner, self.cib, Version(2, 3, 5)
            ),
            (
                Severity.ERROR,
                report_codes.CIB_UPGRADE_FAILED,
                {
                    "reason":
                        start_tag_error_text(),
                }
            )
        )
        mock_upgrade.assert_called_once_with(self.mock_runner)
        mock_get_cib.assert_called_once_with(self.mock_runner)

class GetLocalNodeStatusTest(LibraryPacemakerNodeStatusTest):
    def test_offline(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertEqual(
            {"offline": True},
            lib.get_local_node_status(mock_runner)
        )
        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())

    def test_invalid_status(self):
        expected_stdout = "invalid xml"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.get_local_node_status(mock_runner),
            (
                Severity.ERROR,
                report_codes.BAD_CLUSTER_STATE_FORMAT,
                {}
            )
        )
        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())

    def test_success(self):
        node_id = "id_1"
        node_name = "name_1"
        node_status = self.fixture_get_node_status(node_name, node_id)
        expected_status = dict(node_status, offline=False)
        self.fixture_add_node_status(
            self.fixture_get_node_status("name_2", "id_2")
        )
        self.fixture_add_node_status(node_status)
        self.fixture_add_node_status(
            self.fixture_get_node_status("name_3", "id_3")
        )

        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [
            mock.call(self.crm_mon_cmd()),
            mock.call([self.path("crm_node"), "--cluster-id"]),
            mock.call(
                [self.path("crm_node"), "--name-for-id={0}".format(node_id)]
            ),
        ]
        return_value_list = [
            (str(self.status), "", 0),
            (node_id, "", 0),
            (node_name, "", 0)
        ]
        mock_runner.run.side_effect = return_value_list

        real_status = lib.get_local_node_status(mock_runner)

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)
        self.assertEqual(expected_status, real_status)

    def test_node_not_in_status(self):
        node_id = "id_1"
        node_name = "name_1"
        node_name_bad = "name_X"
        node_status = self.fixture_get_node_status(node_name, node_id)
        self.fixture_add_node_status(node_status)

        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [
            mock.call(self.crm_mon_cmd()),
            mock.call([self.path("crm_node"), "--cluster-id"]),
            mock.call(
                [self.path("crm_node"), "--name-for-id={0}".format(node_id)]
            ),
        ]
        return_value_list = [
            (str(self.status), "", 0),
            (node_id, "", 0),
            (node_name_bad, "", 0)
        ]
        mock_runner.run.side_effect = return_value_list

        assert_raise_library_error(
            lambda: lib.get_local_node_status(mock_runner),
            (
                Severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {"node": node_name_bad}
            )
        )

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)

    def test_error_1(self):
        node_id = "id_1"
        node_name = "name_1"
        node_status = self.fixture_get_node_status(node_name, node_id)
        self.fixture_add_node_status(node_status)

        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [
            mock.call(self.crm_mon_cmd()),
            mock.call([self.path("crm_node"), "--cluster-id"]),
        ]
        return_value_list = [
            (str(self.status), "", 0),
            ("", "some error", 1),
        ]
        mock_runner.run.side_effect = return_value_list

        assert_raise_library_error(
            lambda: lib.get_local_node_status(mock_runner),
            (
                Severity.ERROR,
                report_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
                {"reason": "node id not found"}
            )
        )

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)

    def test_error_2(self):
        node_id = "id_1"
        node_name = "name_1"
        node_status = self.fixture_get_node_status(node_name, node_id)
        self.fixture_add_node_status(node_status)

        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [
            mock.call(self.crm_mon_cmd()),
            mock.call([self.path("crm_node"), "--cluster-id"]),
            mock.call(
                [self.path("crm_node"), "--name-for-id={0}".format(node_id)]
            ),
        ]
        return_value_list = [
            (str(self.status), "", 0),
            (node_id, "", 0),
            ("", "some error", 1),
        ]
        mock_runner.run.side_effect = return_value_list

        assert_raise_library_error(
            lambda: lib.get_local_node_status(mock_runner),
            (
                Severity.ERROR,
                report_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
                {"reason": "node name not found"}
            )
        )

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)

    def test_error_3(self):
        node_id = "id_1"
        node_name = "name_1"
        node_status = self.fixture_get_node_status(node_name, node_id)
        self.fixture_add_node_status(node_status)

        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [
            mock.call(self.crm_mon_cmd()),
            mock.call([self.path("crm_node"), "--cluster-id"]),
            mock.call(
                [self.path("crm_node"), "--name-for-id={0}".format(node_id)]
            ),
        ]
        return_value_list = [
            (str(self.status), "", 0),
            (node_id, "", 0),
            ("(null)", "", 0),
        ]
        mock_runner.run.side_effect = return_value_list

        assert_raise_library_error(
            lambda: lib.get_local_node_status(mock_runner),
            (
                Severity.ERROR,
                report_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
                {"reason": "node name is null"}
            )
        )

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)

class RemoveNode(LibraryPacemakerTest):
    def test_success(self):
        mock_runner = get_runner("", "", 0)
        lib.remove_node(
            mock_runner,
            "NODE_NAME"
        )
        mock_runner.run.assert_called_once_with([
            self.path("crm_node"),
            "--force",
            "--remove",
            "NODE_NAME",
        ])

    def test_error(self):
        expected_stderr = "expected stderr"
        mock_runner = get_runner("", expected_stderr, 1)
        assert_raise_library_error(
            lambda: lib.remove_node(mock_runner, "NODE_NAME") ,
            (
                Severity.ERROR,
                report_codes.NODE_REMOVE_IN_PACEMAKER_FAILED,
                {
                    "node_name": "NODE_NAME",
                    "reason": expected_stderr,
                }
            )
        )


class ResourceCleanupTest(TestCase):
    def setUp(self):
        self.stdout = "expected output"
        self.stderr = "expected stderr"
        self.resource = "my_resource"
        self.node = "my_node"
        self.env_assist, self.config = get_env_tools(test_case=self)

    def assert_output(self, real_output):
        self.assertEqual(
            self.stdout + "\n" + self.stderr,
            real_output
        )

    def test_basic(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout,
            stderr=self.stderr
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_cleanup(env.cmd_runner())
        self.assert_output(real_output)

    def test_resource(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout,
            stderr=self.stderr,
            resource=self.resource
        )
        env = self.env_assist.get_env()
        real_output = lib.resource_cleanup(
            env.cmd_runner(), resource=self.resource
        )
        self.assert_output(real_output)

    def test_node(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout,
            stderr=self.stderr,
            node=self.node
        )

        env = self.env_assist.get_env()
        real_output = lib.resource_cleanup(
            env.cmd_runner(), node=self.node
        )
        self.assert_output(real_output)

    def test_all_options(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout,
            stderr=self.stderr,
            resource=self.resource,
            node=self.node
        )

        env = self.env_assist.get_env()
        real_output = lib.resource_cleanup(
            env.cmd_runner(), resource=self.resource, node=self.node
        )
        self.assert_output(real_output)

    def test_error_cleanup(self):
        self.config.runner.pcmk.resource_cleanup(
            stdout=self.stdout,
            stderr=self.stderr,
            returncode=1
        )

        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: lib.resource_cleanup(env.cmd_runner()),
            [
                fixture.error(
                    report_codes.RESOURCE_CLEANUP_ERROR,
                    force_code=None,
                    reason=(self.stderr + "\n" + self.stdout)
                )
            ],
            expected_in_processor=False
        )


class ResourceRefreshTest(LibraryPacemakerTest):
    def fixture_status_xml(self, nodes, resources):
        xml_man = XmlManipulation.from_file(rc("crm_mon.minimal.xml"))
        doc = xml_man.tree.getroottree()
        doc.find("/summary/nodes_configured").set("number", str(nodes))
        doc.find("/summary/resources_configured").set("number", str(resources))
        return str(XmlManipulation(doc))

    def test_basic(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [
            mock.call(self.crm_mon_cmd()),
            mock.call([self.path("crm_resource"), "--refresh"]),
        ]
        return_value_list = [
            (self.fixture_status_xml(1, 1), "", 0),
            (expected_stdout, expected_stderr, 0),
        ]
        mock_runner.run.side_effect = return_value_list

        real_output = lib.resource_refresh(mock_runner)

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_threshold_exceeded(self):
        mock_runner = get_runner(
            self.fixture_status_xml(1000, 1000),
            "",
            0
        )

        assert_raise_library_error(
            lambda: lib.resource_refresh(mock_runner),
            (
                Severity.ERROR,
                report_codes.RESOURCE_REFRESH_TOO_TIME_CONSUMING,
                {"threshold": 100},
                report_codes.FORCE_LOAD_THRESHOLD
            )
        )

        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())

    def test_threshold_exceeded_forced(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = get_runner(expected_stdout, expected_stderr, 0)

        real_output = lib.resource_refresh(mock_runner, force=True)

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--refresh"]
        )
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_resource(self):
        resource = "test_resource"
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = get_runner(expected_stdout, expected_stderr, 0)

        real_output = lib.resource_refresh(mock_runner, resource=resource)

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--refresh", "--resource", resource]
        )
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_node(self):
        node = "test_node"
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = get_runner(expected_stdout, expected_stderr, 0)

        real_output = lib.resource_refresh(mock_runner, node=node)

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--refresh", "--node", node]
        )
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_full(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [
            mock.call(self.crm_mon_cmd()),
            mock.call([self.path("crm_resource"), "--refresh", "--force"]),
        ]
        return_value_list = [
            (self.fixture_status_xml(1, 1), "", 0),
            (expected_stdout, expected_stderr, 0),
        ]
        mock_runner.run.side_effect = return_value_list

        real_output = lib.resource_refresh(mock_runner, full=True)

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_all_options(self):
        node = "test_node"
        resource = "test_resource"
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = get_runner(expected_stdout, expected_stderr, 0)

        real_output = lib.resource_refresh(
            mock_runner, resource=resource, node=node, full=True
        )

        mock_runner.run.assert_called_once_with(
            [
                self.path("crm_resource"),
                "--refresh", "--resource", resource, "--node", node, "--force"
            ]
        )
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_error_state(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.resource_refresh(mock_runner),
            (
                Severity.ERROR,
                report_codes.CRM_MON_ERROR,
                {
                    "reason": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())

    def test_error_refresh(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [
            mock.call(self.crm_mon_cmd()),
            mock.call([self.path("crm_resource"), "--refresh"]),
        ]
        return_value_list = [
            (self.fixture_status_xml(1, 1), "", 0),
            (expected_stdout, expected_stderr, expected_retval),
        ]
        mock_runner.run.side_effect = return_value_list

        assert_raise_library_error(
            lambda: lib.resource_refresh(mock_runner),
            (
                Severity.ERROR,
                report_codes.RESOURCE_REFRESH_ERROR,
                {
                    "reason": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)


class ResourcesWaitingTest(LibraryPacemakerTest):
    def test_has_support(self):
        expected_stdout = ""
        expected_stderr = "something --wait something else"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertTrue(
            lib.has_wait_for_idle_support(mock_runner)
        )
        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "-?"]
        )

    def test_has_support_stdout(self):
        expected_stdout = "something --wait something else"
        expected_stderr = ""
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertTrue(
            lib.has_wait_for_idle_support(mock_runner)
        )
        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "-?"]
        )

    def test_doesnt_have_support(self):
        expected_stdout = "something something else"
        expected_stderr = "something something else"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertFalse(
            lib.has_wait_for_idle_support(mock_runner)
        )
        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "-?"]
        )

    @mock.patch(
        "pcs.lib.pacemaker.live.has_wait_for_idle_support",
        autospec=True
    )
    def test_ensure_support_success(self, mock_obj):
        mock_obj.return_value = True
        self.assertEqual(None, lib.ensure_wait_for_idle_support(mock.Mock()))

    @mock.patch(
        "pcs.lib.pacemaker.live.has_wait_for_idle_support",
        autospec=True
    )
    def test_ensure_support_error(self, mock_obj):
        mock_obj.return_value = False
        assert_raise_library_error(
            lambda: lib.ensure_wait_for_idle_support(mock.Mock()),
            (
                Severity.ERROR,
                report_codes.WAIT_FOR_IDLE_NOT_SUPPORTED,
                {}
            )
        )

    def test_wait_success(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 0
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertEqual(None, lib.wait_for_idle(mock_runner))

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--wait"]
        )

    def test_wait_timeout_success(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 0
        timeout = 10
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertEqual(None, lib.wait_for_idle(mock_runner, timeout))

        mock_runner.run.assert_called_once_with(
            [
                self.path("crm_resource"),
                "--wait", "--timeout={0}".format(timeout)
            ]
        )

    def test_wait_error(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.wait_for_idle(mock_runner),
            (
                Severity.ERROR,
                report_codes.WAIT_FOR_IDLE_ERROR,
                {
                    "reason": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--wait"]
        )

    def test_wait_error_timeout(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 62
        mock_runner = get_runner(
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.wait_for_idle(mock_runner),
            (
                Severity.ERROR,
                report_codes.WAIT_FOR_IDLE_TIMED_OUT,
                {
                    "reason": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--wait"]
        )

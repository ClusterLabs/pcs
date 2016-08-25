from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
import os.path

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.xml import XmlManipulation

from pcs import settings
from pcs.common import report_codes
from pcs.lib import pacemaker as lib
from pcs.lib.errors import ReportItemSeverity as Severity
from pcs.lib.external import CommandRunner


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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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

class ReplaceCibConfigurationTest(LibraryPacemakerTest):
    def test_success(self):
        xml = "<xml/>"
        expected_stdout = "expected output"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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

    def test_cib_upgraded(self):
        xml = "<xml/>"
        expected_stdout = "expected output"
        expected_stderr = ""
        expected_retval = 0
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        lib.replace_cib_configuration(
            mock_runner, XmlManipulation.from_str(xml).tree, True
        )

        mock_runner.run.assert_called_once_with(
            [self.path("cibadmin"), "--replace", "--verbose", "--xml-pipe"],
            stdin_string=xml
        )

    def test_error(self):
        xml = "<xml/>"
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 1
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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

class GetLocalNodeStatusTest(LibraryPacemakerNodeStatusTest):
    def test_offline(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
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

class ResourceCleanupTest(LibraryPacemakerTest):
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
            mock.call([self.path("crm_resource"), "--cleanup"]),
        ]
        return_value_list = [
            (self.fixture_status_xml(1, 1), "", 0),
            (expected_stdout, expected_stderr, 0),
        ]
        mock_runner.run.side_effect = return_value_list

        real_output = lib.resource_cleanup(mock_runner)

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_threshold_exceeded(self):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            self.fixture_status_xml(1000, 1000),
            "",
            0
        )

        assert_raise_library_error(
            lambda: lib.resource_cleanup(mock_runner),
            (
                Severity.ERROR,
                report_codes.RESOURCE_CLEANUP_TOO_TIME_CONSUMING,
                {"threshold": 100},
                report_codes.FORCE_LOAD_THRESHOLD
            )
        )

        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())

    def test_forced(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (expected_stdout, expected_stderr, 0)

        real_output = lib.resource_cleanup(mock_runner, force=True)

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--cleanup"]
        )
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_resource(self):
        resource = "test_resource"
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (expected_stdout, expected_stderr, 0)

        real_output = lib.resource_cleanup(mock_runner, resource=resource)

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--cleanup", "--resource", resource]
        )
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_node(self):
        node = "test_node"
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (expected_stdout, expected_stderr, 0)

        real_output = lib.resource_cleanup(mock_runner, node=node)

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--cleanup", "--node", node]
        )
        self.assertEqual(
            expected_stdout + "\n" + expected_stderr,
            real_output
        )

    def test_node_and_resource(self):
        node = "test_node"
        resource = "test_resource"
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (expected_stdout, expected_stderr, 0)

        real_output = lib.resource_cleanup(
            mock_runner, resource=resource, node=node
        )

        mock_runner.run.assert_called_once_with(
            [
                self.path("crm_resource"),
                "--cleanup", "--resource", resource, "--node", node
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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.resource_cleanup(mock_runner),
            (
                Severity.ERROR,
                report_codes.CRM_MON_ERROR,
                {
                    "reason": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())

    def test_error_cleanup(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [
            mock.call(self.crm_mon_cmd()),
            mock.call([self.path("crm_resource"), "--cleanup"]),
        ]
        return_value_list = [
            (self.fixture_status_xml(1, 1), "", 0),
            (expected_stdout, expected_stderr, expected_retval),
        ]
        mock_runner.run.side_effect = return_value_list

        assert_raise_library_error(
            lambda: lib.resource_cleanup(mock_runner),
            (
                Severity.ERROR,
                report_codes.RESOURCE_CLEANUP_ERROR,
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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertTrue(
            lib.has_resource_wait_support(mock_runner)
        )
        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "-?"]
        )

    def test_has_support_stdout(self):
        expected_stdout = "something --wait something else"
        expected_stderr = ""
        expected_retval = 1
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertTrue(
            lib.has_resource_wait_support(mock_runner)
        )
        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "-?"]
        )

    def test_doesnt_have_support(self):
        expected_stdout = "something something else"
        expected_stderr = "something something else"
        expected_retval = 1
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertFalse(
            lib.has_resource_wait_support(mock_runner)
        )
        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "-?"]
        )

    @mock.patch("pcs.lib.pacemaker.has_resource_wait_support", autospec=True)
    def test_ensure_support_success(self, mock_obj):
        mock_obj.return_value = True
        self.assertEqual(None, lib.ensure_resource_wait_support(mock.Mock()))

    @mock.patch("pcs.lib.pacemaker.has_resource_wait_support", autospec=True)
    def test_ensure_support_error(self, mock_obj):
        mock_obj.return_value = False
        assert_raise_library_error(
            lambda: lib.ensure_resource_wait_support(mock.Mock()),
            (
                Severity.ERROR,
                report_codes.RESOURCE_WAIT_NOT_SUPPORTED,
                {}
            )
        )

    def test_wait_success(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 0
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertEqual(None, lib.wait_for_resources(mock_runner))

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--wait"]
        )

    def test_wait_timeout_success(self):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 0
        timeout = 10
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        self.assertEqual(None, lib.wait_for_resources(mock_runner, timeout))

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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.wait_for_resources(mock_runner),
            (
                Severity.ERROR,
                report_codes.RESOURCE_WAIT_ERROR,
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
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.wait_for_resources(mock_runner),
            (
                Severity.ERROR,
                report_codes.RESOURCE_WAIT_TIMED_OUT,
                {
                    "reason": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(
            [self.path("crm_resource"), "--wait"]
        )

class NodeStandbyTest(LibraryPacemakerNodeStatusTest):
    def test_standby_local(self):
        expected_retval = 0
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("dummy", "", expected_retval)

        output = lib.nodes_standby(mock_runner)

        mock_runner.run.assert_called_once_with(
            [self.path("crm_standby"), "-v", "on"]
        )
        self.assertEqual(None, output)

    def test_unstandby_local(self):
        expected_retval = 0
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("dummy", "", expected_retval)

        output = lib.nodes_unstandby(mock_runner)

        mock_runner.run.assert_called_once_with(
            [self.path("crm_standby"), "-D"]
        )
        self.assertEqual(None, output)

    def test_standby_all(self):
        nodes = ("node1", "node2", "node3")
        for i, n in enumerate(nodes, 1):
            self.fixture_add_node_status(
                self.fixture_get_node_status(n, i)
            )
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [mock.call(self.crm_mon_cmd())]
        call_list += [
            mock.call([self.path("crm_standby"), "-v", "on", "-N", n])
            for n in nodes
        ]
        return_value_list = [(str(self.status), "", 0)]
        return_value_list += [("dummy", "", 0) for n in nodes]
        mock_runner.run.side_effect = return_value_list

        output = lib.nodes_standby(mock_runner, all_nodes=True)

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)
        self.assertEqual(None, output)

    def test_unstandby_all(self):
        nodes = ("node1", "node2", "node3")
        for i, n in enumerate(nodes, 1):
            self.fixture_add_node_status(
                self.fixture_get_node_status(n, i)
            )
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [mock.call(self.crm_mon_cmd())]
        call_list += [
            mock.call([self.path("crm_standby"), "-D", "-N", n])
            for n in nodes
        ]
        return_value_list = [(str(self.status), "", 0)]
        return_value_list += [("dummy", "", 0) for n in nodes]
        mock_runner.run.side_effect = return_value_list

        output = lib.nodes_unstandby(mock_runner, all_nodes=True)

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)
        self.assertEqual(None, output)

    def test_standby_nodes(self):
        nodes = ("node1", "node2", "node3")
        for i, n in enumerate(nodes, 1):
            self.fixture_add_node_status(
                self.fixture_get_node_status(n, i)
            )
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [mock.call(self.crm_mon_cmd())]
        call_list += [
            mock.call([self.path("crm_standby"), "-v", "on", "-N", n])
            for n in nodes[1:]
        ]
        return_value_list = [(str(self.status), "", 0)]
        return_value_list += [("dummy", "", 0) for n in nodes[1:]]
        mock_runner.run.side_effect = return_value_list

        output = lib.nodes_standby(mock_runner, node_list=nodes[1:])

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)
        self.assertEqual(None, output)

    def test_unstandby_nodes(self):
        nodes = ("node1", "node2", "node3")
        for i, n in enumerate(nodes, 1):
            self.fixture_add_node_status(
                self.fixture_get_node_status(n, i)
            )
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [mock.call(self.crm_mon_cmd())]
        call_list += [
            mock.call([self.path("crm_standby"), "-D", "-N", n])
            for n in nodes[:2]
        ]
        return_value_list = [(str(self.status), "", 0)]
        return_value_list += [("dummy", "", 0) for n in nodes[:2]]
        mock_runner.run.side_effect = return_value_list

        output = lib.nodes_unstandby(mock_runner, node_list=nodes[:2])

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)
        self.assertEqual(None, output)

    def test_standby_unknown_node(self):
        self.fixture_add_node_status(
            self.fixture_get_node_status("node_1", "id_1")
        )
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (str(self.status), "", 0)

        assert_raise_library_error(
            lambda: lib.nodes_standby(mock_runner, ["node_2"]),
            (
                Severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {"node": "node_2"}
            )
        )

        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())

    def test_unstandby_unknown_node(self):
        self.fixture_add_node_status(
            self.fixture_get_node_status("node_1", "id_1")
        )
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (str(self.status), "", 0)

        assert_raise_library_error(
            lambda: lib.nodes_unstandby(mock_runner, ["node_2", "node_3"]),
            (
                Severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {"node": "node_2"}
            ),
            (
                Severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {"node": "node_3"}
            )
        )

        mock_runner.run.assert_called_once_with(self.crm_mon_cmd())

    def test_error_one_node(self):
        expected_stdout = "some info"
        expected_stderr = "some error"
        expected_retval = 1
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (
            expected_stdout,
            expected_stderr,
            expected_retval
        )

        assert_raise_library_error(
            lambda: lib.nodes_unstandby(mock_runner),
            (
                Severity.ERROR,
                report_codes.COMMON_ERROR,
                {
                    "text": expected_stderr + "\n" + expected_stdout,
                }
            )
        )

        mock_runner.run.assert_called_once_with(
            [self.path("crm_standby"), "-D"]
        )

    def test_error_some_nodes(self):
        nodes = ("node1", "node2", "node3", "node4")
        for i, n in enumerate(nodes, 1):
            self.fixture_add_node_status(
                self.fixture_get_node_status(n, i)
            )
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        call_list = [mock.call(self.crm_mon_cmd())]
        call_list += [
            mock.call([self.path("crm_standby"), "-v", "on", "-N", n])
            for n in nodes
        ]
        return_value_list = [
            (str(self.status), "", 0),
            ("dummy1", "", 0),
            ("dummy2", "error2", 1),
            ("dummy3", "", 0),
            ("dummy4", "error4", 1),
        ]
        mock_runner.run.side_effect = return_value_list

        assert_raise_library_error(
            lambda: lib.nodes_standby(mock_runner, all_nodes=True),
            (
                Severity.ERROR,
                report_codes.COMMON_ERROR,
                {
                    "text": "error2\ndummy2",
                }
            ),
            (
                Severity.ERROR,
                report_codes.COMMON_ERROR,
                {
                    "text": "error4\ndummy4",
                }
            )
        )

        self.assertEqual(len(return_value_list), len(call_list))
        self.assertEqual(len(return_value_list), mock_runner.run.call_count)
        mock_runner.run.assert_has_calls(call_list)


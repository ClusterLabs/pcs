import os.path
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import file_type_codes
from pcs.common.file import RawFileError
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes
from pcs.lib.corosync import live as lib
from pcs.lib.external import CommandRunner

from pcs_test.tools.assertions import assert_raise_library_error
from pcs_test.tools.misc import get_test_resource as rc

# pylint: disable=no-self-use


class GetLocalCorosyncConfTest(TestCase):
    def test_success(self):
        path = rc("corosync.conf")
        settings.corosync_conf_file = path
        with open(path) as a_file:
            self.assertEqual(lib.get_local_corosync_conf(), a_file.read())

    def test_error(self):
        path = rc("corosync.conf.nonexistent")
        settings.corosync_conf_file = path
        assert_raise_library_error(
            lib.get_local_corosync_conf,
            (
                severity.ERROR,
                report_codes.FILE_IO_ERROR,
                {
                    "file_type_code": file_type_codes.COROSYNC_CONF,
                    "operation": RawFileError.ACTION_READ,
                    "reason": f"No such file or directory: '{path}'",
                    "file_path": path,
                },
            ),
        )


class GetQuorumStatusTextTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.quorum_tool = os.path.join(
            settings.corosync_binaries, "corosync-quorumtool"
        )

    def test_success(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info", lib.get_quorum_status_text(self.mock_runner)
        )
        self.mock_runner.run.assert_called_once_with([self.quorum_tool, "-p"])

    def test_success_with_retval_1(self):
        self.mock_runner.run.return_value = ("status info", "", 1)
        self.assertEqual(
            "status info", lib.get_quorum_status_text(self.mock_runner)
        )
        self.mock_runner.run.assert_called_once_with([self.quorum_tool, "-p"])

    def test_error(self):
        self.mock_runner.run.return_value = ("some info", "status error", 2)
        with self.assertRaises(lib.QuorumStatusReadException) as cm:
            lib.get_quorum_status_text(self.mock_runner)
        self.mock_runner.run.assert_called_once_with([self.quorum_tool, "-p"])
        self.assertEqual(cm.exception.reason, "status error")


class SetExpectedVotesTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def path(self, name):
        return os.path.join(settings.corosync_binaries, name)

    def test_success(self):
        cmd_retval = 0
        cmd_stdout = "cmd output"
        cmd_stderr = ""
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (cmd_stdout, cmd_stderr, cmd_retval)

        lib.set_expected_votes(mock_runner, 3)

        mock_runner.run.assert_called_once_with(
            [self.path("corosync-quorumtool"), "-e", "3"]
        )

    def test_error(self):
        cmd_retval = 1
        cmd_stdout = "cmd output"
        cmd_stderr = "cmd stderr"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (cmd_stdout, cmd_stderr, cmd_retval)

        assert_raise_library_error(
            lambda: lib.set_expected_votes(mock_runner, 3),
            (
                severity.ERROR,
                report_codes.COROSYNC_QUORUM_SET_EXPECTED_VOTES_ERROR,
                {
                    "reason": cmd_stderr,
                },
            ),
        )

        mock_runner.run.assert_called_once_with(
            [self.path("corosync-quorumtool"), "-e", "3"]
        )


class QuorumStatusParse(TestCase):
    def test_quorate_no_qdevice(self):
        facade = lib.QuorumStatusFacade.from_string(
            dedent(
                """\
                Quorum information
                ------------------
                Date:             Fri Jan 16 13:03:28 2015
                Quorum provider:  corosync_votequorum
                Nodes:            3
                Node ID:          1
                Ring ID:          19860
                Quorate:          Yes

                Votequorum information
                ----------------------
                Expected votes:   3
                Highest expected: 3
                Total votes:      3
                Quorum:           2
                Flags:            Quorate

                Membership information
                ----------------------
                    Nodeid      Votes    Qdevice Name
                         1          3         NR rh70-node1
                         2          2         NR rh70-node2 (local)
                         3          1         NR rh70-node3
            """
            )
        )
        self.assertEqual(facade.is_quorate, True)
        self.assertEqual(facade.votes_needed_for_quorum, 2)
        self.assertEqual(facade.qdevice_votes, 0)
        self.assertEqual(
            facade.node_list,
            [
                lib.QuorumStatusNode(name="rh70-node1", votes=3, local=False),
                lib.QuorumStatusNode(name="rh70-node2", votes=2, local=True),
                lib.QuorumStatusNode(name="rh70-node3", votes=1, local=False),
            ],
        )
        self.assertEqual(facade.qdevice_list, [])

    def test_quorate_with_qdevice(self):
        facade = lib.QuorumStatusFacade.from_string(
            dedent(
                """\
                Quorum information
                ------------------
                Date:             Fri Jan 16 13:03:28 2015
                Quorum provider:  corosync_votequorum
                Nodes:            3
                Node ID:          1
                Ring ID:          19860
                Quorate:          Yes

                Votequorum information
                ----------------------
                Expected votes:   10
                Highest expected: 10
                Total votes:      10
                Quorum:           6
                Flags:            Quorate Qdevice

                Membership information
                ----------------------
                    Nodeid      Votes    Qdevice Name
                         1          3    A,V,MNW rh70-node1
                         2          2    A,V,MNW rh70-node2 (local)
                         3          1    A,V,MNW rh70-node3
                         0          4            Qdevice
            """
            )
        )
        self.assertEqual(facade.is_quorate, True)
        self.assertEqual(facade.votes_needed_for_quorum, 6)
        self.assertEqual(facade.qdevice_votes, 4)
        self.assertEqual(
            facade.node_list,
            [
                lib.QuorumStatusNode(name="rh70-node1", votes=3, local=False),
                lib.QuorumStatusNode(name="rh70-node2", votes=2, local=True),
                lib.QuorumStatusNode(name="rh70-node3", votes=1, local=False),
            ],
        )
        self.assertEqual(
            facade.qdevice_list,
            [
                lib.QuorumStatusNode(name="Qdevice", votes=4, local=False),
            ],
        )

    def test_quorate_with_qdevice_lost(self):
        facade = lib.QuorumStatusFacade.from_string(
            dedent(
                """\
                Quorum information
                ------------------
                Date:             Fri Jan 16 13:03:28 2015
                Quorum provider:  corosync_votequorum
                Nodes:            3
                Node ID:          1
                Ring ID:          19860
                Quorate:          Yes

                Votequorum information
                ----------------------
                Expected votes:   10
                Highest expected: 10
                Total votes:      6
                Quorum:           6
                Flags:            Quorate Qdevice

                Membership information
                ----------------------
                    Nodeid      Votes    Qdevice Name
                         1          3   NA,V,MNW rh70-node1
                         2          2   NA,V,MNW rh70-node2 (local)
                         3          1   NA,V,MNW rh70-node3
                         0          0            Qdevice (votes 4)
            """
            )
        )
        self.assertEqual(facade.is_quorate, True)
        self.assertEqual(facade.votes_needed_for_quorum, 6)
        self.assertEqual(facade.qdevice_votes, 0)
        self.assertEqual(
            facade.node_list,
            [
                lib.QuorumStatusNode(name="rh70-node1", votes=3, local=False),
                lib.QuorumStatusNode(name="rh70-node2", votes=2, local=True),
                lib.QuorumStatusNode(name="rh70-node3", votes=1, local=False),
            ],
        )
        self.assertEqual(
            facade.qdevice_list,
            [
                lib.QuorumStatusNode(name="Qdevice", votes=0, local=False),
            ],
        )

    def test_no_quorate_no_qdevice(self):
        facade = lib.QuorumStatusFacade.from_string(
            dedent(
                """\
                Quorum information
                ------------------
                Date:             Fri Jan 16 13:03:35 2015
                Quorum provider:  corosync_votequorum
                Nodes:            1
                Node ID:          1
                Ring ID:          19868
                Quorate:          No

                Votequorum information
                ----------------------
                Expected votes:   3
                Highest expected: 3
                Total votes:      1
                Quorum:           2 Activity blocked
                Flags:            

                Membership information
                ----------------------
                    Nodeid      Votes    Qdevice Name
                             1          1         NR rh70-node1 (local)
            """
            )
        )
        self.assertEqual(facade.is_quorate, False)
        self.assertEqual(facade.votes_needed_for_quorum, 2)
        self.assertEqual(facade.qdevice_votes, 0)
        self.assertEqual(
            facade.node_list,
            [
                lib.QuorumStatusNode(name="rh70-node1", votes=1, local=True),
            ],
        )
        self.assertEqual(facade.qdevice_list, [])

    def test_no_quorate_with_qdevice(self):
        facade = lib.QuorumStatusFacade.from_string(
            dedent(
                """\
                Quorum information
                ------------------
                Date:             Fri Jan 16 13:03:35 2015
                Quorum provider:  corosync_votequorum
                Nodes:            1
                Node ID:          1
                Ring ID:          19868
                Quorate:          No

                Votequorum information
                ----------------------
                Expected votes:   3
                Highest expected: 3
                Total votes:      1
                Quorum:           2 Activity blocked
                Flags:            Qdevice

                Membership information
                ----------------------
                    Nodeid      Votes    Qdevice Name
                         1          1         NR rh70-node1 (local)
                         0          0            Qdevice (votes 1)
            """
            )
        )
        self.assertEqual(facade.is_quorate, False)
        self.assertEqual(facade.votes_needed_for_quorum, 2)
        self.assertEqual(facade.qdevice_votes, 0)
        self.assertEqual(
            facade.node_list,
            [
                lib.QuorumStatusNode(name="rh70-node1", votes=1, local=True),
            ],
        )
        self.assertEqual(
            facade.qdevice_list,
            [
                lib.QuorumStatusNode(name="Qdevice", votes=0, local=False),
            ],
        )

    def test_error_empty_string(self):
        with self.assertRaises(lib.QuorumStatusParsingException) as cm:
            lib.QuorumStatusFacade.from_string("")
        self.assertEqual(
            cm.exception.reason,
            "Missing required section(s): 'node_list', 'quorate', 'quorum'",
        )

    def test_error_missing_quorum(self):
        with self.assertRaises(lib.QuorumStatusParsingException) as cm:
            lib.QuorumStatusFacade.from_string(
                dedent(
                    """\
                    Quorum information
                    ------------------
                    Date:             Fri Jan 16 13:03:28 2015
                    Quorum provider:  corosync_votequorum
                    Nodes:            3
                    Node ID:          1
                    Ring ID:          19860
                    Quorate:          Yes

                    Votequorum information
                    ----------------------
                    Expected votes:   3
                    Highest expected: 3
                    Total votes:      3
                    Quorum:           
                    Flags:            Quorate

                    Membership information
                    ----------------------
                        Nodeid      Votes    Qdevice Name
                             1          1         NR rh70-node1 (local)
                             2          1         NR rh70-node2
                             3          1         NR rh70-node3
                """
                )
            )
        self.assertEqual(
            cm.exception.reason,
            "Unable to read number of votes needed for quorum",
        )

    def test_error_quorum_garbage(self):
        with self.assertRaises(lib.QuorumStatusParsingException) as cm:
            lib.QuorumStatusFacade.from_string(
                dedent(
                    """\
                    Quorum information
                    ------------------
                    Date:             Fri Jan 16 13:03:28 2015
                    Quorum provider:  corosync_votequorum
                    Nodes:            3
                    Node ID:          1
                    Ring ID:          19860
                    Quorate:          Yes

                    Votequorum information
                    ----------------------
                    Expected votes:   3
                    Highest expected: 3
                    Total votes:      3
                    Quorum:           Foo
                    Flags:            Quorate

                    Membership information
                    ----------------------
                        Nodeid      Votes    Qdevice Name
                             1          1         NR rh70-node1 (local)
                             2          1         NR rh70-node2
                             3          1         NR rh70-node3
                """
                )
            )
        self.assertEqual(
            cm.exception.reason,
            "Unable to read number of votes needed for quorum",
        )

    def test_error_node_votes_garbage(self):
        with self.assertRaises(lib.QuorumStatusParsingException) as cm:
            lib.QuorumStatusFacade.from_string(
                dedent(
                    """\
                    Quorum information
                    ------------------
                    Date:             Fri Jan 16 13:03:28 2015
                    Quorum provider:  corosync_votequorum
                    Nodes:            3
                    Node ID:          1
                    Ring ID:          19860
                    Quorate:          Yes

                    Votequorum information
                    ----------------------
                    Expected votes:   3
                    Highest expected: 3
                    Total votes:      3
                    Quorum:           2
                    Flags:            Quorate

                    Membership information
                    ----------------------
                        Nodeid      Votes    Qdevice Name
                             1          1         NR rh70-node1 (local)
                             2        foo         NR rh70-node2
                             3          1         NR rh70-node3
                """
                )
            )
        self.assertEqual(cm.exception.reason, "")


class QuorumStatusQuorumLossNodes(TestCase):
    def test_not_quorate(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=False,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=3, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node3"]), False
        )

    def test_one_node_still_quorate_1(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=3, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node3"]), False
        )

    def test_one_node_still_quorate_2(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=3, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node2"]), False
        )

    def test_one_node_quorum_loss(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=3, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node1"]), True
        )

    def test_more_nodes_still_quorate(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=4, local=True),
                    lib.QuorumStatusNode(name="node2", votes=1, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node2", "node3"]),
            False,
        )

    def test_more_nodes_quorum_loss(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=3, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node2", "node3"]),
            True,
        )

    def test_qdevice_still_quorate(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=3,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=1, local=True),
                    lib.QuorumStatusNode(name="node2", votes=1, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[
                    lib.QuorumStatusNode(name="Qdevice", votes=1, local=False),
                ],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node2"]), False
        )

    def test_qdevice_quorum_lost(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=3,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=1, local=True),
                    lib.QuorumStatusNode(name="node2", votes=1, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[
                    lib.QuorumStatusNode(name="Qdevice", votes=1, local=False),
                ],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node2", "node3"]),
            True,
        )

    def test_qdevice_lost_still_quorate(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,  # expect qdevice votes == 1
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=2, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=2, local=False),
                ],
                qdevice_list=[
                    lib.QuorumStatusNode(name="Qdevice", votes=0, local=False),
                ],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node2"]), False
        )

    def test_qdevice_lost_quorum_lost(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,  # expect qdevice votes == 1
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=2, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=2, local=False),
                ],
                qdevice_list=[
                    lib.QuorumStatusNode(name="Qdevice", votes=0, local=False),
                ],
            )
        )
        self.assertEqual(
            facade.stopping_nodes_cause_quorum_loss(["node2", "node3"]),
            True,
        )


class QuorumStatusQuorumLossLocal(TestCase):
    def test_not_quorate(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=False,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=3, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), False)

    def test_local_node_not_in_list(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=1,
                node_list=[
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), False)

    def test_local_node_alone_in_list(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=1,
                node_list=[
                    lib.QuorumStatusNode(name="node3", votes=1, local=True),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), True)

    def test_local_node_still_quorate_1(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=3, local=False),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=True),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), False)

    def test_local_node_still_quorate_2(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=3, local=False),
                    lib.QuorumStatusNode(name="node2", votes=2, local=True),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), False)

    def test_local_node_quorum_loss(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=3, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), True)

    def test_qdevice_still_quorate(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=3,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=1, local=True),
                    lib.QuorumStatusNode(name="node2", votes=1, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[
                    lib.QuorumStatusNode(name="Qdevice", votes=1, local=False),
                ],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), False)

    def test_qdevice_quorum_lost(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=4, local=True),
                    lib.QuorumStatusNode(name="node2", votes=1, local=False),
                    lib.QuorumStatusNode(name="node3", votes=1, local=False),
                ],
                qdevice_list=[
                    lib.QuorumStatusNode(name="Qdevice", votes=1, local=False),
                ],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), True)

    def test_qdevice_lost_still_quorate(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=4,  # expect qdevice votes == 1
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=2, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=2, local=False),
                ],
                qdevice_list=[
                    lib.QuorumStatusNode(name="Qdevice", votes=0, local=False),
                ],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), False)

    def test_qdevice_lost_quorum_lost(self):
        facade = lib.QuorumStatusFacade(
            lib.QuorumStatus(
                is_quorate=True,
                votes_needed_for_quorum=5,  # expect qdevice votes == 1
                node_list=[
                    lib.QuorumStatusNode(name="node1", votes=4, local=True),
                    lib.QuorumStatusNode(name="node2", votes=2, local=False),
                    lib.QuorumStatusNode(name="node3", votes=2, local=False),
                ],
                qdevice_list=[
                    lib.QuorumStatusNode(name="Qdevice", votes=0, local=False),
                ],
            )
        )
        self.assertEqual(facade.stopping_local_node_cause_quorum_loss(), True)

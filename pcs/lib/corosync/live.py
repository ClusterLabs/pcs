import os.path
import re
from dataclasses import dataclass
from typing import (
    Container,
    Optional,
    Sequence,
    cast,
)

from pcs import settings
from pcs.common import reports
from pcs.common.file import RawFileError
from pcs.common.reports.item import ReportItem
from pcs.common.str_tools import format_list
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report


def get_local_corosync_conf() -> str:
    """
    Read corosync.conf file from the local node
    """
    # TODO The architecture of working with corosync.conf needs to be
    # overhauled to match the new file framework.
    instance = FileInstance.for_corosync_conf()
    try:
        return instance.read_raw().decode("utf-8")
    except RawFileError as e:
        raise LibraryError(raw_file_error_report(e)) from e


def set_expected_votes(runner: CommandRunner, votes: int) -> str:
    """
    set expected votes in live cluster to the specified value
    """
    stdout, stderr, retval = runner.run(
        [
            os.path.join(settings.corosync_binaries, "corosync-quorumtool"),
            "-e",
            str(votes),
        ]
    )
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CorosyncQuorumSetExpectedVotesError(stderr)
            )
        )
    return stdout


class QuorumStatusException(Exception):
    def __init__(self, reason: str = ""):
        super().__init__()
        self.reason = reason


class QuorumStatusReadException(QuorumStatusException):
    pass


class QuorumStatusParsingException(QuorumStatusException):
    pass


def get_quorum_status_text(runner: CommandRunner) -> str:
    """
    Get runtime quorum status from the local node
    """
    stdout, stderr, retval = runner.run(
        [os.path.join(settings.corosync_binaries, "corosync-quorumtool"), "-p"]
    )
    # retval is 0 on success if the node is not in a partition with quorum
    # retval is 1 on error OR on success if the node has quorum
    if retval not in [0, 1] or stderr.strip():
        raise QuorumStatusReadException(stderr)
    return stdout


@dataclass(frozen=True)
class QuorumStatusNode:
    name: str
    votes: int
    local: bool


@dataclass(frozen=True)
class QuorumStatus:
    node_list: Sequence[QuorumStatusNode]
    qdevice_list: Sequence[QuorumStatusNode]
    is_quorate: bool
    votes_needed_for_quorum: int

    @property
    def qdevice_votes(self) -> int:
        """
        How many votes are provided by qdevice(s)?
        """
        return sum(qdevice.votes for qdevice in self.qdevice_list)

    def _get_votes_excluding_nodes(self, node_names: Container[str]) -> int:
        """
        How many votes do remain if specified nodes are not counted in?

        node_names -- names of nodes not to count in
        """
        return (
            sum(
                node.votes
                for node in self.node_list
                if node.name not in node_names
            )
            + self.qdevice_votes
        )

    def _get_votes_excluding_local_node(self) -> int:
        """
        How many votes do remain if the local node is not counted in?
        """
        return (
            sum(node.votes for node in self.node_list if not node.local)
            + self.qdevice_votes
        )

    def stopping_nodes_cause_quorum_loss(
        self, node_names: Container[str]
    ) -> bool:
        """
        Will quorum be lost if specified nodes are stopped?

        node_names -- list of names of nodes to be stopped
        """
        if not self.is_quorate:
            return False
        return (
            self._get_votes_excluding_nodes(node_names)
            < self.votes_needed_for_quorum
        )

    def stopping_local_node_cause_quorum_loss(self) -> bool:
        """
        Will quorum be lost if the local node is stopped?
        """
        if not self.is_quorate:
            return False
        return (
            self._get_votes_excluding_local_node()
            < self.votes_needed_for_quorum
        )


def parse_quorum_status(quorum_status: str) -> QuorumStatus:
    # pylint: disable=too-many-branches
    node_list: list[QuorumStatusNode] = []
    qdevice_list: list[QuorumStatusNode] = []
    quorate: Optional[bool] = None
    quorum: Optional[int] = None

    in_node_list = False
    try:
        for line in quorum_status.splitlines():
            line = line.strip()
            if not line:
                continue
            if in_node_list:
                if line.startswith("-") or line.startswith("Nodeid"):
                    # skip headers
                    continue
                parts = line.split()
                if parts[0] == "0":
                    # this line has nodeid == 0, this is a qdevice line
                    qdevice_list.append(
                        QuorumStatusNode(
                            name=parts[2],
                            votes=int(parts[1]),
                            local=False,
                        )
                    )
                else:
                    # this line has non-zero nodeid, this is a node line
                    node_list.append(
                        QuorumStatusNode(
                            name=parts[3],
                            votes=int(parts[1]),
                            local=(len(parts) > 4 and parts[4] == "(local)"),
                        )
                    )
            else:
                if line == "Membership information":
                    in_node_list = True
                    continue
                if not ":" in line:
                    continue
                parts = [x.strip() for x in line.split(":", 1)]
                if parts[0] == "Quorate":
                    quorate = parts[1].lower() == "yes"
                elif parts[0] == "Quorum":
                    match = re.match(r"(\d+).*", parts[1])
                    if match:
                        quorum = int(match.group(1))
                    else:
                        raise QuorumStatusParsingException(
                            "Unable to read number of votes needed for quorum"
                        )
    except (ValueError, IndexError) as e:
        raise QuorumStatusParsingException() from e
    missing_sections = []
    if quorum is None:
        missing_sections.append("quorum")
    if quorate is None:
        missing_sections.append("quorate")
    if not node_list:
        missing_sections.append("node_list")
    if missing_sections:
        raise QuorumStatusParsingException(
            "Missing required section(s): {}".format(
                format_list(missing_sections)
            )
        )
    return QuorumStatus(
        node_list=node_list,
        qdevice_list=qdevice_list,
        is_quorate=cast(bool, quorate),
        votes_needed_for_quorum=cast(int, quorum),
    )

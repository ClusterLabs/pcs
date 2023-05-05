import os.path
import re

from pcs import settings
from pcs.common import reports
from pcs.common.file import RawFileError
from pcs.common.reports.item import ReportItem
from pcs.lib.errors import LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report


def get_local_corosync_conf():
    """
    Read corosync.conf file from local machine
    """
    # TODO The architecture of working with corosync.conf needs to be
    # overhauled to match the new file framework.
    instance = FileInstance.for_corosync_conf()
    try:
        return instance.read_raw().decode("utf-8")
    except RawFileError as e:
        raise LibraryError(raw_file_error_report(e)) from e


def get_quorum_status_text(runner):
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


def set_expected_votes(runner, votes):
    """
    set expected votes in live cluster to specified value
    """
    stdout, stderr, retval = runner.run(
        [
            os.path.join(settings.corosync_binaries, "corosync-quorumtool"),
            # format votes to handle the case where they are int
            "-e",
            "{0}".format(votes),
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
    def __init__(self, reason=""):
        super().__init__()
        self.reason = reason


class QuorumStatusReadException(QuorumStatusException):
    pass


class QuorumStatusParsingException(QuorumStatusException):
    pass


class QuorumStatus:
    """
    Parse corosync quorum status and provide access to parsed info
    """

    def __init__(self, data):
        self._data = data

    @classmethod
    def from_string(cls, quorum_status):
        # pylint: disable=too-many-branches
        """
        Create an instance based on corosync quorum status plaintext data

        string quorum_status -- corosync quorum status plaintext
        """
        parsed = {}
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
                        parsed["qdevice_list"].append(
                            {
                                "name": parts[2],
                                "votes": int(parts[1]),
                                "local": False,
                            }
                        )
                    else:
                        # this line has non-zero nodeid, this is a node line
                        parsed["node_list"].append(
                            {
                                "name": parts[3],
                                "votes": int(parts[1]),
                                "local": len(parts) > 4
                                and parts[4] == "(local)",
                            }
                        )
                else:
                    if line == "Membership information":
                        in_node_list = True
                        parsed["node_list"] = []
                        parsed["qdevice_list"] = []
                        continue
                    if not ":" in line:
                        continue
                    parts = [x.strip() for x in line.split(":", 1)]
                    if parts[0] == "Quorate":
                        parsed["quorate"] = parts[1].lower() == "yes"
                    elif parts[0] == "Quorum":
                        match = re.match(r"(\d+).*", parts[1])
                        if match:
                            parsed["quorum"] = int(match.group(1))
                        else:
                            raise QuorumStatusParsingException(
                                "Unable to read number of votes needed for "
                                "quorum"
                            )
        except (ValueError, IndexError) as e:
            raise QuorumStatusParsingException() from e
        missing_sections = [
            required
            for required in ("quorum", "quorate", "node_list")
            if required not in parsed
        ]
        if missing_sections:
            raise QuorumStatusParsingException(
                "Missing required section(s): '{}'".format(
                    "', '".join(sorted(missing_sections))
                )
            )
        return cls(parsed)

    @property
    def is_quorate(self):
        """
        Does the cluster have quorum?
        """
        return bool(self._data["quorate"])

    @property
    def votes_needed_for_quorum(self):
        """
        How many votes are needed for the cluster to have quorum?
        """
        return self._data["quorum"]

    @property
    def qdevice_votes(self):
        """
        How many votes are provided by qdevice(s)?
        """
        qdevice_votes = 0
        for qdevice_info in self._data.get("qdevice_list", []):
            qdevice_votes += qdevice_info["votes"]
        return qdevice_votes

    def _get_votes_excluding_nodes(self, node_names):
        """
        How many votes do remain if some nodes are not counted in?

        iterable node_names -- list of names of nodes not to count in
        """
        votes = 0
        for node_info in self._data["node_list"]:
            if not (node_names and node_info["name"] in node_names):
                votes += node_info["votes"]
        votes += self.qdevice_votes
        return votes

    def _get_votes_excluding_local_node(self):
        """
        How many votes do remain if the local node is not counted in?
        """
        votes = 0
        for node_info in self._data["node_list"]:
            if not node_info["local"]:
                votes += node_info["votes"]
        votes += self.qdevice_votes
        return votes

    def stopping_nodes_cause_quorum_loss(self, node_names):
        """
        Will quorum be lost if specified nodes are stopped?

        iterable node_names -- list of names of nodes to be stopped
        """
        if not self.is_quorate:
            return False
        return (
            self._get_votes_excluding_nodes(node_names)
            < self.votes_needed_for_quorum
        )

    def stopping_local_node_cause_quorum_loss(self):
        """
        Will quorum be lost if the local node is stopped?
        """
        if not self.is_quorate:
            return False
        return (
            self._get_votes_excluding_local_node()
            < self.votes_needed_for_quorum
        )

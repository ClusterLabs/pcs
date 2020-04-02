import os.path

from pcs_test.tools.misc import outdent
from pcs_test.tools.command_env.mock_runner import Call as RunnerCall

from pcs import settings


class CorosyncShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def version(
        self,
        name="runner.corosync.version",
        version="2.4.0",
        instead=None,
        before=None,
    ):
        self.__calls.place(
            name,
            RunnerCall(
                "corosync -v",
                stdout=outdent(
                    """\
                    Corosync Cluster Engine, version '{0}'
                    Copyright...
                    """.format(
                        version
                    )
                ),
            ),
            before=before,
            instead=instead,
        )

    def qdevice_generate_cert(
        self,
        cluster_name,
        cert_req_path="cert_path",
        stdout=None,
        stderr="",
        returncode=0,
        name="runner.corosync.qdevice_generate_cert",
    ):
        if stdout is not None and cert_req_path is not None:
            raise AssertionError(
                "Cannot specify both 'cert_req_path' and 'stdout'"
            )
        self.__calls.place(
            name,
            RunnerCall(
                "{binary} -r -n {cluster_name}".format(
                    binary=os.path.join(
                        settings.corosync_binaries,
                        "corosync-qdevice-net-certutil",
                    ),
                    cluster_name=cluster_name,
                ),
                stdout=(
                    stdout
                    if stdout is not None
                    else f"Certificate request stored in {cert_req_path}\n"
                ),
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def qdevice_get_pk12(
        self,
        cert_path="cert path",
        output_path="output_path",
        stdout=None,
        stderr="",
        returncode=0,
        name="runner.corosync.qdevice_get_pk12",
    ):
        if stdout is not None and output_path is not None:
            raise AssertionError(
                "Cannot specify both 'output_path' and 'stdout'"
            )
        self.__calls.place(
            name,
            RunnerCall(
                "{binary} -M -c {cert_path}".format(
                    binary=os.path.join(
                        settings.corosync_binaries,
                        "corosync-qdevice-net-certutil",
                    ),
                    cert_path=cert_path,
                ),
                stdout=(
                    stdout
                    if stdout is not None
                    else f"Certificate stored in {output_path}\n"
                ),
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def quorum_status(
        self,
        node_list=None,
        stdout=None,
        stderr="",
        returncode=0,
        name="runner.corosync.quorum_status",
    ):
        if bool(node_list) == bool(stdout):
            raise AssertionError(
                "Exactly one of 'node_list', 'stdout' must be specified"
            )
        if node_list:
            stdout = outdent(
                """\
            Quorum information
            ------------------
            Date:             Fri Jan 16 13:03:28 2015
            Quorum provider:  corosync_votequorum
            Nodes:            {nodes_num}
            Node ID:          1
            Ring ID:          19860
            Quorate:          Yes\n
            Votequorum information
            ----------------------
            Expected votes:   {nodes_num}
            Highest expected: {nodes_num}
            Total votes:      {nodes_num}
            Quorum:           {quorum_num}
            Flags:            Quorate\n
            Membership information
            ----------------------
                Nodeid      Votes    Qdevice Name
            {nodes}\
            """
            ).format(
                nodes_num=len(node_list),
                quorum_num=(len(node_list) // 2) + 1,
                nodes="".join(
                    [
                        _quorum_status_node_fixture(node_id, node)
                        for node_id, node in enumerate(node_list, 1)
                    ]
                ),
            )
        self.__calls.place(
            name,
            RunnerCall(
                "corosync-quorumtool -p",
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )


def _quorum_status_node_fixture(node_id, node_name, votes=1, is_local=False):
    _local = " (local)" if is_local else ""
    return (
        f"         {node_id}          {votes}         NR {node_name}{_local}\n"
    )

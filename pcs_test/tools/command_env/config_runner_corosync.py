import os.path
from textwrap import dedent

from pcs import settings

from pcs_test.tools.command_env.mock_runner import Call as RunnerCall


class CorosyncShortcuts:
    qdevice_generated_cert_path = os.path.join(
        settings.corosync_qdevice_net_client_certs_dir,
        "qdevice-net-node.crq",
    )
    qdevice_pk12_cert_path = os.path.join(
        settings.corosync_qdevice_net_client_certs_dir,
        "qdevice-net-node.p12",
    )

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
                ["corosync", "-v"],
                stdout=dedent(
                    f"""\
                    Corosync Cluster Engine, version '{version}'
                    Copyright...
                    """
                ),
            ),
            before=before,
            instead=instead,
        )

    def qdevice_init_cert_storage(
        self,
        ca_file_path,
        stdout="",
        stderr="",
        returncode=0,
        name="runner.corosync.qdevice_init_cert_storage",
    ):
        self.__calls.place(
            name,
            RunnerCall(
                ["corosync-qdevice-net-certutil", "-i", "-c", ca_file_path],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def qdevice_generate_cert(
        self,
        cluster_name,
        cert_req_path=None,
        stdout=None,
        stderr="",
        returncode=0,
        name="runner.corosync.qdevice_generate_cert",
    ):
        if stdout is not None and cert_req_path is not None:
            raise AssertionError(
                "Cannot specify both 'cert_req_path' and 'stdout'"
            )
        if stdout is None and cert_req_path is None:
            cert_req_path = self.qdevice_generated_cert_path
        self.__calls.place(
            name,
            RunnerCall(
                ["corosync-qdevice-net-certutil", "-r", "-n", cluster_name],
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
        output_path=None,
        stdout=None,
        stderr="",
        returncode=0,
        name="runner.corosync.qdevice_get_pk12",
    ):
        if stdout is not None and output_path is not None:
            raise AssertionError(
                "Cannot specify both 'output_path' and 'stdout'"
            )
        if stdout is None and output_path is None:
            output_path = self.qdevice_pk12_cert_path
        self.__calls.place(
            name,
            RunnerCall(
                ["corosync-qdevice-net-certutil", "-M", "-c", cert_path],
                stdout=(
                    stdout
                    if stdout is not None
                    else f"Certificate stored in {output_path}\n"
                ),
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def qdevice_import_pk12(
        self,
        pk12_file_path,
        stdout="",
        stderr="",
        returncode=0,
        name="runner.corosync.qdevice_import_pk12",
    ):
        self.__calls.place(
            name,
            RunnerCall(
                ["corosync-qdevice-net-certutil", "-m", "-c", pk12_file_path],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def qdevice_list_certs(
        self,
        stdout=None,
        stderr="",
        returncode=0,
        name="runner.corosync.qdevice_list_certs",
    ):
        if stdout is None:
            stdout = dedent(
                """\
                Certificate Nickname   Trust Attributes
                                       SSL,S/MIME,JAR/XPI

                QNet CA                CT,c,c
                Cluster Cert           u,u,u
                """
            )
        self.__calls.place(
            name,
            RunnerCall(
                [
                    settings.certutil_executable,
                    "-d",
                    settings.corosync_qdevice_net_client_certs_dir,
                    "-L",
                ],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def qdevice_show_cert(
        self,
        cert_name,
        stdout,
        ascii_only=False,
        stderr="",
        returncode=0,
        name="runner.corosync.qdevice_show_cert",
    ):
        cmd = [
            settings.certutil_executable,
            "-d",
            settings.corosync_qdevice_net_client_certs_dir,
            "-L",
            "-n",
            cert_name,
        ]
        if ascii_only:
            cmd.append("-a")
        self.__calls.place(
            name,
            RunnerCall(
                cmd,
                stdout=stdout,
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
            stdout = dedent(
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
                ["corosync-quorumtool", "-p"],
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

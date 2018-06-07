import os.path

from pcs import settings
from pcs.test.tools.misc import outdent
from pcs.test.tools.command_env.mock_runner import Call as RunnerCall

class CorosyncShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls

    def version(
        self,
        name="runner.corosync.version",
        version="2.4.0",
        instead=None,
        before=None
    ):
        self.__calls.place(
            name,
            RunnerCall(
                "corosync -v",
                stdout=outdent(
                    """\
                    Corosync Cluster Engine, version '{0}'
                    Copyright...
                    """.format(version)
                )
            ),
            before=before,
            instead=instead
        )

    def reload(
        self,
        name="runner.corosync.reload",
        instead=None,
        before=None
    ):
        self.__calls.place(
            name,
            RunnerCall(
                "corosync-cfgtool -R",
                stdout=outdent(
                    """\
                    Reloading corosync.conf...
                    Done
                    """
                )
            ),
            before=before,
            instead=instead
        )

    def qdevice_generate_cert(
        self, cluster_name, cert_req_path="cert_path",
        name="runner.corosync.qdevice_generate_cert"
    ):
        self.__calls.place(
            name,
            RunnerCall(
                "{binary} -r -n {cluster_name}".format(
                    binary=os.path.join(
                        settings.corosync_binaries,
                        "corosync-qdevice-net-certutil"
                    ),
                    cluster_name=cluster_name,
                ),
                # stdout=cert,
                stdout=f"Certificate request stored in {cert_req_path}\n",
            ),
        )

    def qdevice_get_pk12(
        self, cert_path="cert path", output_path="output_path",
        name="runner.corosync.qdevice_get_pk12"
    ):
        self.__calls.place(
            name,
            RunnerCall(
                "{binary} -M -c {cert_path}".format(
                    binary=os.path.join(
                        settings.corosync_binaries,
                        "corosync-qdevice-net-certutil"
                    ),
                    cert_path=cert_path,
                ),
                stdout=f"Certificate stored in {output_path}\n",
            ),
        )

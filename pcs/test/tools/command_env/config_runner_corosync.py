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

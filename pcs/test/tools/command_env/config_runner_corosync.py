from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.misc import outdent
from pcs.test.tools.command_env.mock_runner import Call as RunnerCall

class CorosyncShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls

    def version(self, name="corosync_version", version="2.4.0"):
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
            )
        )

    def reload(self, name="corosync_reload"):
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
            )
        )

from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.test.tools.command_env.mock_runner import Call as RunnerCall
from pcs.test.tools.fixture import complete_state_resources
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.xml import etree_to_str


DEFAULT_WAIT_TIMEOUT = 10
WAIT_TIMEOUT_EXPIRED_RETURNCODE = 62

class PcmkShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls
        self.default_wait_timeout = DEFAULT_WAIT_TIMEOUT
        self.default_wait_error_returncode = WAIT_TIMEOUT_EXPIRED_RETURNCODE

    def load_state(
        self, name="runner.pcmk.load_state", filename="crm_mon.minimal.xml",
        resources=None
    ):
        """
        Create call for loading pacemaker state.

        string name -- key of the call
        string filename -- points to file with the status in the content
        string resources -- xml - resources section, will be put to state
        """
        state = etree.fromstring(open(rc(filename)).read())
        if resources:
            state.append(complete_state_resources(etree.fromstring(resources)))

        self.__calls.place(
            name,
            RunnerCall(
                "crm_mon --one-shot --as-xml --inactive",
                stdout=etree_to_str(state),
            )
        )

    def load_agent(
        self,
        name="runner.pcmk.load_agent",
        agent_name="ocf:heartbeat:Dummy",
        agent_filename="resource_agent_ocf_heartbeat_dummy.xml",
        instead=None,
    ):
        """
        Create call for loading resource agent metadata.

        string name -- key of the call
        string agent_name
        string agent_filename -- points to file with the agent metadata in the
            content
        string instead -- key of call instead of which this new call is to be
            placed
        """
        self.__calls.place(
            name,
            RunnerCall(
                "crm_resource --show-metadata {0}".format(agent_name),
                stdout=open(rc(agent_filename)).read()
            ),
            instead=instead,
        )

    def load_stonithd_metadata(
        self,
        name="runner.pcmk.load_stonithd_metadata",
        stdout=None,
        stderr="",
        returncode=0,
        instead=None,
        before=None,
    ):
        """
        Create a call for loading stonithd metadata - additional fence options

        string name -- the key of this call
        string stdout -- stonithd stdout, default metadata if None
        string stderr -- stonithd stderr
        int returncode -- stonithd returncode
        string instead -- the key of a call instead of which this new call is to
            be placed
        string before -- the key of a call before which this new call is to be
            placed
        """
        self.__calls.place(
            name,
            RunnerCall(
                "/usr/libexec/pacemaker/stonithd metadata",
                stdout=(
                    stdout if stdout is not None
                    else open(rc("stonithd_metadata.xml")).read()
                ),
                stderr=stderr,
                returncode=returncode
            ),
            before=before,
            instead=instead,
        )

    def resource_cleanup(
        self,
        name="runner.pcmk.cleanup",
        instead=None,
        before=None,
        resource=None,
        node=None,
        stdout="",
        stderr="",
        returncode=0
    ):
        """
        Create a call for crm_resource --cleanup

        string name -- the key of this call
        string instead -- the key of a call instead of which this new call is to
            be placed
        string before -- the key of a call before which this new call is to be
            placed
        string resource -- the id of a resource to be cleaned
        string node -- the name of the node where resources should be cleaned
        string stdout -- crm_resource's stdout
        string stderr -- crm_resource's stderr
        int returncode -- crm_resource's returncode
        """
        cmd = ["crm_resource", "--cleanup"]
        if resource:
            cmd.extend(["--resource", resource])
        if node:
            cmd.extend(["--node", node])
        self.__calls.place(
            name,
            RunnerCall(
                " ".join(cmd),
                stdout=stdout,
                stderr=stderr,
                returncode=returncode
            ),
            before=before,
            instead=instead,
        )

    def wait(
        self, name="runner.pcmk.wait", stderr="", returncode=None, timeout=None
    ):
        """
        Create call for waiting to pacemaker idle

        string name -- key of the call
        string stderr -- stderr of wait command
        int returncode -- has default value 0 if stderr is empty and has default
            configured value (62) if stderr is not empty. However the explicitly
            specified returncode is used if the returncode is specified.
        """
        if returncode is None:
            returncode = self.default_wait_error_returncode if stderr else 0

        self.__calls.place(
            name,
            RunnerCall(
                "crm_resource --wait --timeout={0}".format(
                    timeout if timeout else self.default_wait_timeout
                ),
                stderr=stderr,
                returncode=returncode,
            )
        )

    def can_wait(
        self, name="runner.pcmk.can_wait", before=None, stdout="--wait"
    ):
        """
        Create call that checks that wait for idle is supported

        string name -- key of the call
        string before -- key of call before which this new call is to be placed
        """
        self.__calls.place(
            name,
            RunnerCall("crm_resource -?", stdout=stdout),
            before=before
        )

    def verify(self, name="verify", cib_tempfile=None, stderr=None, verbose=False):
        """
        Create call that checks that wait for idle is supported

        string name -- key of the call
        string before -- key of call before which this new call is to be placed
        """
        self.__calls.place(
            name,
            RunnerCall(
                "crm_verify{0} {1}".format(
                    " -V" if verbose else "",
                    "--xml-file {0}".format(cib_tempfile) if cib_tempfile
                        else "--live-check"
                ),
                stderr=("" if stderr is None else stderr),
                returncode=(0 if stderr is None else 55),
            ),
        )

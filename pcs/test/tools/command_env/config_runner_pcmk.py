from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.integration_lib import Call
from pcs.test.tools.xml import etree_to_str
import pcs.lib.commands.test.resource.fixture as fixture

DEFAULT_WAIT_TIMEOUT = 10
DEFAULT_WAIT_ERROR_RETURNCODE = 62

class PcmkShortcuts(object):
    def __init__(self, calls):
        self.__calls = calls
        self.default_wait_timeout = DEFAULT_WAIT_TIMEOUT
        self.default_wait_error_returncode = DEFAULT_WAIT_ERROR_RETURNCODE

    def load_state(
        self, name="load_state", filename="crm_mon.minimal.xml", resources=None
    ):
        """
        Create call for loading pacemaker state.

        string name -- key of the call
        string filename -- points to file with the status in the content
        string resources -- xml - resources section, will be put to state
        """
        state = etree.fromstring(open(rc(filename)).read())
        if resources:
            state.append(
                fixture.complete_state_resources(etree.fromstring(resources))
            )

        self.__calls.place(
            name,
            Call(
                "crm_mon --one-shot --as-xml --inactive",
                stdout=etree_to_str(state),
            )
        )

    def load_agent(
        self,
        name="load_agent",
        agent_name="ocf:heartbeat:Dummy",
        agent_filename="resource_agent_ocf_heartbeat_dummy.xml",
    ):
        """
        Create call for loading resource agent metadata.

        string name -- key of the call
        string agent_name
        string agent_filename -- points to file with the agent metadata in the
            content
        """
        self.__calls.place(
            name,
            Call(
                "crm_resource --show-metadata {0}".format(agent_name),
                stdout=open(rc(agent_filename)).read()
            )
        )


    def wait(self, name="wait", stderr="", returncode=None, timeout=None):
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
            Call(
                "crm_resource --wait --timeout={0}".format(
                    timeout if timeout else self.default_wait_timeout
                ),
                stderr=stderr,
                returncode=returncode,
            )
        )

    def can_wait(self, name="can_wait", before=None):
        """
        Create call that checks that wait for idle is supported

        string name -- key of the call
        string before -- key of call before which this new call is to be placed
        """
        self.__calls.place(
            name,
            Call("crm_resource -?", stdout="--wait"),
            before=before
        )

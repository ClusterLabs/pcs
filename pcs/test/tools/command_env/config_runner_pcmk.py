import os

from lxml import etree

from pcs.test.tools.command_env.mock_runner import Call as RunnerCall
from pcs.test.tools.fixture import complete_state_resources
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.xml import etree_to_str

# pylint: disable=invalid-name, redefined-builtin, unused-argument, too-many-arguments, too-many-locals, too-many-boolean-expressions

DEFAULT_WAIT_TIMEOUT = 10
WAIT_TIMEOUT_EXPIRED_RETURNCODE = 124
AGENT_FILENAME_MAP = {
    "ocf:heartbeat:Dummy": "resource_agent_ocf_heartbeat_dummy.xml",
    "ocf:pacemaker:remote": "resource_agent_ocf_pacemaker_remote.xml",
}

def fixture_state_resources_xml(
    resource_id="A", resource_agent="ocf::heartbeat:Dummy", role="Started",
    failed="false", node_name="node1"
):
    return(
        """
        <resources>
            <resource
                id="{resource_id}"
                resource_agent="{resource_agent}"
                role="{role}"
                failed="{failed}"
            >
                <node name="{node_name}" id="1" cached="false"/>
            </resource>
        </resources>
        """.format(
            resource_id=resource_id,
            resource_agent=resource_agent,
            role=role,
            failed=failed,
            node_name=node_name,
        )
    )

def fixture_state_node_xml(
    id, name, type="member", online=True, standby=False, standby_onfail=False,
    maintenance=False, pending=False, unclean=False, shutdown=False,
    expected_up=True, is_dc=False, resources_running=0
):
    attrs = locals()
    xml_attrs = []
    for attr_name, attr_value in attrs.items():
        if attr_value is True:
            attr_value = "true"
        elif attr_value is False:
            attr_value = "false"
        xml_attrs.append('{0}="{1}"'.format(attr_name, attr_value))
    return "<node {0}/>".format(" ".join(xml_attrs))


class PcmkShortcuts():
    def __init__(self, calls):
        self.__calls = calls
        self.default_wait_timeout = DEFAULT_WAIT_TIMEOUT
        self.default_wait_error_returncode = WAIT_TIMEOUT_EXPIRED_RETURNCODE

    def fence_history_get(
        self, name="runner.pcmk.fence_history_get", node=None, stdout="",
        stderr="", returncode=0
    ):
        """
        Create call for getting plain text fencing history.

        string name -- key of the call
        string node -- a node to get a history from
        string stdout -- pacemaker's stdout
        string stderr -- pacemaker's stderr
        int returncode -- pacemaker's returncode
        """
        self.__calls.place(
            name,
            RunnerCall(
                "/usr/sbin/stonith_admin --history {0} --verbose".format(node),
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def fence_history_cleanup(
        self, name="runner.pcmk.fence_history_cleanup", node=None, stdout="",
        stderr="", returncode=0
    ):
        """
        Create call for cleaning fencing history up.

        string name -- key of the call
        string node -- a node to clean a history from
        string stdout -- pacemaker's stdout
        string stderr -- pacemaker's stderr
        int returncode -- pacemaker's returncode
        """
        self.__calls.place(
            name,
            RunnerCall(
                "/usr/sbin/stonith_admin --history {0} --cleanup".format(node),
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def fence_history_update(
        self, name="runner.pcmk.fence_history_update", stdout="", stderr="",
        returncode=0
    ):
        """
        Create call for updating fencing history.

        string name -- key of the call
        string stdout -- pacemaker's stdout
        string stderr -- pacemaker's stderr
        int returncode -- pacemaker's returncode
        """
        self.__calls.place(
            name,
            RunnerCall(
                "/usr/sbin/stonith_admin --history * --broadcast",
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def load_state(
        self, name="runner.pcmk.load_state", filename="crm_mon.minimal.xml",
        resources=None, raw_resources=None, nodes=None, stdout="", stderr="",
        returncode=0
    ):
        """
        Create call for loading pacemaker state.

        string name -- key of the call
        string filename -- points to file with the status in the content
        string resources -- xml - resources section, will be put to state
        string nodes -- iterable of node dicts
        string stdout -- crm_mon's stdout
        string stderr -- crm_mon's stderr
        int returncode -- crm_mon's returncode
        """
        if (
            (resources or raw_resources is not None or nodes)
            and
            (stdout or stderr or returncode)
        ):
            raise AssertionError(
                "Cannot specify resources or nodes when stdout, stderr or "
                "returncode is specified"
            )
        if resources and raw_resources is not None:
            raise AssertionError(
                "Cannot use 'resources' and 'raw_resources' together"
            )

        if (stdout or stderr or returncode):
            self.__calls.place(
                name,
                RunnerCall(
                    "crm_mon --one-shot --as-xml --inactive",
                    stdout=stdout,
                    stderr=stderr,
                    returncode=returncode
                )
            )
            return

        state = etree.fromstring(open(rc(filename)).read())

        if raw_resources is not None:
            resources = fixture_state_resources_xml(**raw_resources)
        if resources:
            state.append(complete_state_resources(etree.fromstring(resources)))

        if nodes:
            nodes_element = state.find("./nodes")
            for node in nodes:
                nodes_element.append(
                    etree.fromstring(fixture_state_node_xml(**node))
                )

        # set correct number of nodes and resources into the status
        resources_count = len(state.xpath(" | ".join([
            "./resources/bundle",
            "./resources/clone",
            "./resources/group",
            "./resources/resource",
        ])))
        nodes_count = len(state.findall("./nodes/node"))
        state.find("./summary/nodes_configured").set("number", str(nodes_count))
        state.find("./summary/resources_configured").set(
            "number", str(resources_count)
        )

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
        agent_filename=None,
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

        if agent_filename:
            agent_metadata_filename = agent_filename
        elif agent_name in AGENT_FILENAME_MAP:
            agent_metadata_filename = AGENT_FILENAME_MAP[agent_name]
        else:
            raise AssertionError((
                "Filename with metadata of agent '{0}' not specified.\n"
                "Please specify file with metadata for agent:\n"
                "  a) explicitly for this test:"
                " config.runner.pcmk.load_agent(agent_name='{0}',"
                " filename='FILENAME_HERE.xml')\n"
                "  b) implicitly for agent '{0}' in 'AGENT_FILENAME_MAP' in"
                " '{1}'\n"
                "Place agent metadata into '{2}FILENAME_HERE.xml'"
            ).format(agent_name, os.path.realpath(__file__), rc("")))

        self.__calls.place(
            name,
            RunnerCall(
                "crm_resource --show-metadata {0}".format(agent_name),
                stdout=open(rc(agent_metadata_filename)).read()
            ),
            instead=instead,
        )

    def load_fenced_metadata(
        self,
        name="runner.pcmk.load_fenced_metadata",
        stdout=None,
        stderr="",
        returncode=0,
        instead=None,
        before=None,
    ):
        """
        Create a call for loading fenced metadata - additional fence options

        string name -- the key of this call
        string stdout -- fenced stdout, default metadata if None
        string stderr -- fenced stderr
        int returncode -- fenced returncode
        string instead -- the key of a call instead of which this new call is to
            be placed
        string before -- the key of a call before which this new call is to be
            placed
        """
        self.__calls.place(
            name,
            RunnerCall(
                "/usr/libexec/pacemaker/pacemaker-fenced metadata",
                stdout=(
                    stdout if stdout is not None
                    else open(rc("fenced_metadata.xml")).read()
                ),
                stderr=stderr,
                returncode=returncode
            ),
            before=before,
            instead=instead,
        )

    def local_node_name(
        self, name="runner.pcmk.local_node_name", instead=None, before=None,
        node_name="", stdout="", stderr="", returncode=0
    ):
        """
        Create a call for crm_node --name

        string name -- the key of this call
        string instead -- the key of a call instead of which this new call is to
            be placed
        string before -- the key of a call before which this new call is to be
            placed
        string node_name -- resulting node name
        string stdout -- crm_node's stdout
        string stderr -- crm_node's stderr
        int returncode -- crm_node's returncode
        """
        if node_name and (stdout or stderr or returncode):
            raise AssertionError(
                "Cannot specify node_name when stdout, stderr or returncode is "
                "specified"
            )
        cmd = ["crm_node", "--name"]
        self.__calls.place(
            name,
            RunnerCall(
                " ".join(cmd),
                stdout=(node_name if node_name else stdout),
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

    def resource_move(
        self,
        name="runner.pcmk.resource_move",
        instead=None,
        before=None,
        resource=None,
        node=None,
        master=None,
        lifetime=None,
        stdout="",
        stderr="",
        returncode=0
    ):
        """
        Create a call for crm_resource --move

        string name -- the key of this call
        string instead -- the key of a call instead of which this new call is to
            be placed
        string before -- the key of a call before which this new call is to be
            placed
        string resource -- the id of a resource to be moved
        string node -- the name of a destination node
        bool master -- limit move to master role
        string lifetime -- lifetime of the created moving constraint
        string stdout -- crm_resource's stdout
        string stderr -- crm_resource's stderr
        int returncode -- crm_resource's returncode
        """
        all_args = locals()
        del all_args["self"]
        all_args["action"] = "--move"
        self._resource_move_ban_clear(**all_args)

    def resource_ban(
        self,
        name="runner.pcmk.resource_ban",
        instead=None,
        before=None,
        resource=None,
        node=None,
        master=None,
        lifetime=None,
        stdout="",
        stderr="",
        returncode=0
    ):
        """
        Create a call for crm_resource --ban

        string name -- the key of this call
        string instead -- the key of a call instead of which this new call is to
            be placed
        string before -- the key of a call before which this new call is to be
            placed
        string resource -- the id of a resource to be banned
        string node -- the name of a destination node
        bool master -- limit ban to master role
        string lifetime -- lifetime of the created banning constraint
        string stdout -- crm_resource's stdout
        string stderr -- crm_resource's stderr
        int returncode -- crm_resource's returncode
        """
        all_args = locals()
        del all_args["self"]
        all_args["action"] = "--ban"
        self._resource_move_ban_clear(**all_args)

    def resource_clear(
        self,
        name="runner.pcmk.resource_clear",
        instead=None,
        before=None,
        resource=None,
        node=None,
        master=None,
        expired=None,
        stdout="",
        stderr="",
        returncode=0
    ):
        """
        Create a call for crm_resource --clear

        string name -- the key of this call
        string instead -- the key of a call instead of which this new call is to
            be placed
        string before -- the key of a call before which this new call is to be
            placed
        string resource -- the id of a resource to be unmoved/unbanned
        string node -- the name of a destination node
        bool master -- limit clearing to master role
        bool epired -- clear only expired moves and bans
        string stdout -- crm_resource's stdout
        string stderr -- crm_resource's stderr
        int returncode -- crm_resource's returncode
        """
        all_args = locals()
        del all_args["self"]
        all_args["action"] = "--clear"
        self._resource_move_ban_clear(**all_args)

    def _resource_move_ban_clear(
        self,
        name,
        action,
        instead=None,
        before=None,
        resource=None,
        node=None,
        master=None,
        lifetime=None,
        expired=None,
        stdout="",
        stderr="",
        returncode=0
    ):
        cmd = ["crm_resource", action]
        if resource:
            cmd.extend(["--resource", resource])
        if node:
            cmd.extend(["--node", node])
        if master:
            cmd.extend(["--master"])
        if lifetime:
            cmd.extend(["--lifetime", lifetime])
        if expired:
            cmd.extend(["--expired"])
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

    def can_clear_expired(
        self, name="runner.pcmk.can_clear_expired", stderr="--expired"
    ):
        """
        Create call which check --expired is supported by crm_resource

        string name -- key of the call
        string stderr -- crm_resource help text
        """
        self.__calls.place(
            name,
            RunnerCall("crm_resource -?", stderr=stderr),
        )

    def wait(
        self, name="runner.pcmk.wait", stderr="", returncode=None, timeout=None
    ):
        """
        Create call for waiting to pacemaker idle

        string name -- key of the call
        string stderr -- stderr of wait command
        int returncode -- returncode of the wait command, defaults to 0 if
            stderr is empty and to 124 if stderr is not empty
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

    def verify(
        self, name="runner.pcmk.verify", cib_tempfile=None, stderr=None,
        verbose=False
    ):
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

    def remove_node(
        self, node_name,
        stderr="", returncode=0, name="runner.pcmk.remove_node",
    ):
        self.__calls.place(
            name,
            RunnerCall(
                "crm_node --force --remove {0}".format(node_name),
                stderr=stderr,
                returncode=returncode,
            ),
        )

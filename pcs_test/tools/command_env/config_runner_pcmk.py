import os

from lxml import etree

from pcs_test.tools.command_env.mock_runner import (
    Call as RunnerCall,
    CheckStdinEqualXml,
)
from pcs_test.tools.fixture import complete_state_resources
from pcs_test.tools.fixture_cib import modify_cib
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import etree_to_str

from pcs import settings

# pylint: disable=too-many-arguments

DEFAULT_WAIT_TIMEOUT = 10
WAIT_TIMEOUT_EXPIRED_RETURNCODE = 124
AGENT_FILENAME_MAP = {
    "ocf:heartbeat:Dummy": "resource_agent_ocf_heartbeat_dummy.xml",
    "ocf:pacemaker:remote": "resource_agent_ocf_pacemaker_remote.xml",
    "ocf:heartbeat:IPaddr2": "resource_agent_ocf_heartbeat_ipaddr2.xml",
    "ocf:pacemaker:booth-site": "resource_agent_ocf_pacemaker_booth-site.xml",
}


def _fixture_state_resources_xml(
    resource_id="A",
    resource_agent="ocf::heartbeat:Dummy",
    role="Started",
    failed="false",
    node_name="node1",
):
    return """
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


def _fixture_state_node_xml(
    id,
    name,
    type="member",
    online=True,
    standby=False,
    standby_onfail=False,
    maintenance=False,
    pending=False,
    unclean=False,
    shutdown=False,
    expected_up=True,
    is_dc=False,
    resources_running=0,
):
    # This function uses a "clever" way of defaulting an input **dict containing
    # attributes of an xml element.
    # pylint: disable=unused-argument
    # pylint: disable=invalid-name
    # pylint: disable=redefined-builtin
    # pylint: disable=too-many-locals
    attrs = locals()
    xml_attrs = []
    for attr_name, attr_value in attrs.items():
        if attr_value is True:
            attr_value = "true"
        elif attr_value is False:
            attr_value = "false"
        xml_attrs.append('{0}="{1}"'.format(attr_name, attr_value))
    return "<node {0}/>".format(" ".join(xml_attrs))


class PcmkShortcuts:
    # pylint: disable=too-many-public-methods
    def __init__(self, calls):
        self.__calls = calls
        self.default_wait_timeout = DEFAULT_WAIT_TIMEOUT
        self.default_wait_error_returncode = WAIT_TIMEOUT_EXPIRED_RETURNCODE

    def can_fence_history_manage(
        self,
        name="runner.pcmk.can_fence_history_manage",
        stderr="--history --cleanup --broadcast",
        instead=None,
    ):
        """
        Create a call to check if fence_history is supported by stonith_admin

        string name -- key of the call
        string stderr -- stonith_admin help text
        string instead -- key of call instead of which this new call is to be
            placed
        """
        self.__calls.place(
            name,
            RunnerCall(["stonith_admin", "--help-all"], stderr=stderr),
            instead=instead,
        )

    def can_fence_history_status(
        self,
        name="runner.pcmk.can_fence_history_status",
        stderr="--fence-history",
        instead=None,
    ):
        """
        Create a call to check if fence_history is supported by crm_mon

        string name -- key of the call
        string stderr -- crm_mon help text
        string instead -- key of call instead of which this new call is to be
            placed
        """
        self.__calls.place(
            name,
            RunnerCall(["crm_mon", "--help-all"], stderr=stderr),
            instead=instead,
        )

    def fence_history_get(
        self,
        name="runner.pcmk.fence_history_get",
        node=None,
        stdout="",
        stderr="",
        returncode=0,
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
                ["stonith_admin", "--history", node, "--verbose"],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def fence_history_cleanup(
        self,
        name="runner.pcmk.fence_history_cleanup",
        node=None,
        stdout="",
        stderr="",
        returncode=0,
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
                ["stonith_admin", "--history", node, "--cleanup"],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def fence_history_update(
        self,
        name="runner.pcmk.fence_history_update",
        stdout="",
        stderr="",
        returncode=0,
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
                ["stonith_admin", "--history", "*", "--broadcast"],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def load_state(
        self,
        name="runner.pcmk.load_state",
        filename="crm_mon.minimal.xml",
        resources=None,
        raw_resources=None,
        nodes=None,
        stdout="",
        stderr="",
        returncode=0,
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
        # pylint: disable=too-many-boolean-expressions
        if (resources or raw_resources is not None or nodes) and (
            stdout or stderr or returncode
        ):
            raise AssertionError(
                "Cannot specify resources or nodes when stdout, stderr or "
                "returncode is specified"
            )
        if resources and raw_resources is not None:
            raise AssertionError(
                "Cannot use 'resources' and 'raw_resources' together"
            )

        if stdout or stderr or returncode:
            self.__calls.place(
                name,
                RunnerCall(
                    ["crm_mon", "--one-shot", "--as-xml", "--inactive"],
                    stdout=stdout,
                    stderr=stderr,
                    returncode=returncode,
                ),
            )
            return

        with open(rc(filename)) as a_file:
            state = etree.fromstring(a_file.read())

        if raw_resources is not None:
            resources = _fixture_state_resources_xml(**raw_resources)
        if resources:
            state.append(complete_state_resources(etree.fromstring(resources)))

        if nodes:
            nodes_element = state.find("./nodes")
            for node in nodes:
                nodes_element.append(
                    etree.fromstring(_fixture_state_node_xml(**node))
                )

        # set correct number of nodes and resources into the status
        resources_count = len(
            state.xpath(
                " | ".join(
                    [
                        "./resources/bundle",
                        "./resources/clone",
                        "./resources/group",
                        "./resources/resource",
                    ]
                )
            )
        )
        nodes_count = len(state.findall("./nodes/node"))
        state.find("./summary/nodes_configured").set("number", str(nodes_count))
        state.find("./summary/resources_configured").set(
            "number", str(resources_count)
        )

        self.__calls.place(
            name,
            RunnerCall(
                ["crm_mon", "--one-shot", "--as-xml", "--inactive"],
                stdout=etree_to_str(state),
            ),
        )

    def load_state_plaintext(
        self,
        name="runner.pcmk.load_state_plaintext",
        inactive=True,
        verbose=False,
        fence_history=False,
        stdout="",
        stderr="",
        returncode=0,
    ):
        """
        Create a call for loading plaintext pacemaker status

        str name -- key of the call
        bool incative -- pass --inactive flag to crm_mon
        bool verbose -- pass flags for increased verbosity to crm_mon
        bool fence_history -- pass the flag for getting fence history to crm_mon
        str stdout -- crm_mon's stdout
        str stderr -- crm_mon's stderr
        int returncode -- crm_mon's returncode
        """
        flags = ["--one-shot"]
        if inactive:
            flags.append("--inactive")
        if verbose:
            flags.extend(
                ["--show-detail", "--show-node-attributes", "--failcounts"]
            )
            if fence_history:
                flags.append("--fence-history=3")
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_mon"] + flags,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def load_ticket_state_plaintext(
        self,
        name="runner.pcmk.load_ticket_state_plaintext",
        stdout="",
        stderr="",
        returncode=0,
    ):
        """
        Create a call for loading plaintext tickets status

        str name -- key of the call
        str stdout -- crm_ticket's stdout
        str stderr -- crm_ticket's stderr
        int returncode -- crm_ticket's returncode
        """
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_ticket", "--details"],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def load_agent(
        self,
        name="runner.pcmk.load_agent",
        agent_name="ocf:heartbeat:Dummy",
        agent_filename=None,
        agent_is_missing=False,
        stderr=None,
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
        elif not agent_is_missing:
            raise AssertionError(
                (
                    "Filename with metadata of agent '{0}' not specified.\n"
                    "Please specify file with metadata for agent:\n"
                    "  a) explicitly for this test:"
                    " config.runner.pcmk.load_agent(agent_name='{0}',"
                    " filename='FILENAME_HERE.xml')\n"
                    "  b) implicitly for agent '{0}' in 'AGENT_FILENAME_MAP' in"
                    " '{1}'\n"
                    "Place agent metadata into '{2}FILENAME_HERE.xml'"
                ).format(agent_name, os.path.realpath(__file__), rc(""))
            )

        if agent_is_missing:
            if stderr is None:
                stderr = (
                    f"Agent {agent_name} not found or does not support "
                    "meta-data: Invalid argument (22)\n"
                    f"Metadata query for {agent_name} failed: Input/output "
                    "error\n"
                )
            self.__calls.place(
                name,
                RunnerCall(
                    ["crm_resource", "--show-metadata", agent_name],
                    stdout="",
                    stderr=stderr,
                    returncode=74,
                ),
                instead=instead,
            )
            return

        with open(rc(agent_metadata_filename)) as a_file:
            self.__calls.place(
                name,
                RunnerCall(
                    ["crm_resource", "--show-metadata", agent_name],
                    stdout=a_file.read(),
                    stderr=stderr,
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
        if stdout is None:
            with open(rc("fenced_metadata.xml")) as a_file:
                stdout = a_file.read()
        self.__calls.place(
            name,
            RunnerCall(
                [settings.pacemaker_fenced, "metadata"],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
            before=before,
            instead=instead,
        )

    def local_node_name(
        self,
        name="runner.pcmk.local_node_name",
        instead=None,
        before=None,
        node_name="",
        stdout="",
        stderr="",
        returncode=0,
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
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_node", "--name"],
                stdout=(node_name if node_name else stdout),
                stderr=stderr,
                returncode=returncode,
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
        strict=False,
        stdout="",
        stderr="",
        returncode=0,
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
        bool strict -- strict mode of 'crm_resource cleanup' enabled?
        string stdout -- crm_resource's stdout
        string stderr -- crm_resource's stderr
        int returncode -- crm_resource's returncode
        """
        cmd = ["crm_resource", "--cleanup"]
        if resource:
            cmd.extend(["--resource", resource])
        if node:
            cmd.extend(["--node", node])
        if strict:
            cmd.extend(["--force"])
        self.__calls.place(
            name,
            RunnerCall(
                cmd, stdout=stdout, stderr=stderr, returncode=returncode,
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
        main=None,
        lifetime=None,
        stdout="",
        stderr="",
        returncode=0,
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
        bool main -- limit move to main role
        string lifetime -- lifetime of the created moving constraint
        string stdout -- crm_resource's stdout
        string stderr -- crm_resource's stderr
        int returncode -- crm_resource's returncode
        """
        # arguments are used via locals()
        # pylint: disable=unused-argument
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
        main=None,
        lifetime=None,
        stdout="",
        stderr="",
        returncode=0,
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
        bool main -- limit ban to main role
        string lifetime -- lifetime of the created banning constraint
        string stdout -- crm_resource's stdout
        string stderr -- crm_resource's stderr
        int returncode -- crm_resource's returncode
        """
        # arguments are used via locals()
        # pylint: disable=unused-argument
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
        main=None,
        expired=None,
        stdout="",
        stderr="",
        returncode=0,
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
        bool main -- limit clearing to main role
        bool epired -- clear only expired moves and bans
        string stdout -- crm_resource's stdout
        string stderr -- crm_resource's stderr
        int returncode -- crm_resource's returncode
        """
        # arguments are used via locals()
        # pylint: disable=unused-argument
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
        main=None,
        lifetime=None,
        expired=None,
        stdout="",
        stderr="",
        returncode=0,
    ):
        cmd = ["crm_resource", action]
        if resource:
            cmd.extend(["--resource", resource])
        if node:
            cmd.extend(["--node", node])
        if main:
            cmd.extend(["--main"])
        if lifetime:
            cmd.extend(["--lifetime", lifetime])
        if expired:
            cmd.extend(["--expired"])
        self.__calls.place(
            name,
            RunnerCall(
                cmd, stdout=stdout, stderr=stderr, returncode=returncode,
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
            name, RunnerCall(["crm_resource", "-?"], stderr=stderr),
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
                [
                    "crm_resource",
                    "--wait",
                    "--timeout={0}".format(
                        timeout
                        if timeout is not None
                        else self.default_wait_timeout
                    ),
                ],
                stderr=stderr,
                returncode=returncode,
            ),
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
            RunnerCall(["crm_resource", "-?"], stdout=stdout),
            before=before,
        )

    def verify(
        self,
        name="runner.pcmk.verify",
        cib_tempfile=None,
        stderr=None,
        verbose=False,
    ):
        """
        Create call that checks that wait for idle is supported

        string name -- key of the call
        string before -- key of call before which this new call is to be placed
        """
        cmd = ["crm_verify"]
        if verbose:
            cmd.extend(["-V", "-V"])
        if cib_tempfile:
            cmd.extend(["--xml-file", cib_tempfile])
        else:
            cmd.append("--live-check")
        self.__calls.place(
            name,
            RunnerCall(
                cmd,
                stderr=("" if stderr is None else stderr),
                returncode=(0 if stderr is None else 55),
            ),
        )

    def remove_node(
        self,
        node_name,
        stderr="",
        returncode=0,
        name="runner.pcmk.remove_node",
    ):
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_node", "--force", "--remove", node_name],
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def simulate_cib(
        self,
        new_cib_filepath,
        transitions_filepath,
        cib_modifiers=None,
        cib_load_name="runner.cib.load",
        stdout="",
        stderr="",
        returncode=0,
        name="runner.pcmk.simulate_cib",
        **modifier_shortcuts,
    ):
        """
        Create a call for simulating effects of cib changes

        string new_cib_filepath -- a temp file for storing a new cib
        string transitions_filepath -- a temp file for storing transitions
        list of callable modifiers -- every callable takes etree.Element and
            returns new etree.Element with desired modification
        string cib_load_name -- key of a call from whose stdout the cib is taken
        string stdout -- pacemaker's stdout
        string stderr -- pacemaker's stderr
        int returncode -- pacemaker's returncode
        string name -- key of the call
        dict modifier_shortcuts -- a new modifier is generated from each
            modifier shortcut.
            As key there can be keys of MODIFIER_GENERATORS.
            Value is passed into appropriate generator from MODIFIER_GENERATORS.
            For details see pcs_test.tools.fixture_cib (mainly the variable
            MODIFIER_GENERATORS - please refer it when you are adding params
            here)
        """
        cib_xml = modify_cib(
            self.__calls.get(cib_load_name).stdout,
            cib_modifiers,
            **modifier_shortcuts,
        )
        cmd = [
            "crm_simulate",
            "--simulate",
            "--save-output",
            new_cib_filepath,
            "--save-graph",
            transitions_filepath,
            "--xml-pipe",
        ]
        self.__calls.place(
            name,
            RunnerCall(
                cmd,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                check_stdin=CheckStdinEqualXml(cib_xml),
            ),
        )

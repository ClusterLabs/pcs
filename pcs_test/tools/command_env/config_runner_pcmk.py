import os
from typing import Optional

from pcs import settings

from pcs_test.tools.command_env.mock_runner import Call as RunnerCall
from pcs_test.tools.command_env.mock_runner import CheckStdinEqualXml
from pcs_test.tools.fixture_cib import modify_cib
from pcs_test.tools.fixture_crm_mon import complete_state
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import etree_to_str

DEFAULT_WAIT_TIMEOUT = 10
WAIT_TIMEOUT_EXPIRED_RETURNCODE = 124
AGENT_FILENAME_MAP = {
    "ocf:heartbeat:Dummy": "resource_agent_ocf_heartbeat_dummy.xml",
    "ocf:pacemaker:Dummy": "resource_agent_ocf_pacemaker_dummy.xml",
    "ocf:pacemaker:remote": "resource_agent_ocf_pacemaker_remote.xml",
    "ocf:heartbeat:IPaddr2": "resource_agent_ocf_heartbeat_ipaddr2.xml",
    "ocf:pacemaker:booth-site": "resource_agent_ocf_pacemaker_booth-site.xml",
    "ocf:pacemaker:Stateful": "resource_agent_ocf_pacemaker_stateful_ocf_1.1.xml",
    "systemd:chronyd": "resource_agent_systemd_chronyd.xml",
    "stonith:fence_unfencing": "stonith_agent_fence_unfencing.xml",
}

RULE_IN_EFFECT_RETURNCODE = 0
RULE_EXPIRED_RETURNCODE = 110
RULE_NOT_YET_IN_EFFECT_RETURNCODE = 111


class PcmkShortcuts:
    # pylint: disable=too-many-arguments
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
        env=None,
    ):
        """
        Create a call to check if fence_history is supported by crm_mon

        string name -- key of the call
        string stderr -- crm_mon help text
        string instead -- key of call instead of which this new call is to be
            placed
        dict env -- CommandRunner environment variables
        """
        self.__calls.place(
            name,
            RunnerCall(["crm_mon", "--help-all"], stderr=stderr, env=env),
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
        *,
        name="runner.pcmk.load_state",
        filename="crm_mon.minimal.xml",
        resources=None,
        nodes=None,
        stdout="",
        stderr="",
        returncode=0,
        env=None,
    ):
        """
        Create call for loading pacemaker state.

        string name -- key of the call
        string filename -- points to file with the status in the content
        string resources -- xml - resources section, will be put to state
        string nodes -- xml - nodes section, will be put to state
        string stdout -- crm_mon's stdout
        string stderr -- crm_mon's stderr
        int returncode -- crm_mon's returncode
        dict env -- CommandRunner environment variables
        """
        if (resources or nodes) and (stdout or stderr or returncode):
            raise AssertionError(
                "Cannot specify resources or nodes when stdout, stderr or "
                "returncode is specified"
            )

        command = ["crm_mon", "--one-shot", "--inactive", "--output-as", "xml"]

        if stdout or stderr or returncode:
            self.__calls.place(
                name,
                RunnerCall(
                    command,
                    stdout=stdout,
                    stderr=stderr,
                    returncode=returncode,
                    env=env,
                ),
            )
            return

        with open(rc(filename)) as a_file:
            state_xml = a_file.read()

        self.__calls.place(
            name,
            RunnerCall(
                command,
                stdout=etree_to_str(
                    complete_state(state_xml, resources, nodes)
                ),
                env=env,
            ),
        )

    def load_state_plaintext(
        self,
        *,
        name="runner.pcmk.load_state_plaintext",
        inactive=True,
        verbose=False,
        fence_history=False,
        stdout="",
        stderr="",
        returncode=0,
        env=None,
    ):
        """
        Create a call for loading plaintext pacemaker status

        str name -- key of the call
        bool inactive -- pass --inactive flag to crm_mon
        bool verbose -- pass flags for increased verbosity to crm_mon
        bool fence_history -- pass the flag for getting fence history to crm_mon
        str stdout -- crm_mon's stdout
        str stderr -- crm_mon's stderr
        int returncode -- crm_mon's returncode
        dict env -- CommandRunner environment variables
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
                env=env,
            ),
        )

    def load_ticket_state_plaintext(
        self,
        name="runner.pcmk.load_ticket_state_plaintext",
        stdout="",
        stderr="",
        returncode=0,
        env=None,
    ):
        """
        Create a call for loading plaintext tickets status

        str name -- key of the call
        str stdout -- crm_ticket's stdout
        str stderr -- crm_ticket's stderr
        int returncode -- crm_ticket's returncode
        dict env -- CommandRunner environment variables
        """
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_ticket", "--details"],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                env=env,
            ),
        )

    def list_agents_standards(
        self,
        stdout="",
        stderr="",
        returncode=0,
        env=None,
        name="runner.pcmk.list_agents_standards",
    ):
        """
        Create a call for listing agents standards
        """
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_resource", "--list-standards"],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                env=env,
            ),
        )

    def list_agents_ocf_providers(
        self,
        stdout="",
        stderr="",
        returncode=0,
        env=None,
        name="runner.pcmk.list_agents_ocf_providers",
    ):
        """
        Create a call for listing agents ocf providers
        """
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_resource", "--list-ocf-providers"],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                env=env,
            ),
        )

    def list_agents_for_standard_and_provider(
        self,
        standard_provider,
        stdout="",
        stderr="",
        returncode=0,
        env=None,
        name="runner.pcmk.list_agents_for_standard_and_provider",
    ):
        """
        Create a call for listing agents of given standard and provider
        """
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_resource", "--list-agents", standard_provider],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                env=env,
            ),
        )

    def load_agent(
        self,
        *,
        name="runner.pcmk.load_agent",
        agent_name="ocf:heartbeat:Dummy",
        agent_filename=None,
        agent_is_missing=False,
        stdout=None,
        stderr=None,
        instead=None,
        env=None,
    ):
        """
        Create call for loading resource agent metadata.

        string name -- key of the call
        string agent_name
        string agent_filename -- points to file with the agent metadata in the
            content
        bool agent_is_missing -- create a response as if the agent was missing
        string instead -- key of call instead of which this new call is to be
            placed
        dict env -- CommandRunner environment variables
        """
        if (
            not agent_is_missing
            and not stdout
            and not agent_filename
            and agent_name not in AGENT_FILENAME_MAP
        ):
            raise AssertionError(
                (
                    "Filename with metadata of agent '{0}' not specified.\n"
                    "Please specify file with metadata for agent:\n"
                    "  a) explicitly for this test:"
                    " config.runner.pcmk.load_agent(agent_name='{0}',"
                    " filename='FILENAME_HERE.xml')\n"
                    "  b) implicitly for agent '{0}' in 'AGENT_FILENAME_MAP' in"
                    " '{1}'\n"
                    "Place agent metadata into '{2}FILENAME_HERE.xml'\n"
                    "Or define metadata directly in 'stdout' argument."
                ).format(agent_name, os.path.realpath(__file__), rc(""))
            )

        env = dict(env) if env else {}
        env["PATH"] = ":".join(
            [
                settings.fence_agent_execs,
                "/bin",
                "/usr/bin",
            ]
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
                    env=env,
                ),
                instead=instead,
            )
            return

        if not stdout:
            if agent_filename:
                agent_metadata_filename = agent_filename
            else:
                agent_metadata_filename = AGENT_FILENAME_MAP[agent_name]
            with open(rc(agent_metadata_filename)) as a_file:
                stdout = a_file.read()
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_resource", "--show-metadata", agent_name],
                stdout=stdout,
                stderr=stderr,
                env=env,
            ),
            instead=instead,
        )

    def load_fake_agent_metadata(
        self,
        name="runner.pcmk.load_fake_agent_metadata",
        agent_name="pacemaker-fenced",
        stdout=None,
        stderr="",
        returncode=0,
        instead=None,
        before=None,
    ):
        """
        Create a call for loading fake agent metadata - usually metadata
        provided by pacemaker daemon

        string name -- the key of this call
        string agent_name -- name of the fake agent
        string stdout -- fake agent stdout, default metadata if None
        string stderr -- fake agent stderr
        int returncode -- fake agent returncode
        string instead -- the key of a call instead of which this new call is to
            be placed
        string before -- the key of a call before which this new call is to be
            placed
        """
        name_to_metadata_file = {
            "pacemaker-based": "based_metadata.xml",
            "pacemaker-controld": "controld_metadata.xml",
            "pacemaker-fenced": "fenced_metadata.xml",
            "pacemaker-schedulerd": "schedulerd_metadata.xml",
        }
        if stdout is None:
            with open(rc(name_to_metadata_file[agent_name])) as a_file:
                stdout = a_file.read()
        agent_path = settings.__dict__[agent_name.replace("-", "_") + "_exec"]
        self.__calls.place(
            name,
            RunnerCall(
                [agent_path, "metadata"],
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

    def resource_restart(
        self,
        resource: str,
        node: Optional[str] = None,
        timeout: Optional[str] = None,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        name: str = "runner.pcmk.restart",
    ):
        """
        Create a call for crm_resource --restart

        name -- the key of this call
        resource -- the id of a resource to be restarted
        node -- the name of the node where the resource should be restarted
        timeout -- how long to wait for the resource to restart
        stdout -- crm_resource's stdout
        stderr -- crm_resource's stderr
        returncode -- crm_resource's returncode
        """
        cmd = ["crm_resource", "--restart"]
        if resource:
            cmd.extend(["--resource", resource])
        if node:
            cmd.extend(["--node", node])
        if timeout:
            cmd.extend(["--timeout", timeout])
        self.__calls.place(
            name,
            RunnerCall(
                cmd,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def resource_cleanup(  # noqa: PLR0913
        self,
        *,
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
                cmd,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
            before=before,
            instead=instead,
        )

    def resource_refresh(  # noqa: PLR0913
        self,
        *,
        name="runner.pcmk.refresh",
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
        Create a call for crm_resource --refresh

        string name -- the key of this call
        string instead -- the key of a call instead of which this new call is to
            be placed
        string before -- the key of a call before which this new call is to be
            placed
        string resource -- the id of a resource to be cleaned
        string node -- the name of the node where resources should be cleaned
        bool strict -- strict mode of 'crm_resource refresh' enabled?
        string stdout -- crm_resource's stdout
        string stderr -- crm_resource's stderr
        int returncode -- crm_resource's returncode
        """
        cmd = ["crm_resource", "--refresh"]
        if resource:
            cmd.extend(["--resource", resource])
        if node:
            cmd.extend(["--node", node])
        if strict:
            cmd.extend(["--force"])
        self.__calls.place(
            name,
            RunnerCall(
                cmd,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
            before=before,
            instead=instead,
        )

    def resource_move(  # noqa: PLR0913
        self,
        *,
        name="runner.pcmk.resource_move",
        instead=None,
        before=None,
        resource=None,
        node=None,
        master=None,
        lifetime=None,
        stdout="",
        stderr="",
        returncode=0,
        env=None,
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
        dict env -- CommandRunner environment variables
        """
        # arguments are used via locals()
        # pylint: disable=unused-argument
        all_args = locals()
        del all_args["self"]
        all_args["action"] = "--move"
        self._resource_move_ban_clear(**all_args)

    def resource_ban(  # noqa: PLR0913
        self,
        *,
        name="runner.pcmk.resource_ban",
        instead=None,
        before=None,
        resource=None,
        node=None,
        master=None,
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
        bool master -- limit ban to master role
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

    def resource_clear(  # noqa: PLR0913
        self,
        *,
        name="runner.pcmk.resource_clear",
        instead=None,
        before=None,
        resource=None,
        node=None,
        master=None,
        expired=None,
        stdout="",
        stderr="",
        returncode=0,
        env=None,
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
        dict env -- CommandRunner environment variables
        """
        # arguments are used via locals()
        # pylint: disable=unused-argument
        all_args = locals()
        del all_args["self"]
        all_args["action"] = "--clear"
        self._resource_move_ban_clear(**all_args)

    def _resource_move_ban_clear(  # noqa: PLR0913
        self,
        name,
        action,
        *,
        instead=None,
        before=None,
        resource=None,
        node=None,
        master=None,
        lifetime=None,
        expired=None,
        stdout="",
        stderr="",
        returncode=0,
        env=None,
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
                cmd,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                env=env,
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
            RunnerCall(["crm_resource", "--help-all"], stderr=stderr),
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

        cmd = ["crm_resource", "--wait"]
        if timeout != 0:
            cmd.append(
                "--timeout={0}".format(
                    timeout
                    if timeout is not None
                    else self.default_wait_timeout
                )
            )
        self.__calls.place(
            name,
            RunnerCall(cmd, stderr=stderr, returncode=returncode),
        )

    def is_resource_digests_supported(
        self,
        name="runner.pcmk.is_resource_digests_supported",
        is_supported=True,
    ):
        """
        Create call for `crm_resource --help-all`. If support_digest is True, option
        --digest is included in command output.

        name -- key of the call
        is_supported -- flags which decides if digests are supported
        """
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_resource", "--help-all"],
                stdout="--digests" if is_supported else "",
                stderr="",
                returncode=0,
            ),
        )

    def resource_digests(
        self,
        resource_id,
        node_name,
        name="runner.pcmk.resource_digests",
        args=None,
        stdout="",
        stderr="",
        returncode=0,
    ):
        """
        Create call for crm_resource digests

        resource_id -- id of a resource
        node_name -- name of the node where the resource is running
        name -- key of the call
        args -- additional arguments for crm_resource
        stdout -- crm_resource's stdout
        stderr -- crm_resource's stderr
        returncode -- crm_resource's returncode
        """
        if args is None:
            args = []

        self.__calls.place(
            name,
            RunnerCall(
                [
                    "crm_resource",
                    "--digests",
                    "--resource",
                    resource_id,
                    "--node",
                    node_name,
                    "--output-as",
                    "xml",
                    *args,
                ],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def verify(
        self,
        name="runner.pcmk.verify",
        cib_tempfile=None,
        stderr=None,
        verbose=False,
        env=None,
    ):
        """
        Create call that checks that wait for idle is supported

        string name -- key of the call
        string before -- key of call before which this new call is to be placed
        dict env -- CommandRunner environment variables
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
                env=env,
            ),
        )

    def remove_node(
        self,
        node_name,
        stderr="",
        returncode=0,
        name="runner.pcmk.remove_node",
        env=None,
    ):
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_node", "--force", "--remove", node_name],
                stderr=stderr,
                returncode=returncode,
                env=env,
            ),
        )

    def simulate_cib(  # noqa: PLR0913
        self,
        new_cib_filepath,
        transitions_filepath,
        *,
        cib_xml=None,
        cib_modifiers=None,
        cib_load_name="runner.cib.load",
        stdout="",
        stderr="",
        returncode=0,
        name="runner.pcmk.simulate_cib",
        env=None,
        **modifier_shortcuts,
    ):
        """
        Create a call for simulating effects of cib changes

        string new_cib_filepath -- a temp file for storing a new cib
        string transitions_filepath -- a temp file for storing transitions
        string cib_xml -- cib which will be used for a simulation
        list of callable modifiers -- every callable takes etree.Element and
            returns new etree.Element with desired modification
        string cib_load_name -- key of a call from whose stdout the cib is taken
        string stdout -- pacemaker's stdout
        string stderr -- pacemaker's stderr
        int returncode -- pacemaker's returncode
        string name -- key of the call
        dict env -- runner environment variables
        dict modifier_shortcuts -- a new modifier is generated from each
            modifier shortcut.
            As key there can be keys of MODIFIER_GENERATORS.
            Value is passed into appropriate generator from MODIFIER_GENERATORS.
            For details see pcs_test.tools.fixture_cib (mainly the variable
            MODIFIER_GENERATORS - please refer it when you are adding params
            here)
        """
        if cib_xml is None:
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
                env=env,
            ),
        )

    def get_rule_in_effect_status(
        self,
        rule_id,
        returncode=0,
        name="runner.pcmk.get_rule_in_effect_status",
        cib_load_name="runner.cib.load",
    ):
        """
        Create a call for running a tool to get rule expired status

        string rule_id -- id of the rule to be checked
        int returncode -- result of the check
        sting name -- key of the call
        string cib_load_name -- key of a call from whose stdout the cib is taken
        """
        cib_xml = self.__calls.get(cib_load_name).stdout
        self.__calls.place(
            name,
            RunnerCall(
                ["crm_rule", "--check", "--rule", rule_id, "--xml-text", "-"],
                check_stdin=CheckStdinEqualXml(cib_xml),
                stdout="",
                stderr="",
                returncode=returncode,
            ),
        )

    def resource_agent_self_validation(  # noqa: PLR0913
        self,
        attributes,
        standard="ocf",
        provider="heartbeat",
        agent_type="Dummy",
        *,
        returncode=0,
        output=None,
        stdout="",
        instead=None,
        env=None,
        name="runner.pcmk.resource_agent_self_validation",
    ):
        # pylint: disable=too-many-locals
        if output and stdout:
            raise AssertionError("Cannot specify both output and stdout")
        cmd = [
            "crm_resource",
            "--validate",
            "--output-as",
            "xml",
            "--class",
            standard,
            "--agent",
            agent_type,
        ]
        if provider:
            cmd.extend(["--provider", provider])
        for key, value in sorted(attributes.items()):
            cmd.extend(["--option", f"{key}={value}"])
        if output is not None:
            cmd_str = " ".join(cmd)
            provider_str = f' provider="{provider}"' if provider else ""
            stdout = f"""
            <pacemaker-result api-version="2.15" request="{cmd_str}">
              <resource-agent-action action="validate" class="{standard}" type="{agent_type}"{provider_str}>
                <overrides/>
                <agent-status code="5" message="not installed" execution_code="0" execution_message="complete" reason="environment is invalid, resource considered stopped"/>
                <command code="5">
                  {output}
                </command>
              </resource-agent-action>
              <status code="5" message="Not installed">
                <errors>
                  <error>crm_resource: Error performing operation: Not installed</error>
                </errors>
              </status>
            </pacemaker-result>
            """
        self.__calls.place(
            name,
            RunnerCall(cmd, stdout=stdout, returncode=returncode, env=env),
            instead=instead,
        )

    def stonith_agent_self_validation(
        self,
        attributes,
        agent,
        *,
        returncode=0,
        output=None,
        stdout="",
        instead=None,
        env=None,
        name="runner.pcmk.stonith_agent_self_validation",
    ):
        # pylint: disable=too-many-locals
        if output and stdout:
            raise AssertionError("Cannot specify both output and stdout")
        cmd = [
            "stonith_admin",
            "--validate",
            "--output-as",
            "xml",
            "--agent",
            agent,
        ]
        for key, value in sorted(attributes.items()):
            cmd.extend(["--option", f"{key}={value}"])
        if output is not None:
            cmd_str = " ".join(cmd)
            stdout = f"""
            <pacemaker-result api-version="2.22" request="{cmd_str}">
              <validate agent="{agent}" valid="false">
                <command code="-201">
                  {output}
                </command>
              </validate>
              <status code="1" message="Error occurred"/>
            </pacemaker-result>
            """
        self.__calls.place(
            name,
            RunnerCall(cmd, stdout=stdout, returncode=returncode, env=env),
            instead=instead,
        )

    def ticket_unstandby(
        self,
        ticket_name: str,
        stderr="",
        returncode=0,
        name="runner.pcmk.ticket_unstandby",
    ) -> None:
        self.__calls.place(
            name,
            RunnerCall(
                [
                    settings.crm_ticket_exec,
                    "--activate",
                    "--ticket",
                    ticket_name,
                ],
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def ticket_standby(
        self,
        ticket_name: str,
        stderr="",
        returncode=0,
        name="runner.pcmk.ticket_standby",
    ) -> None:
        self.__calls.place(
            name,
            RunnerCall(
                [
                    settings.crm_ticket_exec,
                    "--standby",
                    "--ticket",
                    ticket_name,
                ],
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def ticket_cleanup(
        self,
        ticket_name: str,
        stderr="",
        returncode=0,
        name="runner.pcmk.ticket_cleanup",
    ) -> None:
        self.__calls.place(
            name,
            RunnerCall(
                [
                    settings.crm_ticket_exec,
                    "--cleanup",
                    "--force",
                    "--ticket",
                    ticket_name,
                ],
                stderr=stderr,
                returncode=returncode,
            ),
        )

from pcs import settings

from pcs_test.tools.command_env.mock_runner import Call as RunnerCall


class BoothShortcuts:
    def __init__(self, calls):
        self.__calls = calls

    def status_daemon(
        self,
        instance_name=None,
        stdout="",
        stderr="",
        returncode=0,
        name="runner.booth.status_daemon",
        instead=None,
        before=None,
    ):
        """
        Create a call for getting the booth daemon status

        string instance_name -- booth instance name
        string stdout -- stdout of the booth command
        string stderr -- stderr of the booth command
        int returncode -- returncode of the booth command
        string name -- the key of the call
        string before -- the key of a call before which this call is to be
            placed
        string instead -- the key of a call instead of which this new call is to
            be placed
        """
        cmd = [settings.booth_exec, "status"]
        if instance_name:
            cmd.extend(["-c", instance_name])
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

    def status_peers(
        self,
        instance_name=None,
        stdout="",
        stderr="",
        returncode=0,
        name="runner.booth.status_peers",
        instead=None,
        before=None,
    ):
        """
        Create a call for getting the booth peers status

        string instance_name -- booth instance name
        string stdout -- stdout of the booth command
        string stderr -- stderr of the booth command
        int returncode -- returncode of the booth command
        string name -- the key of the call
        string before -- the key of a call before which this call is to be
            placed
        string instead -- the key of a call instead of which this new call is to
            be placed
        """
        cmd = [settings.booth_exec, "peers"]
        if instance_name:
            cmd.extend(["-c", instance_name])
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

    def status_tickets(
        self,
        instance_name=None,
        stdout="",
        stderr="",
        returncode=0,
        name="runner.booth.status_tickets",
        instead=None,
        before=None,
    ):
        """
        Create a call for getting the booth tickets status

        string instance_name -- booth instance name
        string stdout -- stdout of the booth command
        string stderr -- stderr of the booth command
        int returncode -- returncode of the booth command
        string name -- the key of the call
        string before -- the key of a call before which this call is to be
            placed
        string instead -- the key of a call instead of which this new call is to
            be placed
        """
        cmd = [settings.booth_exec, "list"]
        if instance_name:
            cmd.extend(["-c", instance_name])
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

    def ticket_grant(
        self,
        ticket_name,
        site_ip,
        stdout="",
        stderr="",
        returncode=0,
        name="runner.booth.ticket_grant",
        instead=None,
        before=None,
    ):
        # pylint: disable=too-many-arguments
        """
        Create a call for granting a ticket

        string ticket_name -- the name of the ticket to be granted
        string site_ip -- an IP address of a site the ticket is being granted to
        string stdout -- stdout of the booth grant command
        string stderr -- stderr of the booth grant command
        int returncode -- returncode of the booth grant command
        string name -- the key of the call
        string before -- the key of a call before which this call is to be
            placed
        string instead -- the key of a call instead of which this new call is to
            be placed
        """
        self.__calls.place(
            name,
            RunnerCall(
                [settings.booth_exec, "grant", "-s", site_ip, ticket_name],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
            before=before,
            instead=instead,
        )

    def ticket_revoke(
        self,
        ticket_name,
        site_ip,
        stdout="",
        stderr="",
        returncode=0,
        name="runner.booth.ticket_revoke",
        instead=None,
        before=None,
    ):
        # pylint: disable=too-many-arguments
        """
        Create a call for revoking a ticket

        string ticket_name -- the name of the ticket to be revoked
        string site_ip -- an IP address of a site the ticket is being revoked to
        string stdout -- stdout of the booth revoke command
        string stderr -- stderr of the booth revoke command
        int returncode -- returncode of the booth revoke command
        string name -- the key of the call
        string before -- the key of a call before which this call is to be
            placed
        string instead -- the key of a call instead of which this new call is to
            be placed
        """
        self.__calls.place(
            name,
            RunnerCall(
                [settings.booth_exec, "revoke", "-s", site_ip, ticket_name],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
            before=before,
            instead=instead,
        )

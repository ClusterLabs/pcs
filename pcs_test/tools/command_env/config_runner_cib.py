from pcs_test.tools.command_env.mock_runner import Call as RunnerCall
from pcs_test.tools.command_env.mock_runner import CheckStdinEqualXml
from pcs_test.tools.fixture_cib import modify_cib
from pcs_test.tools.misc import get_test_resource as rc

CIB_FILENAME = "cib-empty.xml"


class CibShortcuts:
    def __init__(self, calls):
        """
        CallCollection calls -- provides access to call list
        """
        self.__calls = calls
        self.cib_filename = CIB_FILENAME

    def load(
        self,
        *,
        modifiers=None,
        name="runner.cib.load",
        filename=None,
        before=None,
        returncode=0,
        stderr=None,
        instead=None,
        env=None,
        **modifier_shortcuts,
    ):
        """
        Create call for loading cib.

        string name -- key of the call
        list of callable modifiers -- every callable takes etree.Element and
            returns new etree.Element with desired modification.
        string filename -- points to file with cib in the content
        string before -- key of call before which this new call is to be placed
        int returncode
        string stderr
        string instead -- key of call instead of which this new call is to be
            placed
        dict env -- CommandRunner environment variables
        dict modifier_shortcuts -- a new modifier is generated from each
            modifier shortcut.
            As key there can be keys of MODIFIER_GENERATORS.
            Value is passed into appropriate generator from MODIFIER_GENERATORS.
            For details see pcs_test.tools.fixture_cib (mainly the variable
            MODIFIER_GENERATORS - please refer it when you are adding params
            here)
        """
        # pylint: disable=too-many-arguments
        if (returncode != 0 or stderr is not None) and (
            modifiers is not None or filename is not None or modifier_shortcuts
        ):
            raise AssertionError(
                "Do not combine parameters 'returncode' and 'stderr' with"
                " parameters 'modifiers', 'filename' and 'modifier_shortcuts'"
            )

        command = ["cibadmin", "--local", "--query"]
        if returncode != 0:
            call = RunnerCall(
                command, stderr=stderr, returncode=returncode, env=env
            )
        else:
            with open(
                rc(filename if filename else self.cib_filename),
            ) as cib_file:
                cib = modify_cib(
                    cib_file.read(), modifiers, **modifier_shortcuts
                )
                call = RunnerCall(command, stdout=cib, env=env)

        self.__calls.place(name, call, before=before, instead=instead)

    def load_content(
        self,
        cib,
        returncode=0,
        stderr=None,
        name="runner.cib.load_content",
        instead=None,
        before=None,
        env=None,
    ):
        """
        Create call for loading CIB specified by its full content

        string cib -- CIB data (stdout of the loading process)
        string stderr -- error returned from the loading process
        int returncode -- exit code of the loading process
        string name -- key of the call
        string instead -- key of call instead of which this new call is to be
            placed
        string before -- key of call before which this new call is to be placed
        dict env -- CommandRunner environment variables
        """
        command = ["cibadmin", "--local", "--query"]
        if returncode != 0:
            call = RunnerCall(
                command, stderr=stderr, returncode=returncode, env=env
            )
        else:
            call = RunnerCall(command, stdout=cib, env=env)
        self.__calls.place(name, call, before=before, instead=instead)

    def push(
        self,
        modifiers=None,
        name="runner.cib.push",
        load_key="runner.cib.load",
        instead=None,
        stderr="",
        returncode=0,
        **modifier_shortcuts,
    ):
        """
        Create call for pushing cib.
        Cib is taken from the load call by default.

        string name -- key of the call
        list of callable modifiers -- every callable takes etree.Element and
            returns new etree.Element with desired modification.
        string load_key -- key of a call from which stdout can be cib taken
        string instead -- key of call instead of which this new call is to be
            placed
        dict modifier_shortcuts -- a new modifier is generated from each
            modifier shortcut.
            As key there can be keys of MODIFIER_GENERATORS.
            Value is passed into appropriate generator from MODIFIER_GENERATORS.
            For details see pcs_test.tools.fixture_cib (mainly the variable
            MODIFIER_GENERATORS - please refer it when you are adding params
            here)
        """
        cib = modify_cib(
            self.__calls.get(load_key).stdout, modifiers, **modifier_shortcuts
        )
        self.__calls.place(
            name,
            RunnerCall(
                [
                    "cibadmin",
                    "--replace",
                    "--verbose",
                    "--xml-pipe",
                    "--scope",
                    "configuration",
                ],
                stderr=stderr,
                returncode=returncode,
                check_stdin=CheckStdinEqualXml(cib),
            ),
            instead=instead,
        )

    def push_independent(
        self,
        cib,
        name="runner.cib.push_independent",
        instead=None,
    ):
        """
        Create call for pushing cib.
        Cib is specified as an argument.

        string name -- key of the call
        string cib -- whole cib to push
        string instead -- key of call instead of which this new call is to be
            placed
        """
        self.__calls.place(
            name,
            RunnerCall(
                [
                    "cibadmin",
                    "--replace",
                    "--verbose",
                    "--xml-pipe",
                    "--scope",
                    "configuration",
                ],
                check_stdin=CheckStdinEqualXml(cib),
            ),
            instead=instead,
        )

    def diff(
        self,
        cib_old_file,
        cib_new_file,
        name="runner.cib.diff",
        stdout="resulting diff",
        stderr="",
        returncode=1,  # 0 -> old and new are the same, 1 -> old and new differ
    ):
        """
        Create a call for diffing two CIBs stored in two files
        string cib_old_file -- path to a file with an old CIB
        string cib_new_file -- path to a file with a new CIB
        string name -- key of the call
        string stdout -- resulting diff
        string stderr -- error returned from the diff process
        int returncode -- exit code of the diff process
        """
        self.__calls.place(
            name,
            RunnerCall(
                [
                    "crm_diff",
                    "--original",
                    cib_old_file,
                    "--new",
                    cib_new_file,
                    "--no-version",
                ],
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def push_diff(
        self,
        name="runner.cib.push_diff",
        cib_diff="resulting diff",
        stdout="",
        stderr="",
        returncode=0,
        env=None,
    ):
        """
        Create a call for pushing a diff of CIBs
        string name -- key of the call
        string cib_diff -- the diff of CIBs
        dict env -- CommandRunner environment variables
        """
        self.__calls.place(
            name,
            RunnerCall(
                ["cibadmin", "--patch", "--verbose", "--xml-pipe"],
                check_stdin=CheckStdinEqualXml(cib_diff),
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
                env=env,
            ),
        )

    def upgrade(self, name="runner.cib.upgrade", before=None):
        """
        Create call for upgrading cib.

        string name -- key of the call
        string before -- key of call before which this new call is to be placed
        """
        self.__calls.place(
            name,
            RunnerCall(["cibadmin", "--upgrade", "--force"]),
            before=before,
        )

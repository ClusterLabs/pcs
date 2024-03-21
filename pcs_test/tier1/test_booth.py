import os
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs.cli.booth import command as booth_cmd
from pcs.lib.booth import constants

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_dir,
    get_tmp_file,
    outdent,
    skip_unless_booth_resource_agent_installed,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

EMPTY_CIB = rc("cib-empty.xml")


class BoothMixinNoFiles(AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(None)


class BoothMixin(AssertPcsMixin):
    def setUp(self):
        self.booth_dir = get_tmp_dir("tier1_booth")
        self.booth_cfg_path = os.path.join(self.booth_dir.name, "booth.cfg")
        self.booth_key_path = os.path.join(self.booth_dir.name, "booth.key")
        self.temp_cib = get_tmp_file("tier1_booth")
        write_file_to_tmpfile(EMPTY_CIB, self.temp_cib)
        self.pcs_runner = PcsRunner(
            self.temp_cib.name,
            mock_settings=dict(
                booth_enable_authfile_set_enabled=str(False),
                booth_enable_authfile_unset_enabled=str(False),
            ),
        )

    def tearDown(self):
        self.temp_cib.close()
        self.booth_dir.cleanup()

    def fake_file(self, command):
        return command + [
            f"--booth-conf={self.booth_cfg_path}",
            f"--booth-key={self.booth_key_path}",
        ]

    def ensure_booth_config_exists(self):
        if not os.path.exists(self.booth_cfg_path):
            with open(self.booth_cfg_path, "w") as config_file:
                config_file.write("")

    def ensure_booth_config_not_exists(self):
        if os.path.exists(self.booth_cfg_path):
            os.remove(self.booth_cfg_path)
        if os.path.exists(self.booth_key_path):
            os.remove(self.booth_key_path)

    def assert_pcs_success(self, command, *args, **kwargs):
        return super().assert_pcs_success(
            self.fake_file(command), *args, **kwargs
        )

    def assert_pcs_fail(self, command, *args, **kwargs):
        return super().assert_pcs_fail(self.fake_file(command), *args, **kwargs)

    def assert_pcs_fail_original(self, *args, **kwargs):
        return super().assert_pcs_fail(*args, **kwargs)


class SetupTest(BoothMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pcs_runner.cib_file = None

    def test_success_setup_booth_config(self):
        self.ensure_booth_config_not_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3".split()
        )
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    """\
                    authfile = {0}
                    site = 1.1.1.1
                    site = 2.2.2.2
                    arbitrator = 3.3.3.3
                    """.format(
                        self.booth_key_path
                    )
                ),
                config_file.read(),
            )
        with open(self.booth_key_path, "rb") as key_file:
            self.assertEqual(64, len(key_file.read()))

    def test_success_setup_booth_config_enable_autfile(self):
        self.pcs_runner = PcsRunner(
            None,
            mock_settings=dict(
                booth_enable_authfile_set_enabled=str(True),
                booth_enable_authfile_unset_enabled=str(False),
            ),
        )
        self.ensure_booth_config_not_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3".split()
        )
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    f"""\
                    authfile = {self.booth_key_path}
                    {constants.AUTHFILE_FIX_OPTION} = yes
                    site = 1.1.1.1
                    site = 2.2.2.2
                    arbitrator = 3.3.3.3
                    """
                ),
                config_file.read(),
            )

    def test_overwrite_existing_mocked_config(self):
        self.ensure_booth_config_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3".split(),
        )
        self.ensure_booth_config_not_exists()

    def test_fail_on_multiple_reasons(self):
        self.assert_pcs_fail(
            (
                "booth setup sites 1.1.1.1 arbitrators 1.1.1.1 2.2.2.2 3.3.3.3"
            ).split(),
            (
                "Error: lack of sites for booth configuration (need 2 at least)"
                ": sites '1.1.1.1'\n"
                "Error: odd number of peers is required (entered 4 peers)\n"
                "Error: duplicate address for booth configuration: '1.1.1.1'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_refuse_partially_mocked_environment(self):
        self.assert_pcs_fail_original(
            # no --booth-key!
            (
                "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3 "
                "--booth-conf=/some/file"
            ).split(),
            (
                "Error: When --booth-conf is specified, --booth-key must be "
                "specified as well\n"
            ),
        )
        self.assert_pcs_fail_original(
            # no --booth-conf!
            (
                "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3 "
                "--booth-key=/some/file"
            ).split(),
            (
                "Error: When --booth-key is specified, --booth-conf must be "
                "specified as well\n"
            ),
        )

    def test_show_usage_when_no_site_specified(self):
        self.assert_pcs_fail(
            "booth setup arbitrators 3.3.3.3".split(),
            stderr_start="\nUsage: pcs booth <command>\n    setup",
        )
        self.assert_pcs_fail(
            "booth setup".split(),
            stderr_start="\nUsage: pcs booth <command>\n    setup",
        )


class DestroyTest(BoothMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pcs_runner.cib_file = None

    def test_failed_when_using_mocked_booth_env(self):
        self.assert_pcs_fail(
            "booth destroy".split(),
            (
                "Error: Specified options '--booth-conf', '--booth-key' are "
                "not supported in this command\n"
            ),
        )


class BoothTest(BoothMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pcs_runner.cib_file = None
        self.ensure_booth_config_not_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3".split()
        )


class AddTicketTest(BoothTest):
    def test_success_add_ticket(self):
        self.assert_pcs_success("booth ticket add TicketA expire=10".split())
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    """\
                    authfile = {0}
                    site = 1.1.1.1
                    site = 2.2.2.2
                    arbitrator = 3.3.3.3
                    ticket = "TicketA"
                      expire = 10
                    """.format(
                        self.booth_key_path
                    )
                ),
                config_file.read(),
            )

    def test_fail_on_bad_ticket_name(self):
        self.assert_pcs_fail(
            "booth ticket add @TicketA".split(),
            (
                "Error: booth ticket name '@TicketA' is not valid, use up to 63 "
                "alphanumeric characters or dash\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_on_duplicit_ticket_name(self):
        self.assert_pcs_success("booth ticket add TicketA".split())
        self.assert_pcs_fail(
            "booth ticket add TicketA".split(),
            (
                "Error: booth ticket name 'TicketA' already exists in "
                "configuration\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_on_invalid_options(self):
        self.assert_pcs_fail(
            "booth ticket add TicketA site=a timeout=".split(),
            (
                "Error: invalid booth ticket option 'site', allowed options"
                " are: 'acquire-after', 'attr-prereq', "
                "'before-acquire-handler', 'expire', 'mode', 'renewal-freq', "
                "'retries', 'timeout', 'weights'\n"
                "Error: timeout cannot be empty\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_forceable_fail_on_unknown_options(self):
        msg = (
            "invalid booth ticket option 'unknown', allowed options"
            " are: 'acquire-after', 'attr-prereq', 'before-acquire-handler',"
            " 'expire', 'mode', 'renewal-freq', 'retries', 'timeout', 'weights'"
        )
        self.assert_pcs_fail(
            "booth ticket add TicketA unknown=a".split(),
            (
                "Error: {0}, use --force to override\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ).format(msg),
        )
        self.assert_pcs_success(
            "booth ticket add TicketA unknown=a --force".split(),
            stderr_full="Warning: {0}\n".format(msg),
        )

    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth ticket add".split(),
            stderr_start="\nUsage: pcs booth <command>\n    ticket add",
        )


class DeleteRemoveTicketMixin:
    command = None

    def test_not_enough_args(self):
        self.assert_pcs_fail(
            ["booth", "ticket", self.command],
            stderr_start=outdent(
                f"""
                Usage: pcs booth <command>
                    ticket {self.command} <"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            ["booth", "ticket", self.command, "aaa", "bbb"],
            stderr_start=outdent(
                f"""
                Usage: pcs booth <command>
                    ticket {self.command} <"""
            ),
        )

    def test_success_remove_ticket(self):
        self.assert_pcs_success("booth ticket add TicketA".split())
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    """\
                    authfile = {0}
                    site = 1.1.1.1
                    site = 2.2.2.2
                    arbitrator = 3.3.3.3
                    ticket = "TicketA"
                    """.format(
                        self.booth_key_path
                    )
                ),
                config_file.read(),
            )
        self.assert_pcs_success(["booth", "ticket", self.command, "TicketA"])
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    """\
                    authfile = {0}
                    site = 1.1.1.1
                    site = 2.2.2.2
                    arbitrator = 3.3.3.3
                    """.format(
                        self.booth_key_path
                    )
                ),
                config_file.read(),
            )

    def test_fail_when_ticket_does_not_exist(self):
        self.assert_pcs_fail(
            ["booth", "ticket", self.command, "TicketA"],
            (
                "Error: booth ticket name 'TicketA' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )


class DeleteTicketTest(DeleteRemoveTicketMixin, BoothTest):
    command = "delete"


class RemoveTicketTest(DeleteRemoveTicketMixin, BoothTest):
    command = "remove"


@skip_unless_booth_resource_agent_installed()
class CreateTest(BoothMixinNoFiles, TestCase):
    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth create".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    create ip <"""
            ),
        )
        self.assert_pcs_fail(
            "booth create ip".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    create ip <"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth create ip aaa bbb".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    create ip <"""
            ),
        )


class DeleteRemoveTestMixin(AssertPcsMixin):
    command = None

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_booth_delete_remove")
        write_file_to_tmpfile(EMPTY_CIB, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_usage(self):
        self.assert_pcs_fail(
            ["booth", self.command, "a", "b"],
            stderr_start=outdent(
                f"""
                Usage: pcs booth <command>
                    {self.command}
                """
            ),
        )

    def test_failed_when_no_booth_configuration_created(self):
        self.assert_pcs_success(
            "resource status".split(), "NO resources configured\n"
        )
        self.assert_pcs_fail(
            ["booth", self.command],
            [
                "Error: booth instance 'booth' not found in cib",
                "Error: Errors have occurred, therefore pcs is unable to continue",
            ],
        )


@skip_unless_booth_resource_agent_installed()
class DeleteTest(DeleteRemoveTestMixin, TestCase):
    command = "delete"


@skip_unless_booth_resource_agent_installed()
class RemoveTest(DeleteRemoveTestMixin, TestCase):
    command = "remove"


class TicketGrantTest(BoothMixinNoFiles, TestCase):
    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth ticket grant".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    ticket grant <"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth ticket grant aaa bbb ccc".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    ticket grant <"""
            ),
        )


class TicketRevokeTest(BoothMixinNoFiles, TestCase):
    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth ticket revoke".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    ticket revoke <"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth ticket revoke aaa bbb ccc".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    ticket revoke <"""
            ),
        )


class Restart(BoothMixinNoFiles, TestCase):
    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth restart aaa".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    restart"""
            ),
        )


class Sync(BoothMixinNoFiles, TestCase):
    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth sync aaa".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    sync"""
            ),
        )


class BoothServiceTestMixin(BoothMixinNoFiles):
    def test_too_many_args(self):
        self.assert_pcs_fail(
            ["booth", self.cmd_label, "aaa"],
            stderr_start=outdent(
                f"""
                Usage: pcs booth <command>
                    {self.cmd_label}"""
            ),
        )


class Enable(BoothServiceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.cmd_label = "enable"
        self.cli_cmd = booth_cmd.enable


class Disable(BoothServiceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.cmd_label = "disable"
        self.cli_cmd = booth_cmd.disable


class Start(BoothServiceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.cmd_label = "start"
        self.cli_cmd = booth_cmd.start


class Stop(BoothServiceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.cmd_label = "stop"
        self.cli_cmd = booth_cmd.stop


class Pull(BoothMixinNoFiles, TestCase):
    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth pull".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    pull"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth pull aaa bbb".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    pull"""
            ),
        )


# disable printig the booth status so it won't break tests output
@mock.patch("pcs.cli.booth.command.print", new=lambda x: x)
class Status(BoothMixinNoFiles, TestCase):
    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth status aaa".split(),
            stderr_start=outdent(
                """
                Usage: pcs booth <command>
                    status"""
            ),
        )


class EnableAuthfile(BoothMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pcs_runner.cib_file = None
        self.pcs_runner.mock_settings["booth_enable_authfile_set_enabled"] = (
            str(True)
        )
        self.ensure_booth_config_not_exists()

    def test_not_enabled(self):
        with open(self.booth_cfg_path, "w") as config_file:
            config_file.write(f"authfile = {self.booth_key_path}\n")
        self.assert_pcs_success("booth enable-authfile".split())
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    f"""\
                    {constants.AUTHFILE_FIX_OPTION} = yes
                    authfile = {self.booth_key_path}
                    """
                ),
                config_file.read(),
            )

    def test_already_enabled(self):
        with open(self.booth_cfg_path, "w") as config_file:
            config_file.write(
                dedent(
                    f"""\
                    authfile = {self.booth_key_path}
                    {constants.AUTHFILE_FIX_OPTION} = on
                    """
                )
            )
        self.assert_pcs_success("booth enable-authfile".split())
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    f"""\
                    {constants.AUTHFILE_FIX_OPTION} = yes
                    authfile = {self.booth_key_path}
                    """
                ),
                config_file.read(),
            )


class CleanEnableAuthfile(BoothMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pcs_runner.cib_file = None
        self.ensure_booth_config_not_exists()
        self.pcs_runner.mock_settings["booth_enable_authfile_unset_enabled"] = (
            str(True)
        )

    def test_not_set(self):
        with open(self.booth_cfg_path, "w") as config_file:
            config_file.write(f"authfile = {self.booth_key_path}\n")
        self.assert_pcs_success("booth clean-enable-authfile".split())
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    f"""\
                    authfile = {self.booth_key_path}
                    """
                ),
                config_file.read(),
            )

    def test_enabled(self):
        with open(self.booth_cfg_path, "w") as config_file:
            config_file.write(
                dedent(
                    f"""\
                    authfile = {self.booth_key_path}
                    {constants.AUTHFILE_FIX_OPTION} = 1
                    """
                )
            )
        self.assert_pcs_success("booth clean-enable-authfile".split())
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    f"""\
                    authfile = {self.booth_key_path}
                    """
                ),
                config_file.read(),
            )

    def test_disabled(self):
        with open(self.booth_cfg_path, "w") as config_file:
            config_file.write(
                dedent(
                    f"""\
                    authfile = {self.booth_key_path}
                    {constants.AUTHFILE_FIX_OPTION} = off
                    """
                )
            )
        self.assert_pcs_success("booth clean-enable-authfile".split())
        with open(self.booth_cfg_path, "r") as config_file:
            self.assertEqual(
                dedent(
                    f"""\
                    authfile = {self.booth_key_path}
                    """
                ),
                config_file.read(),
            )

import os
from textwrap import dedent
from unittest import mock, skipUnless, TestCase

from pcs.cli.booth import command as booth_cmd
from pcs.cli.common.errors import CmdLineInputError

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    dict_to_modifiers,
    get_test_resource as rc,
    get_tmp_dir,
    get_tmp_file,
    outdent,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


EMPTY_CIB = rc("cib-empty.xml")

BOOTH_RESOURCE_AGENT_INSTALLED = os.path.exists(
    "/usr/lib/ocf/resource.d/pacemaker/booth-site"
)
need_booth_resource_agent = skipUnless(
    BOOTH_RESOURCE_AGENT_INSTALLED,
    "test requires resource agent ocf:pacemaker:booth-site"
    " which is not installed",
)


class BoothLibCallMixin(AssertPcsMixin):
    def setUp(self):
        # plyint cannot possibly know this is being mixed into TestCase classes
        # pylint: disable=invalid-name
        self.pcs_runner = PcsRunner(None)
        self.lib = mock.Mock(spec_set=["booth"])


class BoothMixin(AssertPcsMixin):
    def setUp(self):
        # plyint cannot possibly know this is being mixed into TestCase classes
        # pylint: disable=invalid-name
        self.booth_dir = get_tmp_dir("tier0_booth")
        self.booth_cfg_path = os.path.join(self.booth_dir.name, "booth.cfg")
        self.booth_key_path = os.path.join(self.booth_dir.name, "booth.key")
        self.temp_cib = get_tmp_file("tier0_booth")
        write_file_to_tmpfile(EMPTY_CIB, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.lib = mock.Mock(spec_set=["booth"])

    def tearDown(self):
        # plyint cannot possibly know this is being mixed into TestCase classes
        # pylint: disable=invalid-name
        self.temp_cib.close()
        self.booth_dir.cleanup()

    def fake_file(self, command):
        return "{0} --booth-conf={1} --booth-key={2}".format(
            command, self.booth_cfg_path, self.booth_key_path,
        )

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
        # pylint: disable=arguments-differ
        return super(BoothMixin, self).assert_pcs_success(
            self.fake_file(command), *args, **kwargs
        )

    def assert_pcs_fail(self, command, *args, **kwargs):
        # pylint: disable=arguments-differ
        return super(BoothMixin, self).assert_pcs_fail(
            self.fake_file(command), *args, **kwargs
        )

    def assert_pcs_fail_original(self, *args, **kwargs):
        return super(BoothMixin, self).assert_pcs_fail(*args, **kwargs)


class SetupTest(BoothMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pcs_runner.cib_file = None
        self.lib.booth = mock.Mock(spec_set=["config_setup"])

    def test_sucess_setup_booth_config(self):
        self.ensure_booth_config_not_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
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

    def test_overwrite_existing_mocked_config(self):
        self.ensure_booth_config_exists()
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3",
        )
        self.ensure_booth_config_not_exists()

    def test_fail_on_multiple_reasons(self):
        self.assert_pcs_fail(
            "booth setup sites 1.1.1.1 arbitrators 1.1.1.1 2.2.2.2 3.3.3.3",
            (
                "Error: lack of sites for booth configuration (need 2 at least)"
                ": sites '1.1.1.1'\n"
                "Error: odd number of peers is required (entered 4 peers)\n"
                "Error: duplicate address for booth configuration: '1.1.1.1'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_refuse_partialy_mocked_environment(self):
        self.assert_pcs_fail_original(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
            " --booth-conf=/some/file",  # no --booth-key!
            (
                "Error: When --booth-conf is specified, --booth-key must be "
                "specified as well\n"
            ),
        )
        self.assert_pcs_fail_original(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
            " --booth-key=/some/file",  # no --booth-conf!
            (
                "Error: When --booth-key is specified, --booth-conf must be "
                "specified as well\n"
            ),
        )

    def test_show_usage_when_no_site_specified(self):
        self.assert_pcs_fail(
            "booth setup arbitrators 3.3.3.3",
            stdout_start="\nUsage: pcs booth <command>\n    setup",
        )
        self.assert_pcs_fail(
            "booth setup",
            stdout_start="\nUsage: pcs booth <command>\n    setup",
        )

    def test_lib_call_minimal(self):
        booth_cmd.config_setup(
            self.lib,
            ["sites", "1.1.1.1", "2.2.2.2", "3.3.3.3"],
            dict_to_modifiers(dict()),
        )
        self.lib.booth.config_setup.assert_called_once_with(
            ["1.1.1.1", "2.2.2.2", "3.3.3.3"],
            [],
            instance_name=None,
            overwrite_existing=False,
        )

    def test_lib_call_full(self):
        booth_cmd.config_setup(
            self.lib,
            ["sites", "1.1.1.1", "2.2.2.2", "arbitrators", "3.3.3.3"],
            dict_to_modifiers(dict(name="my_booth", force=True)),
        )
        self.lib.booth.config_setup.assert_called_once_with(
            ["1.1.1.1", "2.2.2.2"],
            ["3.3.3.3"],
            instance_name="my_booth",
            overwrite_existing=True,
        )


class DestroyTest(BoothMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["config_destroy"])

    def test_failed_when_using_mocked_booth_env(self):
        self.pcs_runner.cib_file = None
        self.assert_pcs_fail(
            "booth destroy",
            (
                "Error: Specified options '--booth-conf', '--booth-key' are "
                "not supported in this command\n"
            ),
        )

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            booth_cmd.config_destroy(
                self.lib, ["aaa"], dict_to_modifiers(dict())
            )
        self.assertIsNone(cm.exception.message)
        self.lib.booth.config_destroy.assert_not_called()

    def test_lib_call_minimal(self):
        booth_cmd.config_destroy(self.lib, [], dict_to_modifiers(dict()))
        self.lib.booth.config_destroy.assert_called_once_with(
            ignore_config_load_problems=False, instance_name=None,
        )

    def test_lib_call_full(self):
        booth_cmd.config_destroy(
            self.lib, [], dict_to_modifiers(dict(name="my_booth", force=True))
        )
        self.lib.booth.config_destroy.assert_called_once_with(
            ignore_config_load_problems=True, instance_name="my_booth",
        )


class BoothTest(BoothMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.ensure_booth_config_not_exists()
        self.pcs_runner.cib_file = None
        self.assert_pcs_success(
            "booth setup sites 1.1.1.1 2.2.2.2 arbitrators 3.3.3.3"
        )
        self.pcs_runner.cib_file = self.temp_cib.name


class AddTicketTest(BoothTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.cib_file = None
        self.lib.booth = mock.Mock(spec_set=["config_ticket_add"])

    def test_success_add_ticket(self):
        self.assert_pcs_success("booth ticket add TicketA expire=10")
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
            "booth ticket add @TicketA",
            (
                "Error: booth ticket name '@TicketA' is not valid, use "
                "alphanumeric chars or dash\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_on_duplicit_ticket_name(self):
        self.assert_pcs_success("booth ticket add TicketA")
        self.assert_pcs_fail(
            "booth ticket add TicketA",
            (
                "Error: booth ticket name 'TicketA' already exists in "
                "configuration\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_on_invalid_options(self):
        self.assert_pcs_fail(
            "booth ticket add TicketA site=a timeout=",
            (
                "Error: invalid booth ticket option 'site', allowed options"
                " are: 'acquire-after', 'attr-prereq', "
                "'before-acquire-handler', 'expire', 'renewal-freq', "
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
            " 'expire', 'renewal-freq', 'retries', 'timeout', 'weights'"
        )
        self.assert_pcs_fail(
            "booth ticket add TicketA unknown=a",
            (
                "Error: {0}, use --force to override\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ).format(msg),
        )
        self.assert_pcs_success(
            "booth ticket add TicketA unknown=a --force",
            "Warning: {0}\n".format(msg),
        )

    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth ticket add",
            stdout_start="\nUsage: pcs booth <command>\n    ticket add",
        )

    def test_lib_call_minimal(self):
        booth_cmd.config_ticket_add(
            self.lib, ["ticketA"], dict_to_modifiers(dict())
        )
        self.lib.booth.config_ticket_add.assert_called_once_with(
            "ticketA", {}, instance_name=None, allow_unknown_options=False,
        )

    def test_lib_call_full(self):
        booth_cmd.config_ticket_add(
            self.lib,
            ["ticketA", "a=A", "b=B"],
            dict_to_modifiers(
                {
                    "name": "my_booth",
                    "force": True,
                    "booth-conf": "C",
                    "booth-key": "K",
                }
            ),
        )
        self.lib.booth.config_ticket_add.assert_called_once_with(
            "ticketA",
            {"a": "A", "b": "B"},
            instance_name="my_booth",
            allow_unknown_options=True,
        )


class DeleteRemoveTicketMixin:
    command = None

    # plyint cannot possibly know this is being mixed into TestCase classes
    # pylint: disable=invalid-name
    def setUp(self):
        super().setUp()
        self.pcs_runner.cib_file = None
        self.lib.booth = mock.Mock(spec_set=["config_ticket_remove"])

    def test_not_enough_args(self):
        self.assert_pcs_fail(
            f"booth ticket {self.command}",
            stdout_start=outdent(
                f"""
                Usage: pcs booth <command>
                    ticket {self.command} <"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            f"booth ticket {self.command} aaa bbb",
            stdout_start=outdent(
                f"""
                Usage: pcs booth <command>
                    ticket {self.command} <"""
            ),
        )

    def test_success_remove_ticket(self):
        self.assert_pcs_success("booth ticket add TicketA")
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
        self.assert_pcs_success(f"booth ticket {self.command} TicketA")
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
            f"booth ticket {self.command} TicketA",
            (
                "Error: booth ticket name 'TicketA' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_lib_call_minimal(self):
        booth_cmd.config_ticket_remove(
            self.lib, ["ticketA"], dict_to_modifiers(dict())
        )
        self.lib.booth.config_ticket_remove.assert_called_once_with(
            "ticketA", instance_name=None,
        )

    def test_lib_call_full(self):
        booth_cmd.config_ticket_remove(
            self.lib,
            ["ticketA"],
            dict_to_modifiers(
                {"name": "my_booth", "booth-conf": "C", "booth-key": "K",}
            ),
        )
        self.lib.booth.config_ticket_remove.assert_called_once_with(
            "ticketA", instance_name="my_booth",
        )


class DeleteTicketTest(DeleteRemoveTicketMixin, BoothTest):
    command = "delete"


class RemoveTicketTest(DeleteRemoveTicketMixin, BoothTest):
    command = "remove"


@need_booth_resource_agent
class CreateTest(AssertPcsMixin, TestCase):
    def setUp(self):
        self.pcs_runner = PcsRunner(None)
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["create_in_cluster"])

    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth create",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    create ip <"""
            ),
        )
        self.assert_pcs_fail(
            "booth create ip",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    create ip <"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth create ip aaa bbb",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    create ip <"""
            ),
        )

    def test_lib_call_minimal(self):
        booth_cmd.create_in_cluster(
            self.lib, ["ip", "1.2.3.4"], dict_to_modifiers(dict())
        )
        self.lib.booth.create_in_cluster.assert_called_once_with(
            "1.2.3.4", instance_name=None, allow_absent_resource_agent=False,
        )

    def test_lib_call_full(self):
        booth_cmd.create_in_cluster(
            self.lib,
            ["ip", "1.2.3.4"],
            dict_to_modifiers(dict(name="my_booth", force=True)),
        )
        self.lib.booth.create_in_cluster.assert_called_once_with(
            "1.2.3.4",
            instance_name="my_booth",
            allow_absent_resource_agent=True,
        )


class DeleteRemoveTestMixin(AssertPcsMixin):
    command = None

    def setUp(self):
        # pylint cannot know this will be mixed into a TetsCase class
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier0_booth_delete_remove")
        write_file_to_tmpfile(EMPTY_CIB, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["remove_from_cluster"])

    def tearDown(self):
        # plyint cannot possibly know this is being mixed into TestCase classes
        # pylint: disable=invalid-name
        self.temp_cib.close()

    def test_usage(self):
        self.assert_pcs_fail(
            f"booth {self.command} a b",
            stdout_start=outdent(
                f"""
                Usage: pcs booth <command>
                    {self.command}
                """
            ),
        )

    def test_failed_when_no_booth_configuration_created(self):
        self.assert_pcs_success("resource status", "NO resources configured\n")
        self.assert_pcs_fail(
            f"booth {self.command}",
            [
                # pylint: disable=line-too-long
                "Error: booth instance 'booth' not found in cib",
                "Error: Errors have occurred, therefore pcs is unable to continue",
            ],
        )

    def test_lib_call_minimal(self):
        resource_remove = lambda x: x
        booth_cmd.get_remove_from_cluster(resource_remove)(
            self.lib, [], dict_to_modifiers(dict())
        )
        self.lib.booth.remove_from_cluster.assert_called_once_with(
            resource_remove, instance_name=None, allow_remove_multiple=False,
        )

    def test_lib_call_full(self):
        resource_remove = lambda x: x
        booth_cmd.get_remove_from_cluster(resource_remove)(
            self.lib, [], dict_to_modifiers(dict(name="my_booth", force=True))
        )
        self.lib.booth.remove_from_cluster.assert_called_once_with(
            resource_remove,
            instance_name="my_booth",
            allow_remove_multiple=True,
        )


@need_booth_resource_agent
class DeleteTest(DeleteRemoveTestMixin, TestCase):
    command = "delete"


@need_booth_resource_agent
class RemoveTest(DeleteRemoveTestMixin, TestCase):
    command = "remove"


class TicketGrantTest(BoothLibCallMixin, TestCase):
    # plyint cannot possibly know this is being mixed into TestCase classes
    # pylint: disable=invalid-name
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["ticket_grant"])

    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth ticket grant",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    ticket grant <"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth ticket grant aaa bbb ccc",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    ticket grant <"""
            ),
        )

    def test_lib_call_minimal(self):
        booth_cmd.ticket_grant(self.lib, ["ticketA"], dict_to_modifiers(dict()))
        self.lib.booth.ticket_grant.assert_called_once_with(
            "ticketA", instance_name=None, site_ip=None,
        )

    def test_lib_call_full(self):
        booth_cmd.ticket_grant(
            self.lib,
            ["ticketA", "1.2.3.4"],
            dict_to_modifiers(dict(name="my_booth")),
        )
        self.lib.booth.ticket_grant.assert_called_once_with(
            "ticketA", instance_name="my_booth", site_ip="1.2.3.4",
        )


class TicketRevokeTest(BoothLibCallMixin, TestCase):
    # plyint cannot possibly know this is being mixed into TestCase classes
    # pylint: disable=invalid-name
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["ticket_revoke"])

    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth ticket revoke",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    ticket revoke <"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth ticket revoke aaa bbb ccc",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    ticket revoke <"""
            ),
        )

    def test_lib_call_minimal(self):
        booth_cmd.ticket_revoke(
            self.lib, ["ticketA"], dict_to_modifiers(dict())
        )
        self.lib.booth.ticket_revoke.assert_called_once_with(
            "ticketA", instance_name=None, site_ip=None,
        )

    def test_lib_call_full(self):
        booth_cmd.ticket_revoke(
            self.lib,
            ["ticketA", "1.2.3.4"],
            dict_to_modifiers(dict(name="my_booth")),
        )
        self.lib.booth.ticket_revoke.assert_called_once_with(
            "ticketA", instance_name="my_booth", site_ip="1.2.3.4",
        )


# disable printig the booth config so it won't break tests output
@mock.patch("pcs.cli.booth.command.print", new=lambda x: x)
class ConfigTest(BoothMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["config_text"])

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            booth_cmd.config_show(
                self.lib, ["aaa", "bbb"], dict_to_modifiers(dict())
            )
        self.assertIsNone(cm.exception.message)
        self.lib.booth.config_text.assert_not_called()

    def test_lib_call_minimal(self):
        booth_cmd.config_show(self.lib, [], dict_to_modifiers(dict()))
        self.lib.booth.config_text.assert_called_once_with(
            instance_name=None, node_name=None,
        )

    def test_lib_call_full(self):
        booth_cmd.config_show(
            self.lib,
            ["node1"],
            dict_to_modifiers({"name": "my_booth", "request-timeout": "10",}),
        )
        self.lib.booth.config_text.assert_called_once_with(
            instance_name="my_booth", node_name="node1",
        )


class Restart(BoothLibCallMixin, TestCase):
    # plyint cannot possibly know this is being mixed into TestCase classes
    # pylint: disable=invalid-name
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["restart"])

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth restart aaa",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    restart"""
            ),
        )

    def test_lib_call_minimal(self):
        resource_restart = lambda x: x
        booth_cmd.get_restart(resource_restart)(
            self.lib, [], dict_to_modifiers(dict())
        )
        # The first arg going to the lib call is a lambda which we cannot get
        # in here. So we must check all the other parameters in a bit more
        # complicated way.
        self.assertEqual(self.lib.booth.restart.call_count, 1)
        call = self.lib.booth.restart.call_args
        self.assertEqual(
            call[1], dict(instance_name=None, allow_multiple=False)
        )

    def test_lib_call_full(self):
        resource_restart = lambda x: x
        booth_cmd.get_restart(resource_restart)(
            self.lib, [], dict_to_modifiers(dict(name="my_booth", force=True))
        )
        # The first arg going to the lib call is a lambda which we cannot get
        # in here. So we must check all the other parameters in a bit more
        # complicated way.
        self.assertEqual(self.lib.booth.restart.call_count, 1)
        call = self.lib.booth.restart.call_args
        self.assertEqual(
            call[1], dict(instance_name="my_booth", allow_multiple=True)
        )


class Sync(BoothLibCallMixin, TestCase):
    # plyint cannot possibly know this is being mixed into TestCase classes
    # pylint: disable=invalid-name
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["config_sync"])

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth sync aaa",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    sync"""
            ),
        )

    def test_lib_call_minimal(self):
        booth_cmd.sync(self.lib, [], dict_to_modifiers(dict()))
        self.lib.booth.config_sync.assert_called_once_with(
            instance_name=None, skip_offline_nodes=False,
        )

    def test_lib_call_full(self):
        booth_cmd.sync(
            self.lib,
            [],
            dict_to_modifiers(
                {
                    "name": "my_booth",
                    "request-timeout": "10",
                    "skip-offline": True,
                    "booth-conf": "C",
                    "booth-key": "K",
                }
            ),
        )
        self.lib.booth.config_sync.assert_called_once_with(
            instance_name="my_booth", skip_offline_nodes=True,
        )


class BoothServiceTestMixin(BoothLibCallMixin):
    def test_too_many_args(self):
        self.assert_pcs_fail(
            f"booth {self.cmd_label} aaa",
            stdout_start=outdent(
                f"""
                Usage: pcs booth <command>
                    {self.cmd_label}"""
            ),
        )

    def test_lib_call_minimal(self):
        self.cli_cmd(self.lib, [], dict_to_modifiers(dict()))
        self.lib_cmd.assert_called_once_with(instance_name=None,)

    def test_lib_call_full(self):
        self.cli_cmd(self.lib, [], dict_to_modifiers(dict(name="my_booth")))
        self.lib_cmd.assert_called_once_with(instance_name="my_booth",)


class Enable(BoothServiceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["enable_booth"])
        self.cmd_label = "enable"
        self.lib_cmd = self.lib.booth.enable_booth
        self.cli_cmd = booth_cmd.enable


class Disable(BoothServiceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["disable_booth"])
        self.cmd_label = "disable"
        self.lib_cmd = self.lib.booth.disable_booth
        self.cli_cmd = booth_cmd.disable


class Start(BoothServiceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["start_booth"])
        self.cmd_label = "start"
        self.lib_cmd = self.lib.booth.start_booth
        self.cli_cmd = booth_cmd.start


class Stop(BoothServiceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["stop_booth"])
        self.cmd_label = "stop"
        self.lib_cmd = self.lib.booth.stop_booth
        self.cli_cmd = booth_cmd.stop


class Pull(BoothLibCallMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["pull_config"])

    def test_not_enough_args(self):
        self.assert_pcs_fail(
            "booth pull",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    pull"""
            ),
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth pull aaa bbb",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    pull"""
            ),
        )

    def test_lib_call_minimal(self):
        booth_cmd.pull(self.lib, ["node1"], dict_to_modifiers(dict()))
        self.lib.booth.pull_config.assert_called_once_with(
            "node1", instance_name=None,
        )

    def test_lib_call_full(self):
        booth_cmd.pull(
            self.lib,
            ["node1"],
            dict_to_modifiers({"name": "my_booth", "request-timeout": "10",}),
        )
        self.lib.booth.pull_config.assert_called_once_with(
            "node1", instance_name="my_booth",
        )


# disable printig the booth status so it won't break tests output
@mock.patch("pcs.cli.booth.command.print", new=lambda x: x)
class Status(BoothLibCallMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.lib.booth = mock.Mock(spec_set=["get_status"])
        self.lib.booth.get_status.return_value = {
            "ticket": "ticket_status",
            "peers": "peers_status",
            "daemon": "daemon_status",
        }

    def test_too_many_args(self):
        self.assert_pcs_fail(
            "booth status aaa",
            stdout_start=outdent(
                """
                Usage: pcs booth <command>
                    status"""
            ),
        )

    def test_lib_call_minimal(self):
        booth_cmd.status(self.lib, [], dict_to_modifiers(dict()))
        self.lib.booth.get_status.assert_called_once_with(instance_name=None,)

    def test_lib_call_full(self):
        booth_cmd.status(self.lib, [], dict_to_modifiers(dict(name="my_booth")))
        self.lib.booth.get_status.assert_called_once_with(
            instance_name="my_booth",
        )

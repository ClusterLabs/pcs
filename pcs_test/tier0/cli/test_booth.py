from unittest import (
    TestCase,
    mock,
)

from pcs.cli.booth import command as booth_cmd
from pcs.cli.common.errors import CmdLineInputError

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import dict_to_modifiers


class SetupTest(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["config_setup"])

    def test_lib_call_minimal(self):
        booth_cmd.config_setup(
            self.lib,
            ["sites", "1.1.1.1", "2.2.2.2", "3.3.3.3"],
            dict_to_modifiers({}),
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


class DestroyTest(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["config_destroy"])

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            booth_cmd.config_destroy(self.lib, ["aaa"], dict_to_modifiers({}))
        self.assertIsNone(cm.exception.message)
        self.lib.booth.config_destroy.assert_not_called()

    def test_lib_call_minimal(self):
        booth_cmd.config_destroy(self.lib, [], dict_to_modifiers({}))
        self.lib.booth.config_destroy.assert_called_once_with(
            ignore_config_load_problems=False,
            instance_name=None,
        )

    def test_lib_call_full(self):
        booth_cmd.config_destroy(
            self.lib, [], dict_to_modifiers(dict(name="my_booth", force=True))
        )
        self.lib.booth.config_destroy.assert_called_once_with(
            ignore_config_load_problems=True,
            instance_name="my_booth",
        )


class AddTicketTest(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["config_ticket_add"])

    def test_lib_call_minimal(self):
        booth_cmd.config_ticket_add(
            self.lib, ["ticketA"], dict_to_modifiers({})
        )
        self.lib.booth.config_ticket_add.assert_called_once_with(
            "ticketA",
            {},
            instance_name=None,
            allow_unknown_options=False,
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

    # pylint cannot possibly know this is being mixed into TestCase classes
    # pylint: disable=invalid-name
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["config_ticket_remove"])

    def test_lib_call_minimal(self):
        booth_cmd.config_ticket_remove(
            self.lib, ["ticketA"], dict_to_modifiers({})
        )
        self.lib.booth.config_ticket_remove.assert_called_once_with(
            "ticketA",
            instance_name=None,
        )

    def test_lib_call_full(self):
        booth_cmd.config_ticket_remove(
            self.lib,
            ["ticketA"],
            dict_to_modifiers(
                {
                    "name": "my_booth",
                    "booth-conf": "C",
                    "booth-key": "K",
                }
            ),
        )
        self.lib.booth.config_ticket_remove.assert_called_once_with(
            "ticketA",
            instance_name="my_booth",
        )


class DeleteTicketTest(DeleteRemoveTicketMixin, TestCase):
    command = "delete"


class RemoveTicketTest(DeleteRemoveTicketMixin, TestCase):
    command = "remove"


class CreateTest(AssertPcsMixin, TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["create_in_cluster"])

    def test_lib_call_minimal(self):
        booth_cmd.create_in_cluster(
            self.lib, ["ip", "1.2.3.4"], dict_to_modifiers({})
        )
        self.lib.booth.create_in_cluster.assert_called_once_with(
            "1.2.3.4",
            instance_name=None,
            allow_absent_resource_agent=False,
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
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["remove_from_cluster"])

    def test_lib_call_minimal(self):
        def resource_remove(something):
            return something

        booth_cmd.get_remove_from_cluster(resource_remove)(
            self.lib, [], dict_to_modifiers({})
        )
        self.lib.booth.remove_from_cluster.assert_called_once_with(
            resource_remove,
            instance_name=None,
            allow_remove_multiple=False,
        )

    def test_lib_call_full(self):
        def resource_remove(something):
            return something

        booth_cmd.get_remove_from_cluster(resource_remove)(
            self.lib, [], dict_to_modifiers(dict(name="my_booth", force=True))
        )
        self.lib.booth.remove_from_cluster.assert_called_once_with(
            resource_remove,
            instance_name="my_booth",
            allow_remove_multiple=True,
        )


class DeleteTest(DeleteRemoveTestMixin, TestCase):
    command = "delete"


class RemoveTest(DeleteRemoveTestMixin, TestCase):
    command = "remove"


class TicketGrantTest(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["ticket_grant"])

    def test_lib_call_minimal(self):
        booth_cmd.ticket_grant(self.lib, ["ticketA"], dict_to_modifiers({}))
        self.lib.booth.ticket_grant.assert_called_once_with(
            "ticketA",
            instance_name=None,
            site_ip=None,
        )

    def test_lib_call_full(self):
        booth_cmd.ticket_grant(
            self.lib,
            ["ticketA", "1.2.3.4"],
            dict_to_modifiers(dict(name="my_booth")),
        )
        self.lib.booth.ticket_grant.assert_called_once_with(
            "ticketA",
            instance_name="my_booth",
            site_ip="1.2.3.4",
        )


class TicketRevokeTest(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["ticket_revoke"])

    def test_lib_call_minimal(self):
        booth_cmd.ticket_revoke(self.lib, ["ticketA"], dict_to_modifiers({}))
        self.lib.booth.ticket_revoke.assert_called_once_with(
            "ticketA",
            instance_name=None,
            site_ip=None,
        )

    def test_lib_call_full(self):
        booth_cmd.ticket_revoke(
            self.lib,
            ["ticketA", "1.2.3.4"],
            dict_to_modifiers(dict(name="my_booth")),
        )
        self.lib.booth.ticket_revoke.assert_called_once_with(
            "ticketA",
            instance_name="my_booth",
            site_ip="1.2.3.4",
        )


# disable printig the booth config so it won't break tests output
@mock.patch("pcs.cli.booth.command.print", new=lambda x: x)
class ConfigTest(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["config_text"])

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            booth_cmd.config_show(
                self.lib, ["aaa", "bbb"], dict_to_modifiers({})
            )
        self.assertIsNone(cm.exception.message)
        self.lib.booth.config_text.assert_not_called()

    def test_lib_call_minimal(self):
        booth_cmd.config_show(self.lib, [], dict_to_modifiers({}))
        self.lib.booth.config_text.assert_called_once_with(
            instance_name=None,
            node_name=None,
        )

    def test_lib_call_full(self):
        booth_cmd.config_show(
            self.lib,
            ["node1"],
            dict_to_modifiers(
                {
                    "name": "my_booth",
                    "request-timeout": "10",
                }
            ),
        )
        self.lib.booth.config_text.assert_called_once_with(
            instance_name="my_booth",
            node_name="node1",
        )


class Restart(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["restart"])

    def test_lib_call_minimal(self):
        def resource_restart(something):
            return something

        booth_cmd.get_restart(resource_restart)(
            self.lib, [], dict_to_modifiers({})
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
        def resource_restart(something):
            return something

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


class Sync(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["config_sync"])

    def test_lib_call_minimal(self):
        booth_cmd.sync(self.lib, [], dict_to_modifiers({}))
        self.lib.booth.config_sync.assert_called_once_with(
            instance_name=None,
            skip_offline_nodes=False,
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
            instance_name="my_booth",
            skip_offline_nodes=True,
        )


class BoothServiceTestMixin:
    # pylint cannot possibly know this is being mixed into TestCase classes
    # pylint: disable=invalid-name
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])

    def test_lib_call_minimal(self):
        self.cli_cmd(self.lib, [], dict_to_modifiers({}))
        self.lib_cmd.assert_called_once_with(
            instance_name=None,
        )

    def test_lib_call_full(self):
        self.cli_cmd(self.lib, [], dict_to_modifiers(dict(name="my_booth")))
        self.lib_cmd.assert_called_once_with(
            instance_name="my_booth",
        )


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


class Pull(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["pull_config"])

    def test_lib_call_minimal(self):
        booth_cmd.pull(self.lib, ["node1"], dict_to_modifiers({}))
        self.lib.booth.pull_config.assert_called_once_with(
            "node1",
            instance_name=None,
        )

    def test_lib_call_full(self):
        booth_cmd.pull(
            self.lib,
            ["node1"],
            dict_to_modifiers(
                {
                    "name": "my_booth",
                    "request-timeout": "10",
                }
            ),
        )
        self.lib.booth.pull_config.assert_called_once_with(
            "node1",
            instance_name="my_booth",
        )


# disable printig the booth status so it won't break tests output
@mock.patch("pcs.cli.booth.command.print", new=lambda x: x)
class Status(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["booth"])
        self.lib.booth = mock.Mock(spec_set=["get_status"])
        self.lib.booth.get_status.return_value = {
            "ticket": "ticket_status",
            "peers": "peers_status",
            "daemon": "daemon_status",
        }

    def test_lib_call_minimal(self):
        booth_cmd.status(self.lib, [], dict_to_modifiers({}))
        self.lib.booth.get_status.assert_called_once_with(
            instance_name=None,
        )

    def test_lib_call_full(self):
        booth_cmd.status(self.lib, [], dict_to_modifiers(dict(name="my_booth")))
        self.lib.booth.get_status.assert_called_once_with(
            instance_name="my_booth",
        )

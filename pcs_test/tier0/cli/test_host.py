from unittest import TestCase, mock

from pcs import settings
from pcs.cli import host
from pcs.cli.common.errors import CmdLineInputError
from pcs.common.auth import HostAuthData, HostWithTokenAuthData
from pcs.common.host import Destination

from pcs_test.tools.misc import dict_to_modifiers


class HostAuth(TestCase):
    host_names = {
        "node-01": {
            "hostname": "node-01.example.com",
            "ipv4": "192.168.122.11",
            "ipv6": "[2620:52:0:25a4:1800:ff:fe00:1]",
        },
        "node-02": {
            "hostname": "node-02.example.com",
            "ipv4": "192.168.122.12",
            "ipv6": "[2620:52:0:25a4:1800:ff:fe00:2]",
        },
    }

    def setUp(self):
        self.lib = mock.Mock(spec_set=["auth"])
        self.lib.auth = mock.Mock(
            spec_set=["auth_hosts_token_no_sync", "auth_hosts"]
        )

    @staticmethod
    def _fixture_args(name_addr_port_tuple_list):
        arg_list = []
        for name, addr, port in name_addr_port_tuple_list:
            port_str = ":{}".format(port) if port is not None else ""
            arg_list.extend([name, f"addr={addr}{port_str}"])
        return arg_list

    def _assert_invalid_port(self, name_addr_port_tuple_list):
        arg_list = self._fixture_args(name_addr_port_tuple_list)
        with self.assertRaises(CmdLineInputError) as cm:
            host.auth_cmd(self.lib, arg_list, dict_to_modifiers({}))
        _, addr, port = name_addr_port_tuple_list[-1]
        self.assertEqual(
            (
                "Invalid port number in address '{addr}:{port}', use 1..65535"
            ).format(addr=addr, port=port),
            cm.exception.message,
        )
        self.lib.auth.auth_hosts.assert_not_called()
        self.lib.auth.auth_hosts_token_no_sync.assert_not_called()

    def _assert_valid_port(self, name_addr_port_tuple_list):
        arg_list = self._fixture_args(name_addr_port_tuple_list)
        host.auth_cmd(self.lib, arg_list, dict_to_modifiers({}))
        self.lib.auth.auth_hosts.assert_called_once_with(
            {
                name: HostAuthData(
                    username="hacluster",
                    password="password",
                    dest_list=[
                        Destination(
                            addr=addr
                            if addr.count(":") <= 1
                            else addr.strip("[]"),
                            port=port,
                        )
                    ],
                )
                for name, addr, port in name_addr_port_tuple_list
            }
        )
        self.lib.auth.auth_hosts_token_no_sync.assert_not_called()

    def run_port_subtests(self, assert_function, port_list):
        for addr_type in ["hostname", "ipv4", "ipv6"]:
            name_list = sorted(self.host_names.keys())[0 : len(port_list)]
            addr_list = [self.host_names[name][addr_type] for name in name_list]

            with self.subTest(addr_type=addr_type):
                self.lib.reset_mock()
                assert_function(
                    list(zip(name_list, addr_list, port_list, strict=False))
                )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            host.auth_cmd(self.lib, [], dict_to_modifiers({}))
        self.assertEqual("No host specified", cm.exception.message)

    def test_invalid_port_notanumber(self):
        self.run_port_subtests(self._assert_invalid_port, ["notanumber"])

    def test_invalid_port_lower_bound(self):
        self.run_port_subtests(self._assert_invalid_port, [0])

    def test_invalid_port_higher_bound(self):
        self.run_port_subtests(self._assert_invalid_port, [65536])

    def test_invalid_port_notanumber_multinode(self):
        self.run_port_subtests(
            self._assert_invalid_port,
            [1, "notanumber"],
        )

    def test_invalid_port_lower_bound_multinode(self):
        self.run_port_subtests(self._assert_invalid_port, [3000, 0])

    def test_invalid_port_higher_bound_hostname_multinode(self):
        self.run_port_subtests(self._assert_invalid_port, [65535, 65536])

    @mock.patch(
        "pcs.utils.get_user_and_pass", return_value=("hacluster", "password")
    )
    def test_valid_port(self, _):
        self.run_port_subtests(self._assert_valid_port, [3000])

    @mock.patch(
        "pcs.utils.get_user_and_pass", return_value=("hacluster", "password")
    )
    def test_valid_port_multinode(self, _):
        self.run_port_subtests(self._assert_valid_port, [3000, 5000])

    @mock.patch("pcs.utils.get_token_from_file", return_value="TOKEN")
    def test_token(self, mock_get_token):
        host.auth_cmd(
            self.lib, ["host1", "host2"], dict_to_modifiers({"token": "file"})
        )

        mock_get_token.assert_called_once_with("file")
        self.lib.auth.auth_hosts_token_no_sync.assert_called_once_with(
            {
                "host1": HostWithTokenAuthData(
                    token="TOKEN",
                    dest_list=[
                        Destination(
                            addr="host1", port=settings.pcsd_default_port
                        )
                    ],
                ),
                "host2": HostWithTokenAuthData(
                    token="TOKEN",
                    dest_list=[
                        Destination(
                            addr="host2", port=settings.pcsd_default_port
                        )
                    ],
                ),
            }
        )
        self.lib.auth.auth_hosts.assert_not_called()


class DeauthHosts(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["auth"])
        self.lib.auth = mock.Mock(
            spec_set=["deauth_hosts", "deauth_all_local_hosts"]
        )

    def test_success_no_args(self):
        host.deauth_cmd(self.lib, [], dict_to_modifiers({}))

        self.lib.auth.deauth_all_local_hosts.assert_called_once_with()
        self.lib.auth.deauth_hosts.assert_not_called()

    def test_success_args(self):
        host.deauth_cmd(self.lib, ["node1", "node2"], dict_to_modifiers({}))

        self.lib.auth.deauth_all_local_hosts.assert_not_called()
        self.lib.auth.deauth_hosts.assert_called_once_with(["node1", "node2"])

    def test_non_unique_args(self):
        with self.assertRaises(CmdLineInputError):
            host.deauth_cmd(self.lib, ["node1", "node1"], dict_to_modifiers({}))

        self.lib.auth.deauth_all_local_hosts.assert_not_called()
        self.lib.auth.deauth_hosts.assert_not_called()

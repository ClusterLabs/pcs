from unittest import (
    TestCase,
    mock,
)

from pcs import host
from pcs.cli.common.errors import CmdLineInputError

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
        self.lib = mock.Mock()
        self.patch_get_user_and_pass = mock.patch(
            "pcs.utils.get_user_and_pass",
            return_value=("hacluster", "password"),
        )
        self.patch_auth_hosts = mock.patch("pcs.utils.auth_hosts")

    @staticmethod
    def _fixture_args(name_addr_port_tuple_list):
        arg_list = []
        for name, addr, port in name_addr_port_tuple_list:
            port_str = ":{}".format(port) if port is not None else ""
            arg_list.extend([name, f"addr={addr}{port_str}"])
        return arg_list

    def _assert_invalid_port(self, name_addr_port_tuple_list):
        arg_list = self._fixture_args(name_addr_port_tuple_list)
        mock_auth_hosts = self.patch_auth_hosts.start()
        with self.assertRaises(CmdLineInputError) as cm:
            host.auth_cmd(self.lib, arg_list, dict_to_modifiers({}))
        _, addr, port = name_addr_port_tuple_list[-1]
        self.assertEqual(
            (
                "Invalid port number in address '{addr}:{port}', use 1..65535"
            ).format(addr=addr, port=port),
            cm.exception.message,
        )
        mock_auth_hosts.assert_not_called()
        self.patch_auth_hosts.stop()

    def _assert_valid_port(self, name_addr_port_tuple_list):
        arg_list = self._fixture_args(name_addr_port_tuple_list)
        mock_get_user_and_pass = self.patch_get_user_and_pass.start()
        mock_auth_hosts = self.patch_auth_hosts.start()
        host.auth_cmd(self.lib, arg_list, dict_to_modifiers({}))
        mock_get_user_and_pass.assert_called_once_with()
        mock_auth_hosts.assert_called_once_with(
            {
                name: {
                    "dest_list": [
                        dict(
                            addr=(
                                addr
                                if addr.count(":") <= 1
                                else addr.strip("[]")
                            ),
                            port=port,
                        )
                    ],
                    "username": "hacluster",
                    "password": "password",
                }
                for name, addr, port in name_addr_port_tuple_list
            }
        )
        self.patch_get_user_and_pass.stop()
        self.patch_auth_hosts.stop()

    def run_port_subtests(self, assert_function, port_list):
        for addr_type in ["hostname", "ipv4", "ipv6"]:
            name_list = sorted(self.host_names.keys())[0 : len(port_list)]
            addr_list = [self.host_names[name][addr_type] for name in name_list]

            with self.subTest(addr_type=addr_type):
                assert_function(list(zip(name_list, addr_list, port_list)))

    @mock.patch("pcs.utils.auth_hosts")
    def test_no_args(self, mock_auth_hosts):
        with self.assertRaises(CmdLineInputError) as cm:
            host.auth_cmd(self.lib, [], dict_to_modifiers({}))
        self.assertEqual("No host specified", cm.exception.message)
        mock_auth_hosts.assert_not_called()

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

    def test_valid_port(self):
        self.run_port_subtests(self._assert_valid_port, [3000])

    def test_valid_port_multinode(self):
        self.run_port_subtests(self._assert_valid_port, [3000, 5000])

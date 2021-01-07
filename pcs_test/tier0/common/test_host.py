from unittest import TestCase

from pcs import settings
from pcs.common import host


def _dest(addr, port):
    return dict(addr=addr, port=port)


class PcsKnownHostFromKnownHost(TestCase):
    def setUp(self):
        self.name = "host name"
        self.token = "token"

    def test_from_known_host(self):
        known_host = host.PcsKnownHost.from_known_host_file_dict(
            self.name,
            dict(
                dest_list=[_dest("addr1", "port1"), _dest("addr2", "port2")],
                token=self.token,
            ),
        )
        self.assertEqual(self.name, known_host.name)
        self.assertEqual(self.token, known_host.token)
        self.assertEqual(
            [
                host.Destination("addr1", "port1"),
                host.Destination("addr2", "port2"),
            ],
            known_host.dest_list,
        )
        self.assertEqual(host.Destination("addr1", "port1"), known_host.dest)

    def test_missing_token(self):
        known_host_call = lambda: host.PcsKnownHost.from_known_host_file_dict(
            self.name,
            dict(
                dest_list=[_dest("addr1", "port1"), _dest("addr2", "port2")],
            ),
        )
        self.assertRaises(KeyError, known_host_call)

    def test_missing_port(self):
        known_host_call = lambda: host.PcsKnownHost.from_known_host_file_dict(
            self.name,
            dict(
                dest_list=[_dest("addr1", "port1"), dict(addr="addr2")],
                token=self.token,
            ),
        )
        self.assertRaises(KeyError, known_host_call)

    def test_missing_addr(self):
        known_host_call = lambda: host.PcsKnownHost.from_known_host_file_dict(
            self.name,
            dict(
                dest_list=[_dest("addr1", "port1"), dict(port="port2")],
                token=self.token,
            ),
        )
        self.assertRaises(KeyError, known_host_call)

    def test_no_dest_list(self):
        known_host_call = lambda: host.PcsKnownHost.from_known_host_file_dict(
            self.name, dict(token=self.token)
        )
        self.assertRaises(KeyError, known_host_call)

    def test_dest_list_empty(self):
        known_host_call = lambda: host.PcsKnownHost.from_known_host_file_dict(
            self.name, dict(dest_list=[], token=self.token)
        )
        self.assertRaises(KeyError, known_host_call)


class PcsKnownHost(TestCase):
    def setUp(self):
        self.name = "host_name"
        self.default_dest = host.Destination(
            self.name, settings.pcsd_default_port
        )

    def test_dest_list_none(self):
        self.assertEqual(
            self.default_dest, host.PcsKnownHost(self.name, None, None).dest
        )

    def test_dest_list_empty(self):
        self.assertEqual(
            self.default_dest, host.PcsKnownHost(self.name, None, []).dest
        )

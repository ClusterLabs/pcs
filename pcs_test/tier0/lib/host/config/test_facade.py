from unittest import TestCase

from pcs.common.host import Destination, PcsKnownHost
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.host.config.types import KnownHosts


class Facade(TestCase):
    def setUp(self):
        self.facade = KnownHostsFacade(
            KnownHosts(
                format_version=1,
                data_version=10,
                known_hosts={
                    "a": PcsKnownHost(
                        name="a",
                        token="abcd",
                        dest_list=[Destination("10.0.0.1", 2224)],
                    )
                },
            )
        )

    def test_create(self):
        facade = KnownHostsFacade.create()

        self.assertEqual(1, facade.data_version)
        self.assertEqual(dict(), facade.known_hosts)

    def test_ok(self):
        self.assertEqual(10, self.facade.data_version)
        self.assertEqual(
            {
                "a": PcsKnownHost(
                    name="a",
                    token="abcd",
                    dest_list=[Destination("10.0.0.1", 2224)],
                )
            },
            self.facade.known_hosts,
        )

    def test_update_known_hosts_add_new_host(self):
        self.facade.update_known_hosts(
            [
                PcsKnownHost(
                    name="b",
                    token="wxyz",
                    dest_list=[Destination("10.0.0.2", 2224)],
                )
            ]
        )

        self.assertEqual(
            {
                "a": PcsKnownHost(
                    name="a",
                    token="abcd",
                    dest_list=[Destination("10.0.0.1", 2224)],
                ),
                "b": PcsKnownHost(
                    name="b",
                    token="wxyz",
                    dest_list=[Destination("10.0.0.2", 2224)],
                ),
            },
            self.facade.known_hosts,
        )

    def test_update_known_hosts_rewrite_existing(self):
        self.facade.update_known_hosts(
            [
                PcsKnownHost(
                    name="a",
                    token="wxyz",
                    dest_list=[Destination("10.0.0.2", 2224)],
                )
            ]
        )

        self.assertEqual(
            {
                "a": PcsKnownHost(
                    name="a",
                    token="wxyz",
                    dest_list=[Destination("10.0.0.2", 2224)],
                ),
            },
            self.facade.known_hosts,
        )

    def test_remove_known_hosts(self):
        facade = KnownHostsFacade(
            KnownHosts(
                format_version=1,
                data_version=10,
                known_hosts={
                    "a": PcsKnownHost(
                        name="a",
                        token="abcd",
                        dest_list=[Destination("10.0.0.1", 2224)],
                    ),
                    "b": PcsKnownHost(
                        name="b",
                        token="wxyz",
                        dest_list=[Destination("10.0.0.2", 2224)],
                    ),
                },
            )
        )

        facade.remove_known_hosts(["b", "c"])

        self.assertEqual(
            {
                "a": PcsKnownHost(
                    name="a",
                    token="abcd",
                    dest_list=[Destination("10.0.0.1", 2224)],
                )
            },
            self.facade.known_hosts,
        )

    def test_set_version(self):
        self.assertEqual(self.facade.data_version, 10)
        self.facade.set_data_version(1000)
        self.assertEqual(self.facade.data_version, 1000)

from unittest import TestCase

from pcs.common.host import Destination, PcsKnownHost
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.host.config.types import KnownHosts


class Facade(TestCase):
    def test_create(self):
        facade = KnownHostsFacade.create()

        self.assertEqual(1, facade.data_version)
        self.assertEqual(dict(), facade.known_hosts)

    def test_ok(self):
        facade = KnownHostsFacade(
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

        self.assertEqual(10, facade.data_version)
        self.assertEqual(
            {
                "a": PcsKnownHost(
                    name="a",
                    token="abcd",
                    dest_list=[Destination("10.0.0.1", 2224)],
                )
            },
            facade.known_hosts,
        )

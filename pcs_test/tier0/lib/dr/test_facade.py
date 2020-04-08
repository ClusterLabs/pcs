from unittest import TestCase

from pcs.common.dr import DrRole
from pcs.lib.dr.config import facade


class Facade(TestCase):
    def test_create(self):
        for role in DrRole:
            with self.subTest(local_role=role.value):
                self.assertEqual(
                    dict(local=dict(role=role.value,), remote_sites=[],),
                    facade.Facade.create(role).config,
                )

    def test_local_role(self):
        for role in DrRole:
            with self.subTest(local_role=role.value):
                cfg = facade.Facade(
                    {"local": {"role": role.value,}, "remote_sites": [],}
                )
                self.assertEqual(cfg.local_role, role)

    def test_add_site(self):
        node_list = [f"node{i}" for i in range(4)]
        cfg = facade.Facade.create(DrRole.PRIMARY)
        cfg.add_site(DrRole.RECOVERY, node_list)
        self.assertEqual(
            dict(
                local=dict(role=DrRole.PRIMARY.value,),
                remote_sites=[
                    dict(
                        role=DrRole.RECOVERY.value,
                        nodes=[dict(name=node) for node in node_list],
                    ),
                ],
            ),
            cfg.config,
        )


class GetRemoteSiteList(TestCase):
    def test_no_sites(self):
        cfg = facade.Facade(
            {"local": {"role": DrRole.PRIMARY.value,}, "remote_sites": [],}
        )
        self.assertEqual(cfg.get_remote_site_list(), [])

    def test_one_site(self):
        cfg = facade.Facade(
            {
                "local": {"role": DrRole.PRIMARY.value,},
                "remote_sites": [
                    {
                        "role": DrRole.RECOVERY.value,
                        "nodes": [{"name": "node1"},],
                    },
                ],
            }
        )
        self.assertEqual(
            cfg.get_remote_site_list(),
            [facade.DrSite(role=DrRole.RECOVERY, node_name_list=["node1"]),],
        )

    def test_more_sites(self):
        cfg = facade.Facade(
            {
                "local": {"role": DrRole.RECOVERY.value,},
                "remote_sites": [
                    {
                        "role": DrRole.PRIMARY.value,
                        "nodes": [{"name": "nodeA1"}, {"name": "nodeA2"},],
                    },
                    {
                        "role": DrRole.RECOVERY.value,
                        "nodes": [{"name": "nodeB1"}, {"name": "nodeB2"},],
                    },
                ],
            }
        )
        self.assertEqual(
            cfg.get_remote_site_list(),
            [
                facade.DrSite(
                    role=DrRole.PRIMARY, node_name_list=["nodeA1", "nodeA2"]
                ),
                facade.DrSite(
                    role=DrRole.RECOVERY, node_name_list=["nodeB1", "nodeB2"]
                ),
            ],
        )

    def test_no_nodes(self):
        cfg = facade.Facade(
            {
                "local": {"role": DrRole.PRIMARY.value,},
                "remote_sites": [
                    {"role": DrRole.RECOVERY.value, "nodes": [],},
                ],
            }
        )
        self.assertEqual(
            cfg.get_remote_site_list(),
            [facade.DrSite(role=DrRole.RECOVERY, node_name_list=[]),],
        )

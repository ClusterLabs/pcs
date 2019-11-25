from unittest import TestCase

from pcs.lib.dr.config import facade


class Facade(TestCase):
    def test_create(self):
        for role in facade.DrRole:
            with self.subTest(local_role=role.value):
                self.assertEqual(
                    dict(
                        local=dict(
                            role=role.value,
                        ),
                        remote_sites=[],
                    ),
                    facade.Facade.create(role).config,
                )

    def test_add_site(self):
        node_list = [f"node{i}" for i in range(4)]
        cfg = facade.Facade.create(facade.DrRole.PRIMARY)
        cfg.add_site(facade.DrRole.RECOVERY, node_list)
        self.assertEqual(
            dict(
                local=dict(
                    role=facade.DrRole.PRIMARY.value,
                ),
                remote_sites=[
                    dict(
                        role=facade.DrRole.RECOVERY.value,
                        nodes=[dict(name=node) for node in node_list],
                    ),
                ]
            ),
            cfg.config
        )

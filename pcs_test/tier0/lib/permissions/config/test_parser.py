import json
from unittest import TestCase

from pcs.common.interface.dto import to_dict
from pcs.common.permissions.types import (
    PermissionAccessType,
    PermissionTargetType,
)
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.permissions.config.parser import (
    ParserError,
    ParserV2,
)
from pcs.lib.permissions.config.types import (
    ClusterEntry,
    ClusterPermissions,
    ConfigV2,
    PermissionEntry,
)


class ParserV2Test(TestCase):
    @staticmethod
    def _run_parse(data):
        return ParserV2.parse(json.dumps(data).encode())

    def test_not_json(self):
        with self.assertRaises(ParserErrorException):
            ParserV2.parse("not json".encode())

    def test_root_element_not_an_object(self):
        with self.assertRaises(ParserError):
            self._run_parse([dict(key="value"), "string", 1])

    def test_format_version_missing(self):
        with self.assertRaises(ParserError):
            self._run_parse(
                dict(
                    data_version=1,
                    clusters=[],
                    permissions=dict(local_cluster=[]),
                )
            )

    def test_format_version_unsupported(self):
        with self.assertRaises(ParserError):
            self._run_parse(
                dict(
                    data_version=1,
                    format_version=3,
                    clusters=[],
                    permissions=dict(local_cluster=[]),
                )
            )

    def test_invalid_data(self):
        with self.assertRaises(ParserError):
            self._run_parse(
                dict(
                    format_version=2,
                    data_version=1,
                    clusters=[
                        dict(
                            name="testcluster",
                            nodes=["node1", "node2", "node0"],
                        ),
                        dict(name="invalid data"),
                    ],
                    permissions=dict(local_cluster=[]),
                )
            )

    def test_valid_data(self):
        config = ConfigV2(
            data_version=1,
            clusters=[
                ClusterEntry(
                    name="testcluster",
                    nodes=["node1", "node2", "node0"],
                ),
                ClusterEntry(
                    name="cluster name",
                    nodes=["n1", "n0"],
                ),
            ],
            permissions=ClusterPermissions(
                local_cluster=[
                    PermissionEntry(
                        name="user1",
                        type=PermissionTargetType.USER,
                        allow=[PermissionAccessType.READ],
                    ),
                    PermissionEntry(
                        name="group1",
                        type=PermissionTargetType.GROUP,
                        allow=[
                            PermissionAccessType.GRANT,
                            PermissionAccessType.WRITE,
                        ],
                    ),
                ]
            ),
        )
        self.assertEqual(
            self._run_parse(dict(**to_dict(config), format_version=2)), config
        )

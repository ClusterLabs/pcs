from typing import Optional
from unittest import (
    TestCase,
    mock,
)

from pcs.cli.resource import command
from pcs.common import const
from pcs.common.const import (
    PcmkRoleType,
    PcmkStatusRoleType,
)
from pcs.common.status_dto import (
    BundleReplicaStatusDto,
    BundleStatusDto,
    CloneStatusDto,
    GroupStatusDto,
    PrimitiveStatusDto,
    ResourcesStatusDto,
)


def _fixture_primitive_status_dto(
    resource_id: str,
    resource_agent: str = "ocf:pacemaker:Dummy",
    target_role: Optional[PcmkRoleType] = None,
    role: PcmkStatusRoleType = const.PCMK_STATUS_ROLE_STARTED,
    managed: bool = True,
    node_names: Optional[list[str]] = None,
) -> PrimitiveStatusDto:
    return PrimitiveStatusDto(
        resource_id=resource_id,
        instance_id=None,
        resource_agent=resource_agent,
        role=role,
        target_role=target_role,
        active=False,
        orphaned=False,
        blocked=False,
        maintenance=False,
        description=None,
        failed=False,
        managed=managed,
        failure_ignored=False,
        node_names=node_names if node_names else [],
        pending=None,
        locked_to=None,
    )


def _fixture_group_status_dto(
    group_size,
    running_on_nodes,
    instance_id=None,
    agent_name="ocf:pacemaker:Stateful",
):
    return GroupStatusDto(
        resource_id="G1",
        instance_id=instance_id,
        maintenance=False,
        description=None,
        managed=True,
        disabled=False,
        members=[
            _fixture_primitive_status_dto(
                f"R{i}",
                agent_name,
                node_names=running_on_nodes,
            )
            for i in range(1, group_size)
        ],
    )


def _fixture_bundle_status_dto(replicas):
    return BundleStatusDto(
        resource_id="B1",
        type="docker",
        image="pcs:test",
        unique=True,
        maintenance=False,
        description=None,
        managed=False,
        failed=False,
        replicas=replicas,
    )


def _fixture_bundle_replica_dto(replica_id, container):
    return BundleReplicaStatusDto(
        replica_id=replica_id,
        member=None,
        remote=None,
        ip_address=None,
        container=container,
    )


def _fixture_clone_status_dto(multi_state, instances):
    return CloneStatusDto(
        resource_id="clone",
        multi_state=multi_state,
        unique=False,
        maintenance=False,
        description=None,
        managed=True,
        disabled=False,
        failed=False,
        failure_ignored=False,
        target_role=None,
        instances=instances,
    )


class GetResourceMessage(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["status"])

        self.lib.status = mock.Mock(spec_set=["resources_status"])
        self.lib.status.resources_status = self.mock_resources_status = (
            mock.Mock()
        )

    def test_bundle_not_running(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_bundle_status_dto(
                    replicas=[
                        _fixture_bundle_replica_dto(
                            replica_id=0,
                            container=_fixture_primitive_status_dto(
                                "B1-docker-0",
                                "ocf:heartbeat:docker",
                                role=const.PCMK_STATUS_ROLE_STOPPED,
                                managed=False,
                                node_names=["node1"],
                            ),
                        ),
                    ],
                )
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "B1"),
            "Resource 'B1' is not running on any nodes",
        )

    def test_bundle_running_one_replica(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_bundle_status_dto(
                    replicas=[
                        _fixture_bundle_replica_dto(
                            replica_id="0",
                            container=_fixture_primitive_status_dto(
                                "B1-docker-0",
                                "ocf:heartbeat:docker",
                                node_names=["node1"],
                            ),
                        ),
                    ],
                )
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "B1"),
            "Resource 'B1' is running on node 'node1'",
        )

    def test_bundle_running_and_failed(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_bundle_status_dto(
                    replicas=[
                        _fixture_bundle_replica_dto(
                            replica_id="0",
                            container=_fixture_primitive_status_dto(
                                "B1-docker-0",
                                "ocf:heartbeat:docker",
                                node_names=["node1"],
                            ),
                        ),
                        _fixture_bundle_replica_dto(
                            replica_id="1",
                            container=_fixture_primitive_status_dto(
                                "B1-docker-1",
                                "ocf:heartbeat:docker",
                                node_names=["node2"],
                            ),
                        ),
                        _fixture_bundle_replica_dto(
                            replica_id="2",
                            container=_fixture_primitive_status_dto(
                                "B1-docker-2",
                                "ocf:heartbeat:docker",
                                role=const.PCMK_STATUS_ROLE_STOPPED,
                                node_names=[],
                            ),
                        ),
                    ],
                )
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "B1"),
            "Resource 'B1' is running on nodes 'node1', 'node2'",
        )

    def test_bundle_running_multiple_replicas_one_node(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_bundle_status_dto(
                    replicas=[
                        _fixture_bundle_replica_dto(
                            replica_id="0",
                            container=_fixture_primitive_status_dto(
                                "B1-docker-0",
                                "ocf:heartbeat:docker",
                                node_names=["node1"],
                            ),
                        ),
                        _fixture_bundle_replica_dto(
                            replica_id="1",
                            container=_fixture_primitive_status_dto(
                                "B1-docker-1",
                                "ocf:heartbeat:docker",
                                node_names=["node1"],
                            ),
                        ),
                    ],
                )
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "B1"),
            "Resource 'B1' is running on node 'node1'",
        )

    def test_primitive(self):
        status_expected_msg = {
            const.PCMK_STATUS_ROLE_STARTED: "Resource 'R1' is running on node 'node1'"
        }
        status_expected_msg.update(
            {
                status: "Resource 'R1' is not running on any nodes"
                for status in [
                    const.PCMK_STATUS_ROLE_STARTING,
                    const.PCMK_STATUS_ROLE_STOPPING,
                    const.PCMK_STATUS_ROLE_STOPPED,
                ]
            }
        )
        for status, expected_msg in status_expected_msg.items():
            with self.subTest(status=status, expected_msg=expected_msg):
                self.mock_resources_status.return_value = ResourcesStatusDto(
                    [
                        _fixture_primitive_status_dto(
                            "R1",
                            role=status,
                            node_names=["node1"],
                        ),
                    ]
                )
                self.assertEqual(
                    command.get_resource_status_msg(self.lib, "R1"),
                    expected_msg,
                )

    def test_cloned_group_one_instance(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_clone_status_dto(
                    multi_state=True,
                    instances=[
                        _fixture_group_status_dto(
                            instance_id=0,
                            group_size=3,
                            running_on_nodes=["node1"],
                        )
                    ],
                ),
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "clone"),
            "Resource 'clone' is running on node 'node1'",
        )

    def test_cloned_group_more_instances(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_clone_status_dto(
                    multi_state=True,
                    instances=[
                        _fixture_group_status_dto(
                            instance_id=0,
                            group_size=3,
                            running_on_nodes=["node1"],
                        ),
                        _fixture_group_status_dto(
                            instance_id=1,
                            group_size=3,
                            running_on_nodes=["node2"],
                        ),
                    ],
                ),
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "clone"),
            "Resource 'clone' is running on nodes 'node1', 'node2'",
        )

    def test_clone_one_instance(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_clone_status_dto(
                    multi_state=False,
                    instances=[
                        _fixture_primitive_status_dto(
                            "clone",
                            node_names=["node1"],
                        )
                    ],
                ),
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "clone"),
            "Resource 'clone' is running on node 'node1'",
        )

    def test_clone_more_instances(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_clone_status_dto(
                    multi_state=False,
                    instances=[
                        _fixture_primitive_status_dto(
                            "R6", node_names=["node1"]
                        ),
                        _fixture_primitive_status_dto(
                            "R6", node_names=["node1"]
                        ),
                        _fixture_primitive_status_dto(
                            "R6", node_names=["node2"]
                        ),
                        _fixture_primitive_status_dto(
                            "R6", node_names=["node2"]
                        ),
                    ],
                ),
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "clone"),
            "Resource 'clone' is running on nodes 'node1', 'node2'",
        )

    def test_clone_promotable(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_clone_status_dto(
                    multi_state=False,
                    instances=[
                        _fixture_primitive_status_dto(
                            "R6",
                            node_names=["node1"],
                            role=const.PCMK_STATUS_ROLE_PROMOTED,
                        ),
                        _fixture_primitive_status_dto(
                            "R6",
                            node_names=["node2"],
                            role=const.PCMK_STATUS_ROLE_UNPROMOTED,
                        ),
                        _fixture_primitive_status_dto(
                            "R6",
                            node_names=["node3"],
                            role=const.PCMK_STATUS_ROLE_DEMOTING,
                        ),
                        _fixture_primitive_status_dto(
                            "R6",
                            node_names=["node3"],
                            role=const.PCMK_STATUS_ROLE_PROMOTING,
                        ),
                    ],
                ),
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "clone"),
            "Resource 'clone' is promoted on node 'node1'; unpromoted on "
            "node 'node2'",
        )

    def test_group(self):
        self.mock_resources_status.return_value = ResourcesStatusDto(
            [
                _fixture_group_status_dto(
                    group_size=2,
                    running_on_nodes=["node1", "node2"],
                    agent_name="ocf:pacemaker:Dummy",
                ),
            ]
        )
        self.assertEqual(
            command.get_resource_status_msg(self.lib, "G1"),
            "Resource 'G1' is running on nodes 'node1', 'node2'",
        )

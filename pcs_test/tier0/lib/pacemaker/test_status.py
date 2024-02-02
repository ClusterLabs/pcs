# pylint: disable=too-many-lines
from typing import (
    Optional,
    Sequence,
    Union,
)
from unittest import TestCase

from lxml import etree

from pcs.common import reports
from pcs.common.const import (
    PCMK_ROLE_STARTED,
    PCMK_ROLE_UNKNOWN,
    PCMK_ROLES,
    PCMK_STATUS_ROLE_STARTED,
    PCMK_STATUS_ROLE_STOPPED,
    PCMK_STATUS_ROLE_UNKNOWN,
    PCMK_STATUS_ROLE_UNPROMOTED,
    PCMK_STATUS_ROLES,
    PCMK_STATUS_ROLES_PENDING,
    PCMK_STATUS_ROLES_RUNNING,
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
from pcs.lib.pacemaker import status

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor


def fixture_primitive_xml(
    resource_id: str = "resource",
    resource_agent: str = "ocf:heartbeat:Dummy",
    role: PcmkStatusRoleType = PCMK_STATUS_ROLE_STARTED,
    target_role: Optional[str] = None,
    managed: bool = True,
    node_names: Sequence[str] = ("node1",),
    add_optional_args: bool = False,
) -> str:
    target_role = (
        f'target_role="{target_role}"' if target_role is not None else ""
    )
    active = role in PCMK_STATUS_ROLES_RUNNING
    description = 'description="Test description"' if add_optional_args else ""
    pending = 'pending="test"' if add_optional_args else ""
    locked_to = 'locked_to="test"' if add_optional_args else ""

    nodes = "\n".join(
        f'<node name="{node}" id="{i}" cached="true"/>'
        for (i, node) in enumerate(node_names)
    )

    return f"""
        <resource
            id="{resource_id}"
            resource_agent="{resource_agent}"
            role="{role}"
            {target_role}
            active="{active}"
            orphaned="false"
            blocked="false"
            maintenance="false"
            {description}
            managed="{managed}"
            failed="false"
            failure_ignored="false"
            {pending}
            {locked_to}
            nodes_running_on="{len(node_names)}"
        >
            {nodes}
        </resource>
    """


def fixture_primitive_dto(
    resource_id: str = "resource",
    resource_agent: str = "ocf:heartbeat:Dummy",
    role: PcmkStatusRoleType = PCMK_STATUS_ROLE_STARTED,
    target_role: Optional[str] = None,
    managed: bool = True,
    node_names: Sequence[str] = ("node1",),
    add_optional_args: bool = False,
) -> PrimitiveStatusDto:
    return PrimitiveStatusDto(
        resource_id,
        resource_agent,
        role,
        target_role,
        active=role in PCMK_STATUS_ROLES_RUNNING,
        orphaned=False,
        blocked=False,
        maintenance=False,
        description="Test description" if add_optional_args else None,
        managed=managed,
        failed=False,
        failure_ignored=False,
        node_names=list(node_names),
        pending="test" if add_optional_args else None,
        locked_to="test" if add_optional_args else None,
    )


def fixture_group_xml(
    resource_id: str = "resource-group",
    description: Optional[str] = None,
    members: Sequence[str] = (),
) -> str:
    description = (
        f'description="{description}"' if description is not None else ""
    )
    members = "\n".join(members)
    return f"""
        <group
            id="{resource_id}"
            number_resources="{len(members)}"
            maintenance="false"
            {description}
            managed="true"
            disabled="false"
        >
            {members}
        </group>
    """


def fixture_group_dto(
    resource_id: str = "resource-group",
    description: Optional[str] = None,
    members: Sequence[PrimitiveStatusDto] = (),
) -> GroupStatusDto:
    return GroupStatusDto(
        resource_id,
        maintenance=False,
        description=description,
        managed=True,
        disabled=False,
        members=list(members),
    )


def fixture_clone_xml(
    resource_id: str = "resource-clone",
    multi_state: bool = False,
    unique: bool = False,
    description: Optional[str] = None,
    target_role: Optional[str] = None,
    instances: Sequence[str] = (),
) -> str:
    description = (
        f'description="{description}"' if description is not None else ""
    )
    target_role = (
        f'target_role="{target_role}"' if target_role is not None else ""
    )
    instances = "\n".join(instances)
    return f"""
        <clone
            id="{resource_id}"
            multi_state="{multi_state}"
            unique="{unique}"
            maintenance="false"
            {description}
            managed="true"
            disabled="false"
            failed="false"
            failure_ignored="false"
            {target_role}
        >
            {instances}
        </clone>
    """


def fixture_clone_dto(
    resource_id: str = "resource-clone",
    multi_state: bool = False,
    unique: bool = False,
    description: Optional[str] = None,
    target_role: Optional[str] = None,
    instances: Union[
        Sequence[PrimitiveStatusDto], Sequence[GroupStatusDto]
    ] = (),
) -> CloneStatusDto:
    return CloneStatusDto(
        resource_id,
        multi_state,
        unique,
        maintenance=False,
        description=description,
        managed=True,
        disabled=False,
        failed=False,
        failure_ignored=False,
        target_role=target_role,
        instances=list(instances),
    )


def fixture_replica_xml(
    bundle_id: str = "resource-bundle",
    replica_id: str = "0",
    bundle_type: str = "podman",
    ip: bool = False,
    node_name: str = "node1",
    member: Optional[str] = None,
) -> str:
    ip_resource = fixture_primitive_xml(
        resource_id=f"{bundle_id}-ip-192.168.122.{replica_id}",
        resource_agent="ocf:heartbeat:IPaddr2",
        node_names=[node_name],
    )
    remote_resource = fixture_primitive_xml(
        resource_id=f"{bundle_id}-{replica_id}",
        resource_agent="ocf:pacemaker:remote",
        node_names=[node_name],
    )
    container_resource = fixture_primitive_xml(
        resource_id=f"{bundle_id}-{bundle_type}-{replica_id}",
        resource_agent=f"ocf:heartbeat:{bundle_type}",
        node_names=[node_name],
    )
    return f"""
        <replica id="{replica_id}">
            {ip_resource if ip else ""}
            {member if member is not None else ""}
            {container_resource}
            {remote_resource if member is not None else ""}
        </replica>
    """


def fixture_replica_dto(
    bundle_id: str = "resource-bundle",
    replica_id: str = "0",
    bundle_type: str = "podman",
    ip: bool = False,
    node_name: str = "node1",
    member: Optional[PrimitiveStatusDto] = None,
) -> BundleReplicaStatusDto:
    ip_resource = fixture_primitive_dto(
        resource_id=f"{bundle_id}-ip-192.168.122.{replica_id}",
        resource_agent="ocf:heartbeat:IPaddr2",
        node_names=[node_name],
    )
    remote_resource = fixture_primitive_dto(
        resource_id=f"{bundle_id}-{replica_id}",
        resource_agent="ocf:pacemaker:remote",
        node_names=[node_name],
    )
    container_resource = fixture_primitive_dto(
        resource_id=f"{bundle_id}-{bundle_type}-{replica_id}",
        resource_agent=f"ocf:heartbeat:{bundle_type}",
        node_names=[node_name],
    )
    return BundleReplicaStatusDto(
        replica_id,
        member,
        remote_resource if member is not None else None,
        container_resource,
        ip_resource if ip else None,
    )


def fixture_bundle_xml(
    resource_id: str = "resource-bundle", replicas: Sequence[str] = ()
) -> str:
    replicas = "\n".join(replicas)
    return f"""
        <bundle
            id="{resource_id}"
            type="podman"
            image="localhost/pcmktest:http"
            unique="false"
            maintenance="false"
            managed="true"
            failed="false"
        >
            {replicas}
        </bundle>
    """


def fixture_bundle_dto(
    resource_id: str = "resource-bundle",
    replicas: Sequence[BundleReplicaStatusDto] = (),
) -> BundleStatusDto:
    return BundleStatusDto(
        resource_id,
        "podman",
        "localhost/pcmktest:http",
        False,
        False,
        None,
        True,
        False,
        list(replicas),
    )


def fixture_crm_mon_xml(resources: list[str]) -> str:
    # we only care about the resources element,
    # omitting other parts to make the string shorter
    resources = "\n".join(resources)
    return f"""
        <pacemaker-result
            api-version="2.30"
            request="/usr/sbin/crm_mon --one-shot --inactive --output-as xml"
        >
        <resources>
            {resources}
        </resources>
        <status code="0" message="OK"/>
        </pacemaker-result>
    """


class TestPrimitiveStatusToDto(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()

    def test_simple(self):
        primitive_xml = etree.fromstring(fixture_primitive_xml())

        result = status._primitive_to_dto(self.report_processor, primitive_xml)

        self.assertEqual(result, fixture_primitive_dto())
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_empty_node_list(self):
        primitive_xml = etree.fromstring(
            fixture_primitive_xml(role=PCMK_STATUS_ROLE_STOPPED, node_names=[])
        )
        result = status._primitive_to_dto(self.report_processor, primitive_xml)

        self.assertEqual(
            result,
            fixture_primitive_dto(role=PCMK_STATUS_ROLE_STOPPED, node_names=[]),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_all_attributes(self):
        primitive_xml = etree.fromstring(
            fixture_primitive_xml(
                target_role=PCMK_STATUS_ROLE_STOPPED, add_optional_args=True
            )
        )

        result = status._primitive_to_dto(self.report_processor, primitive_xml)

        self.assertEqual(
            result,
            fixture_primitive_dto(
                target_role=PCMK_STATUS_ROLE_STOPPED, add_optional_args=True
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_remove_clone_suffix(self):
        primitive_xml = etree.fromstring(
            fixture_primitive_xml(resource_id="resource:0")
        )

        result = status._primitive_to_dto(
            self.report_processor, primitive_xml, True
        )

        self.assertEqual(result, fixture_primitive_dto())
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_running_on_multiple_nodes(self):
        primitive_xml = etree.fromstring(
            fixture_primitive_xml(node_names=["node1", "node2", "node3"])
        )

        result = status._primitive_to_dto(self.report_processor, primitive_xml)

        self.assertEqual(
            result,
            fixture_primitive_dto(node_names=["node1", "node2", "node3"]),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_empty_node_name(self):
        primitive_xml = etree.fromstring(fixture_primitive_xml(node_names=[""]))

        assert_raise_library_error(
            lambda: status._primitive_to_dto(
                self.report_processor, primitive_xml
            )
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.CLUSTER_STATUS_EMPTY_NODE_NAME,
                    resource_id="resource",
                )
            ],
        )

    def test_empty_resource_id(self):
        primitive_xml = etree.fromstring(fixture_primitive_xml(resource_id=""))

        assert_raise_library_error(
            lambda: status._primitive_to_dto(
                self.report_processor, primitive_xml
            )
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.INVALID_ID_IS_EMPTY,
                    id_description="resource id",
                )
            ],
        )

    def test_role(self):
        for role in PCMK_STATUS_ROLES:
            with self.subTest(value=role):
                primitive_xml = etree.fromstring(
                    fixture_primitive_xml(role=role)
                )

                result = status._primitive_to_dto(
                    self.report_processor, primitive_xml
                )
                self.assertEqual(result, fixture_primitive_dto(role=role))
                assert_report_item_list_equal(
                    self.report_processor.report_item_list, []
                )

    def test_invalid_role(self):
        primitive_xml = etree.fromstring(
            fixture_primitive_xml(role="NotPcmkRole")
        )

        result = status._primitive_to_dto(self.report_processor, primitive_xml)

        self.assertEqual(
            result, fixture_primitive_dto(role=PCMK_STATUS_ROLE_UNKNOWN)
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.warn(
                    reports.codes.CLUSTER_STATUS_UNKNOWN_PCMK_ROLE,
                    role="NotPcmkRole",
                    resource_id="resource",
                )
            ],
        )

    def test_target_role(self):
        for role in PCMK_ROLES:
            with self.subTest(value=role):
                primitive_xml = etree.fromstring(
                    fixture_primitive_xml(target_role=role)
                )

                result = status._primitive_to_dto(
                    self.report_processor, primitive_xml
                )

                self.assertEqual(
                    result, fixture_primitive_dto(target_role=role)
                )
                assert_report_item_list_equal(
                    self.report_processor.report_item_list, []
                )

    def test_invalid_target_role(self):
        for value in PCMK_STATUS_ROLES_PENDING + ("NotPcmkRole",):
            with self.subTest(value=value):
                self.setUp()
                primitive_xml = etree.fromstring(
                    fixture_primitive_xml(target_role=value)
                )

                result = status._primitive_to_dto(
                    self.report_processor, primitive_xml
                )

                self.assertEqual(
                    result, fixture_primitive_dto(target_role=PCMK_ROLE_UNKNOWN)
                )
                assert_report_item_list_equal(
                    self.report_processor.report_item_list,
                    [
                        fixture.warn(
                            reports.codes.CLUSTER_STATUS_UNKNOWN_PCMK_ROLE,
                            role=value,
                            resource_id="resource",
                        )
                    ],
                )


class TestGroupStatusToDto(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()

    def test_all_attributes(self):
        group_xml = etree.fromstring(
            fixture_group_xml(description="Test description")
        )

        result = status._group_to_dto(self.report_processor, group_xml)

        self.assertEqual(
            result, fixture_group_dto(description="Test description")
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_single_member(self):
        group_xml = etree.fromstring(
            fixture_group_xml(members=[fixture_primitive_xml()])
        )

        result = status._group_to_dto(self.report_processor, group_xml)

        self.assertEqual(
            result, fixture_group_dto(members=[fixture_primitive_dto()])
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_multiple_members(self):
        group_xml = etree.fromstring(
            fixture_group_xml(
                members=[
                    fixture_primitive_xml(resource_id="resource1"),
                    fixture_primitive_xml(resource_id="resource2"),
                ]
            )
        )

        result = status._group_to_dto(self.report_processor, group_xml)

        self.assertEqual(
            result,
            fixture_group_dto(
                members=[
                    fixture_primitive_dto(resource_id="resource1"),
                    fixture_primitive_dto(resource_id="resource2"),
                ]
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_multiple_members_different_state(self):
        group_xml = etree.fromstring(
            fixture_group_xml(
                members=[
                    fixture_primitive_xml(
                        resource_id="resource1",
                        role=PCMK_STATUS_ROLE_STOPPED,
                        managed=False,
                        node_names=[],
                    ),
                    fixture_primitive_xml(resource_id="resource2"),
                ]
            )
        )

        result = status._group_to_dto(self.report_processor, group_xml)

        self.assertEqual(
            result,
            fixture_group_dto(
                members=[
                    fixture_primitive_dto(
                        resource_id="resource1",
                        role=PCMK_STATUS_ROLE_STOPPED,
                        managed=False,
                        node_names=[],
                    ),
                    fixture_primitive_dto(resource_id="resource2"),
                ]
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_invalid_member(self):
        resources = {
            "inner-group": '<group id="inner-group" number_resources="0" maintenance="false" managed="true" disabled="false" />',
            "inner-clone": '<clone id="inner-clone" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false" />',
            "inner-bundle": '<bundle id="inner-bundle" type="podman" image="localhost/pcmktest:http" unique="false" maintenance="false" managed="true" failed="false" />',
        }

        for resource_id, member in resources.items():
            with self.subTest(value=resource_id):
                self.setUp()
                group_xml = etree.fromstring(
                    fixture_group_xml(
                        resource_id="outer-group", members=[member]
                    )
                )

                # pylint: disable=cell-var-from-loop
                assert_raise_library_error(
                    lambda: status._group_to_dto(
                        self.report_processor, group_xml
                    )
                )
                assert_report_item_list_equal(
                    self.report_processor.report_item_list,
                    [
                        fixture.error(
                            reports.codes.CLUSTER_STATUS_UNEXPECTED_MEMBER,
                            resource_id="outer-group",
                            resource_type="group",
                            member_id=resource_id,
                            expected_types=["primitive"],
                        )
                    ],
                )

    def test_remove_clone_suffix(self):
        group_xml = etree.fromstring(
            fixture_group_xml(
                resource_id="resource-group:0",
                members=[fixture_primitive_xml(resource_id="resource:0")],
            )
        )

        result = status._group_to_dto(self.report_processor, group_xml, True)
        self.assertEqual(
            result,
            fixture_group_dto(members=[fixture_primitive_dto()]),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )


class TestCloneStatusToDto(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()

    def test_all_attributes(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                description="Test description",
                target_role=PCMK_STATUS_ROLE_STARTED,
            )
        )

        result = status._clone_to_dto(self.report_processor, clone_xml)

        self.assertEqual(
            result,
            fixture_clone_dto(
                description="Test description", target_role=PCMK_ROLE_STARTED
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_primitive_member(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(instances=[fixture_primitive_xml()])
        )

        result = status._clone_to_dto(self.report_processor, clone_xml)

        self.assertEqual(
            result, fixture_clone_dto(instances=[fixture_primitive_dto()])
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_primitive_member_multiple(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                instances=[
                    fixture_primitive_xml(),
                    fixture_primitive_xml(node_names=["node2"]),
                ]
            )
        )

        result = status._clone_to_dto(self.report_processor, clone_xml)

        self.assertEqual(
            result,
            fixture_clone_dto(
                instances=[
                    fixture_primitive_dto(),
                    fixture_primitive_dto(node_names=["node2"]),
                ]
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_primitive_member_unique(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                unique=True,
                instances=[
                    fixture_primitive_xml(resource_id="resource:0"),
                    fixture_primitive_xml(
                        resource_id="resource:1", node_names=["node2"]
                    ),
                ],
            )
        )

        result = status._clone_to_dto(self.report_processor, clone_xml)

        self.assertEqual(
            result,
            fixture_clone_dto(
                unique=True,
                instances=[
                    fixture_primitive_dto(),
                    fixture_primitive_dto(node_names=["node2"]),
                ],
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_primitive_member_promotable(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                multi_state=True,
                instances=[
                    fixture_primitive_xml(role=PCMK_STATUS_ROLE_UNPROMOTED),
                    fixture_primitive_xml(
                        role=PCMK_STATUS_ROLE_UNPROMOTED, node_names=["node2"]
                    ),
                ],
            )
        )
        result = status._clone_to_dto(self.report_processor, clone_xml)

        self.assertEqual(
            result,
            fixture_clone_dto(
                multi_state=True,
                instances=[
                    fixture_primitive_dto(role=PCMK_STATUS_ROLE_UNPROMOTED),
                    fixture_primitive_dto(
                        role=PCMK_STATUS_ROLE_UNPROMOTED, node_names=["node2"]
                    ),
                ],
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_primitive_member_different_ids(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                instances=[
                    fixture_primitive_xml(),
                    fixture_primitive_xml(
                        resource_id="not_the_same_id", node_names=["node2"]
                    ),
                ]
            )
        )

        assert_raise_library_error(
            lambda: status._clone_to_dto(self.report_processor, clone_xml)
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.CLUSTER_STATUS_CLONE_MEMBERS_DIFFERENT_IDS,
                    clone_id="resource-clone",
                )
            ],
        )

    def test_group_member(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                instances=[
                    fixture_group_xml(
                        resource_id="resource-group:0",
                        members=[fixture_primitive_xml()],
                    ),
                    fixture_group_xml(
                        resource_id="resource-group:1",
                        members=[fixture_primitive_xml(node_names=["node2"])],
                    ),
                ],
            )
        )
        result = status._clone_to_dto(self.report_processor, clone_xml)

        self.assertEqual(
            result,
            fixture_clone_dto(
                instances=[
                    fixture_group_dto(members=[fixture_primitive_dto()]),
                    fixture_group_dto(
                        members=[fixture_primitive_dto(node_names=["node2"])]
                    ),
                ],
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_group_member_unique(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                unique=True,
                instances=[
                    fixture_group_xml(
                        resource_id="resource-group:0",
                        members=[
                            fixture_primitive_xml(resource_id="resource:0")
                        ],
                    ),
                    fixture_group_xml(
                        resource_id="resource-group:1",
                        members=[
                            fixture_primitive_xml(
                                resource_id="resource:1", node_names=["node2"]
                            )
                        ],
                    ),
                ],
            )
        )
        result = status._clone_to_dto(self.report_processor, clone_xml)

        self.assertEqual(
            result,
            fixture_clone_dto(
                unique=True,
                instances=[
                    fixture_group_dto(members=[fixture_primitive_dto()]),
                    fixture_group_dto(
                        members=[fixture_primitive_dto(node_names=["node2"])]
                    ),
                ],
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_group_member_different_group_ids(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                instances=[
                    fixture_group_xml(
                        resource_id="resource-group:0",
                        members=[fixture_primitive_xml()],
                    ),
                    fixture_group_xml(
                        resource_id="another-id-:1",
                        members=[fixture_primitive_xml(node_names=["node2"])],
                    ),
                ],
            )
        )

        assert_raise_library_error(
            lambda: status._clone_to_dto(self.report_processor, clone_xml)
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.CLUSTER_STATUS_CLONE_MEMBERS_DIFFERENT_IDS,
                    clone_id="resource-clone",
                )
            ],
        )

    def test_group_member_different_primitive_ids(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                instances=[
                    fixture_group_xml(
                        resource_id="resource-group:0",
                        members=[fixture_primitive_xml()],
                    ),
                    fixture_group_xml(
                        resource_id="resource-group:1",
                        members=[
                            fixture_primitive_xml(
                                resource_id="some-other-id",
                                node_names=["node2"],
                            )
                        ],
                    ),
                ],
            )
        )

        assert_raise_library_error(
            lambda: status._clone_to_dto(self.report_processor, clone_xml)
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.CLUSTER_STATUS_CLONE_MEMBERS_DIFFERENT_IDS,
                    clone_id="resource-clone",
                )
            ],
        )

    def test_primitive_member_types_mixed(self):
        clone_xml = etree.fromstring(
            fixture_clone_xml(
                instances=[
                    fixture_group_xml(
                        resource_id="resource",
                        members=[
                            fixture_primitive_xml(resource_id="inner-resource")
                        ],
                    ),
                    fixture_primitive_xml(node_names=["node2"]),
                ],
            )
        )

        assert_raise_library_error(
            lambda: status._clone_to_dto(self.report_processor, clone_xml)
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.CLUSTER_STATUS_CLONE_MIXED_MEMBERS,
                    clone_id="resource-clone",
                )
            ],
        )

    def test_invalid_member(self):
        resources = {
            "inner-clone": '<clone id="inner-clone" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false" />',
            "inner-bundle": '<bundle id="inner-bundle" type="podman" image="localhost/pcmktest:http" unique="false" maintenance="false" managed="true" failed="false" />',
        }
        for resource_id, element in resources.items():
            with self.subTest(value=resource_id):
                self.setUp()
                clone_xml = etree.fromstring(
                    fixture_clone_xml(instances=[element])
                )

                # pylint: disable=cell-var-from-loop
                assert_raise_library_error(
                    lambda: status._clone_to_dto(
                        self.report_processor, clone_xml
                    )
                )
                assert_report_item_list_equal(
                    self.report_processor.report_item_list,
                    [
                        fixture.error(
                            reports.codes.CLUSTER_STATUS_UNEXPECTED_MEMBER,
                            resource_id="resource-clone",
                            resource_type="clone",
                            member_id=resource_id,
                            expected_types=["primitive", "group"],
                        )
                    ],
                )


class TestBundleReplicaStatusToDto(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()

    def test_no_member_no_ip(self):
        replica_xml = etree.fromstring(fixture_replica_xml())

        bundle_id = "resource-bundle"
        bundle_type = "podman"
        result = status._replica_to_dto(
            self.report_processor, replica_xml, bundle_id, bundle_type
        )
        self.assertEqual(result, fixture_replica_dto())
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_no_member(self):
        replica_xml = etree.fromstring(fixture_replica_xml(ip=True))

        bundle_id = "resource-bundle"
        bundle_type = "podman"
        result = status._replica_to_dto(
            self.report_processor, replica_xml, bundle_id, bundle_type
        )
        self.assertEqual(result, fixture_replica_dto(ip=True))
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_member(self):
        replica_xml = etree.fromstring(
            fixture_replica_xml(
                ip=True,
                member=fixture_primitive_xml(
                    node_names=["resource-bundle-0"],
                ),
            )
        )

        bundle_id = "resource-bundle"
        bundle_type = "podman"
        result = status._replica_to_dto(
            self.report_processor, replica_xml, bundle_id, bundle_type
        )
        self.assertEqual(
            result,
            fixture_replica_dto(
                ip=True,
                member=fixture_primitive_dto(node_names=["resource-bundle-0"]),
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_member_no_ip(self):
        replica_xml = etree.fromstring(
            fixture_replica_xml(
                member=fixture_primitive_xml(
                    node_names=["resource-bundle-0"],
                ),
            )
        )

        bundle_id = "resource-bundle"
        bundle_type = "podman"
        result = status._replica_to_dto(
            self.report_processor, replica_xml, bundle_id, bundle_type
        )
        self.assertEqual(
            result,
            fixture_replica_dto(
                member=fixture_primitive_dto(node_names=["resource-bundle-0"])
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_no_container(self):
        replica_xml = etree.fromstring(
            """
            <replica id="0">
                <resource id="resource-bundle-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="node1" id="1" cached="true"/>
                </resource>
                <resource id="apa" resource_agent="ocf:heartbeat:apache" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="resource-bundle-0" id="resource-bundle-0" cached="true"/>
                </resource>
                <resource id="resource-bundle-0" resource_agent="ocf:pacemaker:remote" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="node1" id="1" cached="true"/>
                </resource>
          </replica>
          """
        )

        bundle_id = "resource-bundle"
        bundle_type = "podman"
        assert_raise_library_error(
            lambda: status._replica_to_dto(
                self.report_processor, replica_xml, bundle_id, bundle_type
            )
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.CLUSTER_STATUS_BUNDLE_REPLICA_NO_CONTAINER,
                    bundle_id=bundle_id,
                    replica_id="0",
                )
            ],
        )

    def test_empty_replica(self):
        replica_xml = etree.fromstring('<replica id="0" />')

        bundle_id = "resource-bundle"
        bundle_type = "podman"
        assert_raise_library_error(
            lambda: status._replica_to_dto(
                self.report_processor, replica_xml, bundle_id, bundle_type
            )
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.CLUSTER_STATUS_BUNDLE_REPLICA_NO_CONTAINER,
                    bundle_id=bundle_id,
                    replica_id="0",
                )
            ],
        )

    def test_member_no_remote(self):
        replica_xml = etree.fromstring(
            """
            <replica id="0">
                <resource id="apa" resource_agent="ocf:heartbeat:apache" role="Stopped" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="0"/>
                <resource id="resource-bundle-podman-0" resource_agent="ocf:heartbeat:podman" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="node1" id="1" cached="true"/>
                </resource>
            </replica>
            """
        )

        bundle_id = "resource-bundle"
        bundle_type = "podman"
        assert_raise_library_error(
            lambda: status._replica_to_dto(
                self.report_processor, replica_xml, bundle_id, bundle_type
            )
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.CLUSTER_STATUS_BUNDLE_REPLICA_MISSING_REMOTE,
                    bundle_id=bundle_id,
                    replica_id="0",
                )
            ],
        )

    def test_member_same_id_as_container(self):
        # xml taken from crm_mon output
        replica_xml = etree.fromstring(
            """
            <replica id="0">
                <resource id="resource-bundle-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="r92-1" id="1" cached="true"/>
                </resource>
                <resource id="resource-bundle-podman-0" resource_agent="ocf:heartbeat:apache" role="Stopped" active="false" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="0"/>
                <resource id="resource-bundle-podman-0" resource_agent="ocf:heartbeat:podman" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="4">
                    <node name="r92-1" id="1" cached="true"/>
                    <node name="resource-bundle-1" id="resource-bundle-1" cached="true"/>
                    <node name="resource-bundle-0" id="resource-bundle-0" cached="true"/>
                    <node name="resource-bundle-2" id="resource-bundle-2" cached="true"/>
                </resource>
                <resource id="resource-bundle-0" resource_agent="ocf:pacemaker:remote" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="r92-1" id="1" cached="true"/>
                </resource>
            </replica>
            """
        )
        bundle_id = "resource-bundle"
        bundle_type = "podman"
        result = status._replica_to_dto(
            self.report_processor, replica_xml, bundle_id, bundle_type
        )
        self.assertTrue(result is None)
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.warn(
                    reports.codes.CLUSTER_STATUS_BUNDLE_MEMBER_ID_AS_IMPLICIT,
                    bundle_id=bundle_id,
                    bad_ids=["resource-bundle-podman-0"],
                )
            ],
        )

    def test_member_same_id_as_remote(self):
        # xml taken from crm_mon output
        replica_xml = etree.fromstring(
            """
            <replica id="0">
                <resource id="resource-bundle-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="node1" id="1" cached="true"/>
                </resource>
                <resource id="resource-bundle-0" resource_agent="ocf:heartbeat:apache" role="Stopped" active="false" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="0"/>
                <resource id="resource-bundle-podman-0" resource_agent="ocf:heartbeat:podman" role="Stopping" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="true" failure_ignored="false" nodes_running_on="1">
                    <node name="node1" id="1" cached="true"/>
                </resource>
                <resource id="resource-bundle-0" resource_agent="ocf:pacemaker:remote" role="Started" active="false" orphaned="false" blocked="false" maintenance="false" managed="true" failed="true" failure_ignored="false" nodes_running_on="1">
                    <node name="resource-bundle-0" id="resource-bundle-0" cached="false"/>
                </resource>
            </replica>
            """
        )
        bundle_id = "resource-bundle"
        bundle_type = "podman"
        result = status._replica_to_dto(
            self.report_processor, replica_xml, bundle_id, bundle_type
        )
        self.assertTrue(result is None)
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.warn(
                    reports.codes.CLUSTER_STATUS_BUNDLE_MEMBER_ID_AS_IMPLICIT,
                    bundle_id=bundle_id,
                    bad_ids=["resource-bundle-0"],
                )
            ],
        )

    def test_member_same_id_as_ip(self):
        # xml taken from crm_mon output
        replica_xml = etree.fromstring(
            """
            <replica id="0">
                <resource id="resource-bundle-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="4">
                    <node name="node1" id="1" cached="true"/>
                    <node name="resource-bundle-0" id="resource-bundle-0" cached="true"/>
                    <node name="resource-bundle-1" id="resource-bundle-1" cached="true"/>
                    <node name="resource-bundle-2" id="resource-bundle-2" cached="true"/>
                </resource>
                <resource id="resource-bundle-ip-192.168.122.250" resource_agent="ocf:heartbeat:apache" role="Stopped" active="false" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="0"/>
                <resource id="resource-bundle-podman-0" resource_agent="ocf:heartbeat:podman" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="node1" id="1" cached="true"/>
                </resource>
                <resource id="resource-bundle-0" resource_agent="ocf:pacemaker:remote" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="node1" id="1" cached="true"/>
                </resource>
            </replica>
            """
        )
        bundle_id = "resource-bundle"
        bundle_type = "podman"

        result = status._replica_to_dto(
            self.report_processor, replica_xml, bundle_id, bundle_type
        )
        self.assertTrue(result is None)
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.warn(
                    reports.codes.CLUSTER_STATUS_BUNDLE_MEMBER_ID_AS_IMPLICIT,
                    bundle_id=bundle_id,
                    bad_ids=["resource-bundle-ip-192.168.122.250"],
                )
            ],
        )

    def test_too_many_members(self):
        replica_xml = etree.fromstring(
            """
            <replica id="0">
                <resource id="resource-bundle-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="r92-1" id="1" cached="true"/>
                </resource>
                <resource id="apa1" resource_agent="ocf:heartbeat:apache" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="resource-bundle-0" id="resource-bundle-0" cached="true"/>
                </resource>
                <resource id="resource-bundle-podman-0" resource_agent="ocf:heartbeat:podman" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="r92-1" id="1" cached="true"/>
                </resource>
                <resource id="resource-bundle-0" resource_agent="ocf:pacemaker:remote" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="r92-1" id="1" cached="true"/>
                </resource>
                <resource id="apa2" resource_agent="ocf:heartbeat:apache" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                    <node name="resource-bundle-0" id="resource-bundle-0" cached="true"/>
                </resource>
            </replica>
            """
        )

        bundle_id = "resource-bundle"
        bundle_type = "podman"
        assert_raise_library_error(
            lambda: status._replica_to_dto(
                self.report_processor, replica_xml, bundle_id, bundle_type
            )
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.CLUSTER_STATUS_BUNDLE_REPLICA_INVALID_COUNT,
                    bundle_id=bundle_id,
                    replica_id="0",
                )
            ],
        )


class TestBundleStatusToDto(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()

    def test_no_member(self):
        bundle_xml = etree.fromstring(
            fixture_bundle_xml(replicas=[fixture_replica_xml()])
        )

        result = status._bundle_to_dto(self.report_processor, bundle_xml, False)
        self.assertEqual(
            result, fixture_bundle_dto(replicas=[fixture_replica_dto()])
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_member(self):
        bundle_xml = etree.fromstring(
            fixture_bundle_xml(
                replicas=[
                    fixture_replica_xml(
                        ip=True,
                        member=fixture_primitive_xml(
                            node_names=["resource-bundle-0"]
                        ),
                    )
                ]
            )
        )
        result = status._bundle_to_dto(self.report_processor, bundle_xml, False)
        self.assertEqual(
            result,
            fixture_bundle_dto(
                replicas=[
                    fixture_replica_dto(
                        ip=True,
                        member=fixture_primitive_dto(
                            node_names=["resource-bundle-0"]
                        ),
                    )
                ]
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_multiple_replicas(self):
        bundle_xml = etree.fromstring(
            fixture_bundle_xml(
                replicas=[
                    fixture_replica_xml(
                        ip=True,
                        member=fixture_primitive_xml(
                            node_names=["resource-bundle-0"]
                        ),
                    ),
                    fixture_replica_xml(
                        ip=True,
                        replica_id="1",
                        node_name="node2",
                        member=fixture_primitive_xml(
                            node_names=["resource-bundle-1"]
                        ),
                    ),
                ]
            )
        )
        result = status._bundle_to_dto(self.report_processor, bundle_xml, False)
        self.assertEqual(
            result,
            fixture_bundle_dto(
                replicas=[
                    fixture_replica_dto(
                        ip=True,
                        member=fixture_primitive_dto(
                            node_names=["resource-bundle-0"]
                        ),
                    ),
                    fixture_replica_dto(
                        replica_id="1",
                        ip=True,
                        node_name="node2",
                        member=fixture_primitive_dto(
                            node_names=["resource-bundle-1"]
                        ),
                    ),
                ]
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_same_id_as_implicit(self):
        bundle_xml = etree.fromstring(
            """
            <bundle id="resource-bundle" type="podman" image="localhost/pcmktest:http" unique="false" maintenance="false" managed="true" failed="false">
                <replica id="0">
                    <resource id="resource-bundle-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                        <node name="node1" id="1" cached="true"/>
                    </resource>
                    <resource id="resource-bundle-0" resource_agent="ocf:heartbeat:apache" role="Stopped" active="false" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="0"/>
                    <resource id="resource-bundle-podman-0" resource_agent="ocf:heartbeat:podman" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                        <node name="node1" id="1" cached="true"/>
                    </resource>
                    <resource id="resource-bundle-0" resource_agent="ocf:pacemaker:remote" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="2">
                        <node name="node1" id="1" cached="true"/>
                        <node name="resource-bundle-0" id="resource-bundle-0" cached="true"/>
                    </resource>
                </replica>
            </bundle>
            """
        )
        result = status._bundle_to_dto(self.report_processor, bundle_xml, False)
        self.assertTrue(result is None)
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.warn(
                    reports.codes.CLUSTER_STATUS_BUNDLE_MEMBER_ID_AS_IMPLICIT,
                    bundle_id="resource-bundle",
                    bad_ids=["resource-bundle-0"],
                )
            ],
        )

    def test_same_id_as_implicit_multiple_replicas(self):
        bundle_xml = etree.fromstring(
            """
            <bundle id="resource-bundle" type="podman" image="localhost/pcmktest:http" unique="false" maintenance="false" managed="true" failed="false">
                <replica id="0">
                    <resource id="resource-bundle-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                        <node name="node1" id="1" cached="true"/>
                    </resource>
                    <resource id="resource-bundle-1" resource_agent="ocf:heartbeat:apache" role="Stopped" active="false" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="0"/>
                    <resource id="resource-bundle-podman-0" resource_agent="ocf:heartbeat:podman" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                        <node name="node1" id="1" cached="true"/>
                    </resource>
                    <resource id="resource-bundle-0" resource_agent="ocf:pacemaker:remote" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                        <node name="node1" id="1" cached="true"/>
                    </resource>
                </replica>
                <replica id="1">
                    <resource id="resource-bundle-ip-192.168.122.251" resource_agent="ocf:heartbeat:IPaddr2" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                        <node name="node2" id="2" cached="true"/>
                    </resource>
                    <resource id="resource-bundle-1" resource_agent="ocf:heartbeat:apache" role="Stopped" active="false" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="0"/>
                    <resource id="resource-bundle-podman-1" resource_agent="ocf:heartbeat:podman" role="Stopping" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="true" failure_ignored="false" nodes_running_on="1">
                        <node name="node2" id="2" cached="true"/>
                    </resource>
                    <resource id="resource-bundle-1" resource_agent="ocf:pacemaker:remote" role="Started" active="false" orphaned="false" blocked="false" maintenance="false" managed="true" failed="true" failure_ignored="false" nodes_running_on="1">
                        <node name="resource-bundle-1" id="resource-bundle-1" cached="false"/>
                    </resource>
                </replica>
            </bundle>
            """
        )
        result = status._bundle_to_dto(self.report_processor, bundle_xml, False)
        self.assertTrue(result is None)
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.warn(
                    reports.codes.CLUSTER_STATUS_BUNDLE_MEMBER_ID_AS_IMPLICIT,
                    bundle_id="resource-bundle",
                    bad_ids=["resource-bundle-1"],
                )
            ],
        )

    def test_replicas_different(self):
        replicas = {
            "no-ip": fixture_replica_xml(
                ip=False, member=fixture_primitive_xml()
            ),
            "different-member-id": fixture_replica_xml(
                ip=True, member=fixture_primitive_xml(resource_id="another-id")
            ),
            "no-member": fixture_replica_xml(ip=True, member=None),
            "different-member-agent": fixture_replica_xml(
                ip=True,
                member=fixture_primitive_xml(
                    resource_agent="ocf:heartbeat:apache"
                ),
            ),
        }
        for name, element in replicas.items():
            with self.subTest(value=name):
                self.setUp()

                bundle_xml = etree.fromstring(
                    fixture_bundle_xml(
                        replicas=[
                            element,
                            fixture_replica_xml(
                                ip=True,
                                replica_id="1",
                                member=fixture_primitive_xml(),
                            ),
                        ]
                    )
                )

                # pylint: disable=cell-var-from-loop
                assert_raise_library_error(
                    lambda: status._bundle_to_dto(
                        self.report_processor, bundle_xml
                    )
                )

                assert_report_item_list_equal(
                    self.report_processor.report_item_list,
                    [
                        fixture.error(
                            reports.codes.CLUSTER_STATUS_BUNDLE_DIFFERENT_REPLICAS,
                            bundle_id="resource-bundle",
                        )
                    ],
                )


class TestResourcesStatusToDto(TestCase):
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()

    def test_empty_resources(self):
        status_xml = etree.fromstring(fixture_crm_mon_xml([]))

        result = status.status_xml_to_dto(self.report_processor, status_xml)
        self.assertEqual(result, ResourcesStatusDto([]))
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_single_primitive(self):
        status_xml = etree.fromstring(
            fixture_crm_mon_xml([fixture_primitive_xml()])
        )

        result = status.status_xml_to_dto(self.report_processor, status_xml)
        self.assertEqual(result, ResourcesStatusDto([fixture_primitive_dto()]))
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_single_group(self):
        status_xml = etree.fromstring(
            fixture_crm_mon_xml(
                [fixture_group_xml(members=[fixture_primitive_xml()])]
            )
        )

        result = status.status_xml_to_dto(self.report_processor, status_xml)
        self.assertEqual(
            result,
            ResourcesStatusDto(
                [fixture_group_dto(members=[fixture_primitive_dto()])]
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_single_clone(self):
        status_xml = etree.fromstring(
            fixture_crm_mon_xml(
                [fixture_clone_xml(instances=[fixture_primitive_xml()])]
            )
        )

        result = status.status_xml_to_dto(self.report_processor, status_xml)
        self.assertEqual(
            result,
            ResourcesStatusDto(
                [fixture_clone_dto(instances=[fixture_primitive_dto()])]
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_single_bundle(self):
        status_xml = etree.fromstring(
            fixture_crm_mon_xml(
                [
                    fixture_bundle_xml(
                        replicas=[
                            fixture_replica_xml(
                                ip=True,
                                member=fixture_primitive_xml(
                                    node_names=["resource-bundle-0"]
                                ),
                            )
                        ]
                    )
                ]
            )
        )

        result = status.status_xml_to_dto(self.report_processor, status_xml)
        self.assertEqual(
            result,
            ResourcesStatusDto(
                [
                    fixture_bundle_dto(
                        replicas=[
                            fixture_replica_dto(
                                ip=True,
                                member=fixture_primitive_dto(
                                    node_names=["resource-bundle-0"]
                                ),
                            )
                        ]
                    )
                ]
            ),
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_all_resource_types(self):
        status_xml = etree.fromstring(
            fixture_crm_mon_xml(
                [
                    fixture_primitive_xml(),
                    fixture_group_xml(members=[fixture_primitive_xml()]),
                    fixture_clone_xml(instances=[fixture_primitive_xml()]),
                    fixture_bundle_xml(
                        replicas=[
                            fixture_replica_xml(
                                ip=True,
                                member=fixture_primitive_xml(
                                    node_names=["resource-bundle-0"]
                                ),
                            )
                        ]
                    ),
                ]
            )
        )
        result = status.status_xml_to_dto(self.report_processor, status_xml)

        self.assertEqual(result.resources[0], fixture_primitive_dto())
        self.assertEqual(
            result.resources[1],
            fixture_group_dto(members=[fixture_primitive_dto()]),
        )
        self.assertEqual(
            result.resources[2],
            fixture_clone_dto(instances=[fixture_primitive_dto()]),
        )
        self.assertEqual(
            result.resources[3],
            fixture_bundle_dto(
                replicas=[
                    fixture_replica_dto(
                        ip=True,
                        member=fixture_primitive_dto(
                            node_names=["resource-bundle-0"]
                        ),
                    )
                ]
            ),
        )

    def test_skip_bundle(self):
        status_xml = etree.fromstring(
            fixture_crm_mon_xml(
                [
                    fixture_primitive_xml(),
                    """
            <bundle id="resource-bundle" type="podman" image="localhost/pcmktest:http" unique="false" maintenance="false" managed="true" failed="false">
                <replica id="0">
                    <resource id="resource-bundle-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                        <node name="node1" id="1" cached="true"/>
                    </resource>
                    <resource id="resource-bundle-0" resource_agent="ocf:heartbeat:apache" role="Stopped" active="false" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="0"/>
                    <resource id="resource-bundle-podman-0" resource_agent="ocf:heartbeat:podman" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="1">
                        <node name="node1" id="1" cached="true"/>
                    </resource>
                    <resource id="resource-bundle-0" resource_agent="ocf:pacemaker:remote" role="Started" active="true" orphaned="false" blocked="false" maintenance="false" managed="true" failed="false" failure_ignored="false" nodes_running_on="2">
                        <node name="node1" id="1" cached="true"/>
                        <node name="resource-bundle-0" id="resource-bundle-0" cached="true"/>
                    </resource>
                </replica>
            </bundle>
                    """,
                ]
            )
        )

        result = status.status_xml_to_dto(self.report_processor, status_xml)

        self.assertEqual(result, ResourcesStatusDto([fixture_primitive_dto()]))
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.warn(
                    reports.codes.CLUSTER_STATUS_BUNDLE_MEMBER_ID_AS_IMPLICIT,
                    bundle_id="resource-bundle",
                    bad_ids=["resource-bundle-0"],
                )
            ],
        )

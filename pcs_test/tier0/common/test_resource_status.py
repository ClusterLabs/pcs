# pylint: disable=too-many-lines
from typing import (
    Optional,
    Sequence,
    Union,
)
from unittest import TestCase

from pcs.common.const import (
    PCMK_ROLE_STOPPED,
    PCMK_STATUS_ROLE_STARTED,
    PCMK_STATUS_ROLE_STOPPED,
    PCMK_STATUS_ROLES_PENDING,
    PcmkRoleType,
    PcmkStatusRoleType,
)
from pcs.common.resource_status import (
    InstancesQuantifierUnsupportedException,
    MembersQuantifierUnsupportedException,
    MoreChildrenQuantifierType,
    ResourceNonExistentException,
    ResourceNotInGroupException,
    ResourcesStatusFacade,
    ResourceState,
    ResourceType,
    ResourceUnexpectedTypeException,
    _filter_clone_orphans,
)
from pcs.common.status_dto import (
    BundleReplicaStatusDto,
    BundleStatusDto,
    CloneStatusDto,
    GroupStatusDto,
    PrimitiveStatusDto,
    ResourcesStatusDto,
)
from pcs.common.types import StringSequence


def fixture_primitive_dto(
    resource_id: str,
    instance_id: Optional[str],
    resource_agent: str = "ocf:pacemaker:Dummy",
    role: PcmkStatusRoleType = PCMK_STATUS_ROLE_STARTED,
    target_role: Optional[PcmkRoleType] = None,
    active: bool = True,
    orphaned: bool = False,
    blocked: bool = False,
    maintenance: bool = False,
    failed: bool = False,
    failure_ignored: bool = False,
    managed: bool = True,
    node_names: StringSequence = ("node1",),
    pending: Optional[str] = None,
    locked_to: Optional[str] = None,
) -> PrimitiveStatusDto:
    # pylint: disable=too-many-arguments
    return PrimitiveStatusDto(
        resource_id,
        instance_id,
        resource_agent,
        role,
        target_role,
        active,
        orphaned,
        blocked,
        maintenance,
        None,
        failed,
        managed,
        failure_ignored,
        list(node_names),
        pending,
        locked_to,
    )


def fixture_group_dto(
    resource_id: str,
    instance_id: Optional[str],
    maintenance: bool = False,
    managed: bool = True,
    disabled: bool = False,
    members: Sequence[PrimitiveStatusDto] = (),
) -> GroupStatusDto:
    return GroupStatusDto(
        resource_id,
        instance_id,
        maintenance,
        None,
        managed,
        disabled,
        list(members),
    )


def fixture_clone_dto(
    resource_id: str,
    multi_state: bool = False,
    unique: bool = False,
    maintenance: bool = False,
    managed: bool = True,
    disabled: bool = False,
    failed: bool = False,
    failure_ignored: bool = False,
    instances: Union[
        Sequence[PrimitiveStatusDto], Sequence[GroupStatusDto]
    ] = (),
) -> CloneStatusDto:
    # pylint: disable=too-many-arguments
    return CloneStatusDto(
        resource_id,
        multi_state,
        unique,
        maintenance,
        None,
        managed,
        disabled,
        failed,
        failure_ignored,
        None,
        instances,
    )


class TestFilterCloneOrphans(TestCase):
    # pylint: disable=protected-access
    def test_primitives(self):
        resource_list = [
            fixture_primitive_dto("primitive", None, node_names=["node1"]),
            fixture_primitive_dto("primitive", None, node_names=["node2"]),
            fixture_primitive_dto(
                "primitive", None, orphaned=True, node_names=["node3"]
            ),
        ]

        filtered_list = _filter_clone_orphans(resource_list)
        self.assertEqual(
            filtered_list,
            [
                fixture_primitive_dto("primitive", None, node_names=["node1"]),
                fixture_primitive_dto("primitive", None, node_names=["node2"]),
            ],
        )

    def test_groups(self):
        primitive_names = ["node1", "node2"]
        resource_list = [
            fixture_group_dto(
                "group",
                "0",
                members=[
                    fixture_primitive_dto(name, None)
                    for name in primitive_names
                ],
            ),
            fixture_group_dto(
                "group",
                "1",
                members=[
                    fixture_primitive_dto(
                        "primitive_1", None, orphaned=True, node_names=["node2"]
                    )
                    for name in primitive_names
                ],
            ),
        ]
        filtered_list = _filter_clone_orphans(resource_list)
        self.assertEqual(
            filtered_list,
            [
                fixture_group_dto(
                    "group",
                    "0",
                    members=[
                        fixture_primitive_dto(name, None)
                        for name in primitive_names
                    ],
                )
            ],
        )


class TestFacadeFromDto(TestCase):
    # pylint: disable=protected-access
    def test_primitive(self):
        primitive = fixture_primitive_dto("primitive", None)
        dto = ResourcesStatusDto([primitive])

        facade = ResourcesStatusFacade.from_resources_status_dto(dto)

        self.assertEqual(facade._resources, [primitive])
        self.assertEqual(facade._resource_map, {"primitive": [primitive]})
        self.assertEqual(facade._child_parent_map, {})
        self.assertEqual(facade._bundle_member_node_map, {})
        self.assertFalse(facade._bundle_defined)

    def test_group(self):
        primitive = fixture_primitive_dto("primitive", None)
        group = fixture_group_dto("group", None, members=[primitive])

        dto = ResourcesStatusDto([group])
        facade = ResourcesStatusFacade.from_resources_status_dto(dto)

        self.assertEqual(facade._resources, [group])
        self.assertEqual(
            facade._resource_map, {"group": [group], "primitive": [primitive]}
        )
        self.assertEqual(facade._child_parent_map, {"primitive": "group"})
        self.assertEqual(facade._bundle_member_node_map, {})
        self.assertFalse(facade._bundle_defined)

    def test_clone(self):
        primitive = fixture_primitive_dto("primitive", None)
        clone = fixture_clone_dto("clone", instances=[primitive])

        dto = ResourcesStatusDto([clone])
        facade = ResourcesStatusFacade.from_resources_status_dto(dto)

        self.assertEqual(facade._resources, [clone])
        self.assertEqual(
            facade._resource_map, {"clone": [clone], "primitive": [primitive]}
        )
        self.assertEqual(facade._child_parent_map, {"primitive": "clone"})
        self.assertEqual(facade._bundle_member_node_map, {})
        self.assertFalse(facade._bundle_defined)

    def test_cloned_group(self):
        primitive = fixture_primitive_dto("primitive", None)
        group = fixture_group_dto("group", None, members=[primitive])
        clone = fixture_clone_dto("clone", instances=[group])

        dto = ResourcesStatusDto([clone])
        facade = ResourcesStatusFacade.from_resources_status_dto(dto)

        self.assertEqual(facade._resources, [clone])
        self.assertEqual(
            facade._resource_map,
            {"clone": [clone], "group": [group], "primitive": [primitive]},
        )
        self.assertEqual(
            facade._child_parent_map, {"group": "clone", "primitive": "group"}
        )
        self.assertEqual(facade._bundle_member_node_map, {})
        self.assertFalse(facade._bundle_defined)

    def test_bundle(self):
        member = fixture_primitive_dto("member", None)
        container = fixture_primitive_dto("container", None)
        remote = fixture_primitive_dto("remote", None)
        bundle = BundleStatusDto(
            "bundle",
            "",
            "",
            False,
            False,
            None,
            True,
            False,
            [BundleReplicaStatusDto("0", member, remote, container, None)],
        )
        dto = ResourcesStatusDto([bundle])

        facade = ResourcesStatusFacade.from_resources_status_dto(dto)
        self.assertEqual(facade._resources, [bundle])
        self.assertEqual(
            facade._resource_map, {"bundle": [bundle], "member": [member]}
        )
        self.assertEqual(facade._child_parent_map, {"member": "bundle"})
        self.assertEqual(
            facade._bundle_member_node_map, {id(member): ["node1"]}
        )
        self.assertTrue(facade._bundle_defined)

    def test_combination(self):
        primitive = fixture_primitive_dto("primitive", None)
        primitive_member = fixture_primitive_dto("primitive_member", None)
        group = fixture_group_dto("group", None, members=[primitive_member])
        primitive_instance = fixture_primitive_dto("primitive_instance", None)
        clone = fixture_clone_dto("clone", instances=[primitive_instance])

        dto = ResourcesStatusDto([primitive, group, clone])
        facade = ResourcesStatusFacade.from_resources_status_dto(dto)

        self.assertEqual(facade._resources, [primitive, group, clone])
        self.assertEqual(
            facade._resource_map,
            {
                "primitive": [primitive],
                "group": [group],
                "primitive_member": [primitive_member],
                "clone": [clone],
                "primitive_instance": [primitive_instance],
            },
        )
        self.assertEqual(
            facade._child_parent_map,
            {"primitive_member": "group", "primitive_instance": "clone"},
        )
        self.assertEqual(facade._bundle_member_node_map, {})
        self.assertFalse(facade._bundle_defined)


def fixture_facade() -> ResourcesStatusFacade:
    stonith = fixture_primitive_dto("stonith", None, "stonith:fence_xvm")
    primitive = fixture_primitive_dto("primitive", None)
    primitive_stopped = fixture_primitive_dto(
        "primitive_stopped",
        None,
        role=PCMK_STATUS_ROLE_STOPPED,
        active=False,
        node_names=[],
    )

    group_empty = fixture_group_dto("group_empty", None)
    group = fixture_group_dto(
        "group",
        None,
        members=[
            fixture_primitive_dto("group-primitive_1", None),
            fixture_primitive_dto("group-primitive_2", None),
        ],
    )

    clone_empty = fixture_clone_dto("clone_empty")
    clone = fixture_clone_dto(
        "clone",
        instances=[
            fixture_primitive_dto("clone-primitive", None, node_names=[node])
            for node in ["node1", "node2"]
        ],
    )

    clone_unique = fixture_clone_dto(
        "clone_unique",
        unique=True,
        # multiple replicas running on the same node
        instances=[
            fixture_primitive_dto(
                "clone_unique-primitive", str(i), node_names=[f"node{i % 2}"]
            )
            for i in range(4)
        ],
    )
    clone_promotable = fixture_clone_dto("clone_promotable", multi_state=True)

    cloned_group = fixture_clone_dto(
        "cloned_group",
        instances=[
            fixture_group_dto(
                "cloned_group-group",
                "0",
                members=[
                    fixture_primitive_dto(
                        "cloned_group-group-primitive_1", None
                    ),
                    fixture_primitive_dto(
                        "cloned_group-group-primitive_2",
                        None,
                        role=PCMK_STATUS_ROLE_STOPPED,
                        active=False,
                        node_names=[],
                    ),
                ],
            )
        ],
    )

    bundle_empty = BundleStatusDto(
        "bundle_empty",
        "podman",
        "",
        False,
        False,
        None,
        True,
        False,
        [],
    )

    bundle = BundleStatusDto(
        "bundle",
        "podman",
        "",
        True,
        False,
        None,
        True,
        False,
        [
            BundleReplicaStatusDto(
                str(i),
                member=fixture_primitive_dto(
                    "bundle-member", None, node_names=[f"bundle-remote-{i}"]
                ),
                remote=fixture_primitive_dto(
                    f"bundle-remote-{i}", None, node_names=[f"node{i}"]
                ),
                container=fixture_primitive_dto(
                    f"bundle-container-{i}", None, node_names=[f"node{i}"]
                ),
                ip_address=None,
            )
            for i in range(2)
        ],
    )

    return ResourcesStatusFacade(
        [
            stonith,
            primitive,
            primitive_stopped,
            group_empty,
            group,
            clone_empty,
            clone,
            clone_unique,
            clone_promotable,
            cloned_group,
            bundle_empty,
            bundle,
        ]
    )


class TestFacadeGetResource(TestCase):
    def setUp(self):
        self.facade = fixture_facade()

    def test_one_instance_primitive(self):
        primitive = self.facade.get_resource_one_instance("primitive", None)
        self.assertEqual(primitive, fixture_primitive_dto("primitive", None))

    def test_one_instance_group(self):
        group = self.facade.get_resource_one_instance("group", None)
        self.assertEqual(
            group,
            fixture_group_dto(
                "group",
                None,
                members=[
                    fixture_primitive_dto("group-primitive_1", None),
                    fixture_primitive_dto("group-primitive_2", None),
                ],
            ),
        )

    def test_one_instance_clone(self):
        clone = self.facade.get_resource_one_instance("clone", None)
        self.assertEqual(
            clone,
            fixture_clone_dto(
                "clone",
                instances=[
                    fixture_primitive_dto(
                        "clone-primitive", None, node_names=[node]
                    )
                    for node in ["node1", "node2"]
                ],
            ),
        )

    def test_one_instance_clone_instance(self):
        clone_primitive = self.facade.get_resource_one_instance(
            "clone_unique-primitive", None
        )
        self.assertEqual(
            clone_primitive,
            fixture_primitive_dto(
                "clone_unique-primitive", "0", node_names=["node0"]
            ),
        )

    def test_one_instance_clone_instance_with_id(self):
        clone_primitive = self.facade.get_resource_one_instance(
            "clone_unique-primitive", "1"
        )
        self.assertEqual(
            clone_primitive,
            fixture_primitive_dto(
                "clone_unique-primitive", "1", node_names=["node1"]
            ),
        )

    def test_one_instance_bundle(self):
        bundle = self.facade.get_resource_one_instance("bundle", None)

        self.assertEqual(
            bundle,
            BundleStatusDto(
                "bundle",
                "podman",
                "",
                True,
                False,
                None,
                True,
                False,
                [
                    BundleReplicaStatusDto(
                        str(i),
                        member=fixture_primitive_dto(
                            "bundle-member",
                            None,
                            node_names=[f"bundle-remote-{i}"],
                        ),
                        remote=fixture_primitive_dto(
                            f"bundle-remote-{i}", None, node_names=[f"node{i}"]
                        ),
                        container=fixture_primitive_dto(
                            f"bundle-container-{i}",
                            None,
                            node_names=[f"node{i}"],
                        ),
                        ip_address=None,
                    )
                    for i in range(2)
                ],
            ),
        )

    def test_one_instance_bundle_member(self):
        member = self.facade.get_resource_one_instance("bundle-member", None)
        self.assertEqual(
            member,
            fixture_primitive_dto(
                "bundle-member", None, node_names=["bundle-remote-0"]
            ),
        )

    def test_one_instance_nonexistent(self):
        id_list = [
            ("nonexistent", None),
            ("primitive", "0"),
            ("clone-primitive", "42"),
            ("clone_unique-primitive", "42"),
            ("bundle-container", None),
        ]
        for resource_id, instance_id in id_list:
            with self.subTest(value=f"{resource_id}:{instance_id}"):
                resource = self.facade.get_resource_one_instance(
                    resource_id, instance_id
                )
                self.assertEqual(resource, None)

    def test_all_instances(self):
        clone = self.facade.get_resource_all_instances("clone_unique-primitive")
        self.assertEqual(
            clone,
            [
                fixture_primitive_dto(
                    "clone_unique-primitive",
                    str(i),
                    node_names=[f"node{i % 2}"],
                )
                for i in range(4)
            ],
        )

    def test_all_instances_nonexistent(self):
        for resource_id in ["nonexistent", "bundle-container"]:
            with self.subTest(value=resource_id):
                resource = self.facade.get_resource_all_instances(resource_id)
                self.assertEqual(resource, None)


class TestFacadeExists(TestCase):
    def setUp(self):
        self.facade = fixture_facade()

    def test_exists(self):
        resource_id_list = [
            ("stonith", None),
            ("primitive", None),
            ("group", None),
            ("group-primitive_1", None),
            ("group-primitive_2", None),
            ("clone", None),
            ("clone-primitive", None),
            ("clone_unique", None),
            ("clone_unique-primitive", None),
            ("clone_unique-primitive", "0"),
            ("clone_unique-primitive", "1"),
            ("cloned_group", None),
            ("cloned_group-group", None),
            ("cloned_group-group", "0"),
            ("cloned_group-group-primitive_1", None),
            ("cloned_group-group-primitive_2", None),
            ("bundle", None),
            ("bundle-member", None),
        ]
        for resource_id, instance_id in resource_id_list:
            with self.subTest(value=f"{resource_id}:{instance_id}"):
                self.assertTrue(self.facade.exists(resource_id, instance_id))

    def test_does_not_exist(self):
        id_list = [
            ("nonexistent", None),
            ("primitive", "0"),
            ("clone-primitive", "42"),
            ("clone_unique-primitive", "42"),
            ("bundle-container", None),
        ]
        for resource_id, instance_id in id_list:
            with self.subTest(value=f"{resource_id}:{instance_id}"):
                self.assertFalse(self.facade.exists(resource_id, instance_id))


class TestFacadeResourceTypes(TestCase):
    def setUp(self):
        self.facade = fixture_facade()

    def test_is_stonith(self):
        self.assertTrue(self.facade.is_stonith("stonith", None))
        self.assertFalse(self.facade.is_stonith("primitive", None))

    def test_is_stonith_nonexistent(self):
        with self.assertRaises(ResourceNonExistentException) as cm:
            self.facade.is_stonith("nonexistent", None)

        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)

    def test_get_type(self):
        resource_list = [
            ("primitive", None, ResourceType.PRIMITIVE),
            ("group", None, ResourceType.GROUP),
            ("clone", None, ResourceType.CLONE),
            ("cloned_group", None, ResourceType.CLONE),
            ("bundle", None, ResourceType.BUNDLE),
            ("group-primitive_1", None, ResourceType.PRIMITIVE),
            ("group-primitive_2", None, ResourceType.PRIMITIVE),
            ("clone_unique-primitive", None, ResourceType.PRIMITIVE),
            ("clone_unique-primitive", "0", ResourceType.PRIMITIVE),
            ("cloned_group-group", None, ResourceType.GROUP),
            ("cloned_group-group", "0", ResourceType.GROUP),
            ("cloned_group-group-primitive_1", None, ResourceType.PRIMITIVE),
            ("bundle-member", None, ResourceType.PRIMITIVE),
        ]
        for resource_id, instance_id, resource_type in resource_list:
            with self.subTest(value=f"{resource_id}:{instance_id}"):
                returned_type = self.facade.get_type(resource_id, instance_id)
                self.assertEqual(returned_type, resource_type)

    def test_get_type_nonexistent(self):
        with self.assertRaises(ResourceNonExistentException) as cm:
            self.facade.get_type("nonexistent", None)

        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)

    def test_is_promotable(self):
        self.assertTrue(self.facade.is_promotable("clone_promotable", None))
        self.assertFalse(self.facade.is_promotable("clone", None))

    def test_is_promotable_nonexistent(self):
        with self.assertRaises(ResourceNonExistentException) as cm:
            self.facade.is_promotable("nonexistent", None)

        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)

    def test_is_promotable_bad_type(self):
        resource_list = [
            ("primitive", ResourceType.PRIMITIVE),
            ("group", ResourceType.GROUP),
            ("bundle", ResourceType.BUNDLE),
        ]
        for resource_id, resource_type in resource_list:
            with self.subTest(value=resource_id):
                with self.assertRaises(ResourceUnexpectedTypeException) as cm:
                    self.facade.is_promotable(resource_id, None)

                self.assertEqual(cm.exception.resource_id, resource_id)
                self.assertEqual(cm.exception.instance_id, None)
                self.assertEqual(cm.exception.resource_type, resource_type)
                self.assertEqual(
                    cm.exception.expected_types, [ResourceType.CLONE]
                )

    def test_is_unique_clone(self):
        self.assertTrue(self.facade.is_unique("clone_unique", None))
        self.assertFalse(self.facade.is_unique("clone", None))

    def test_is_unique_bundle(self):
        self.assertTrue(self.facade.is_unique("bundle", None))
        self.assertFalse(self.facade.is_unique("bundle_empty", None))

    def test_is_unique_nonexistent(self):
        facade = fixture_facade()
        with self.assertRaises(ResourceNonExistentException) as cm:
            facade.is_unique("nonexistent", None)

        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)

    def test_is_unique_bad_type(self):
        resource_list = [
            ("primitive", ResourceType.PRIMITIVE),
            ("group", ResourceType.GROUP),
        ]
        for resource_id, resource_type in resource_list:
            with self.subTest(value=resource_id):
                with self.assertRaises(ResourceUnexpectedTypeException) as cm:
                    self.facade.is_unique(resource_id, None)

                self.assertEqual(cm.exception.resource_id, resource_id)
                self.assertEqual(cm.exception.instance_id, None)
                self.assertEqual(cm.exception.resource_type, resource_type)
                self.assertEqual(
                    cm.exception.expected_types,
                    [ResourceType.CLONE, ResourceType.BUNDLE],
                )


class TestFacadeParentResources(TestCase):
    def setUp(self):
        self.facade = fixture_facade()

    def test_get_parent_group_id(self):
        resource_list = [
            ("group-primitive_1", "group"),
            ("group-primitive_2", "group"),
            ("cloned_group-group-primitive_1", "cloned_group-group"),
        ]

        for resource_id, group_id in resource_list:
            with self.subTest(value=resource_id):
                result = self.facade.get_parent_group_id(resource_id, None)
                self.assertEqual(result, group_id)

    def test_get_parent_group_id_not_grouped(self):
        parent_id = self.facade.get_parent_group_id("primitive", None)
        self.assertEqual(parent_id, None)

    def test_get_parent_group_id_nonexistent(self):
        with self.assertRaises(ResourceNonExistentException) as cm:
            self.facade.get_parent_group_id("nonexistent", None)

        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)

    def test_get_parent_group_id_bad_type(self):
        resource_list = [
            ("group", ResourceType.GROUP),
            ("clone", ResourceType.CLONE),
            ("bundle", ResourceType.BUNDLE),
        ]

        for resource_id, resource_type in resource_list:
            with self.subTest(value=resource_id):
                with self.assertRaises(ResourceUnexpectedTypeException) as cm:
                    self.facade.get_parent_group_id(resource_id, None)

                self.assertEqual(cm.exception.resource_id, resource_id)
                self.assertEqual(cm.exception.instance_id, None)
                self.assertEqual(cm.exception.resource_type, resource_type)
                self.assertEqual(
                    cm.exception.expected_types, [ResourceType.PRIMITIVE]
                )

    def test_get_parent_clone_id(self):
        resource_list = [
            ("clone-primitive", None, "clone"),
            ("clone_unique-primitive", None, "clone_unique"),
            ("clone_unique-primitive", "0", "clone_unique"),
            ("clone_unique-primitive", "1", "clone_unique"),
            ("cloned_group-group", None, "cloned_group"),
            ("cloned_group-group", "0", "cloned_group"),
            ("cloned_group-group-primitive_1", None, "cloned_group"),
        ]
        for resource_id, instance_id, expected_clone_id in resource_list:
            with self.subTest(value=resource_id):
                clone_id = self.facade.get_parent_clone_id(
                    resource_id, instance_id
                )
                self.assertEqual(
                    clone_id,
                    expected_clone_id,
                )

    def test_get_parent_clone_id_not_cloned(self):
        for resource_id in ["primitive", "group"]:
            with self.subTest(value=resource_id):
                result = self.facade.get_parent_clone_id(resource_id, None)
                self.assertEqual(result, None)

    def test_get_parent_clone_nonexistent(self):
        id_list = [
            ("nonexistent", None),
            ("primitive", "0"),
            ("clone-primitive", "42"),
            ("clone_unique-primitive", "42"),
        ]
        for resource_id, instance_id in id_list:
            with self.subTest(value=f"{resource_id}:{instance_id}"):
                with self.assertRaises(ResourceNonExistentException) as cm:
                    self.facade.get_parent_clone_id(resource_id, instance_id)

                self.assertEqual(cm.exception.resource_id, resource_id)
                self.assertEqual(cm.exception.instance_id, instance_id)

    def test_get_parent_clone_id_bad_type(self):
        resource_list = [
            ("clone", ResourceType.CLONE),
            ("bundle", ResourceType.BUNDLE),
        ]

        for resource_id, resource_type in resource_list:
            with self.subTest(value=resource_id):
                with self.assertRaises(ResourceUnexpectedTypeException) as cm:
                    self.facade.get_parent_clone_id(resource_id, None)

                self.assertEqual(cm.exception.resource_id, resource_id)
                self.assertEqual(cm.exception.instance_id, None)
                self.assertEqual(cm.exception.resource_type, resource_type)
                self.assertEqual(
                    cm.exception.expected_types,
                    [ResourceType.PRIMITIVE, ResourceType.GROUP],
                )

    def test_get_parent_bundle_id(self):
        parent_id = self.facade.get_parent_bundle_id("bundle-member", None)
        self.assertEqual(parent_id, "bundle")

    def test_get_parent_bundle_not_bundled(self):
        parent_id = self.facade.get_parent_bundle_id("primitive", None)
        self.assertEqual(parent_id, None)

    def test_get_parent_bundle_nonexistent(self):
        with self.assertRaises(ResourceNonExistentException) as cm:
            self.facade.get_parent_bundle_id("nonexistent", None)

        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)

    def test_get_parent_bundle_id_bad_type(self):
        resource_list = [
            ("clone", ResourceType.CLONE),
            ("bundle", ResourceType.BUNDLE),
        ]

        for resource_id, resource_type in resource_list:
            with self.subTest(value=resource_id):
                with self.assertRaises(ResourceUnexpectedTypeException) as cm:
                    self.facade.get_parent_bundle_id(resource_id, None)

                self.assertEqual(cm.exception.resource_id, resource_id)
                self.assertEqual(cm.exception.instance_id, None)
                self.assertEqual(cm.exception.resource_type, resource_type)
                self.assertEqual(
                    cm.exception.expected_types, [ResourceType.PRIMITIVE]
                )


class TestGetIndexInGroup(TestCase):
    def setUp(self):
        self.facade = fixture_facade()

    def test_ok(self):
        index_1 = self.facade.get_index_in_group("group-primitive_1", None)
        self.assertEqual(index_1, 0)

        index_2 = self.facade.get_index_in_group("group-primitive_2", None)
        self.assertEqual(index_2, 1)

    def test_nonexistent(self):
        with self.assertRaises(ResourceNonExistentException) as cm:
            self.facade.get_index_in_group("nonexistent", None)
        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)

    def test_not_in_group(self):
        with self.assertRaises(ResourceNotInGroupException) as cm:
            self.facade.get_index_in_group("primitive", None)
        self.assertEqual(cm.exception.resource_id, "primitive")
        self.assertEqual(cm.exception.instance_id, None)


class TestFacadeGetMembers(TestCase):
    def setUp(self):
        self.facade = fixture_facade()

    def test_all(self):
        resource_list = [
            ("group", None, ["group-primitive_1", "group-primitive_2"]),
            ("clone", None, ["clone-primitive"]),
            ("cloned_group", None, ["cloned_group-group"]),
            (
                "cloned_group-group",
                None,
                [
                    "cloned_group-group-primitive_1",
                    "cloned_group-group-primitive_2",
                ],
            ),
            (
                "cloned_group-group",
                "0",
                [
                    "cloned_group-group-primitive_1",
                    "cloned_group-group-primitive_2",
                ],
            ),
            ("bundle", None, ["bundle-member"]),
        ]

        for resource_id, instance_id, members in resource_list:
            with self.subTest(value=resource_id):
                result = self.facade.get_members(resource_id, instance_id)
                self.assertEqual(result, members)

    def test_nonexistent(self):
        resource_list = [("nonexistent", None), ("cloned_group-group", "42")]

        for resource_id, instance_id in resource_list:
            with self.subTest(value=resource_id):
                with self.assertRaises(ResourceNonExistentException) as cm:
                    self.facade.get_members(resource_id, instance_id)
                self.assertEqual(cm.exception.resource_id, resource_id)
                self.assertEqual(cm.exception.instance_id, instance_id)

    def test_bad_type(self):
        with self.assertRaises(ResourceUnexpectedTypeException) as cm:
            self.facade.get_members("primitive", None)

        self.assertEqual(cm.exception.resource_id, "primitive")
        self.assertEqual(cm.exception.instance_id, None)
        self.assertEqual(cm.exception.resource_type, ResourceType.PRIMITIVE)
        self.assertEqual(
            cm.exception.expected_types,
            [ResourceType.GROUP, ResourceType.CLONE, ResourceType.BUNDLE],
        )


def fixture_bundle_facade() -> ResourcesStatusFacade:
    return ResourcesStatusFacade(
        [
            BundleStatusDto(
                "bundle",
                "podman",
                "",
                unique=True,
                maintenance=False,
                description=None,
                managed=True,
                failed=False,
                replicas=[
                    BundleReplicaStatusDto(
                        "0",
                        member=fixture_primitive_dto(
                            "bundle-member",
                            None,
                            node_names=["bundle-remote-0"],
                        ),
                        remote=fixture_primitive_dto(
                            "bundle-remote-0", None, node_names=["node1"]
                        ),
                        container=fixture_primitive_dto(
                            "bundle-container-0", None, node_names=["node1"]
                        ),
                        ip_address=None,
                    ),
                    BundleReplicaStatusDto(
                        "1",
                        member=fixture_primitive_dto(
                            "bundle-member",
                            None,
                            target_role=PCMK_STATUS_ROLE_STOPPED,
                            managed=False,
                            node_names=["bundle-remote-1"],
                        ),
                        remote=fixture_primitive_dto(
                            "bundle-remote-1", None, node_names=["node2"]
                        ),
                        container=fixture_primitive_dto(
                            "bundle-container-1", None, node_names=["node2"]
                        ),
                        ip_address=None,
                    ),
                ],
            )
        ]
    )


class TestFacadeGetNodes(TestCase):
    def setUp(self):
        self.facade = fixture_facade()

    def test_all(self):
        resource_list = [
            ("primitive", None, ["node1"]),
            ("primitive_stopped", None, []),
            ("group", None, ["node1"]),
            ("clone", None, ["node1", "node2"]),
            ("clone-primitive", None, ["node1", "node2"]),
            ("clone_unique", None, ["node0", "node0", "node1", "node1"]),
            (
                "clone_unique-primitive",
                None,
                ["node0", "node0", "node1", "node1"],
            ),
            ("clone_unique-primitive", "1", ["node1"]),
            ("clone_unique-primitive", "2", ["node0"]),
            ("cloned_group", None, ["node1"]),
            ("cloned_group-group", None, ["node1"]),
            ("cloned_group-group-primitive_1", None, ["node1"]),
            ("bundle", None, ["node0", "node1"]),
            ("bundle-member", None, ["node0", "node1"]),
        ]

        for resource_id, instance_id, node_list in resource_list:
            with self.subTest(value=f"{resource_id}:{instance_id}"):
                result = self.facade.get_nodes(resource_id, instance_id)
                self.assertEqual(result, node_list)

    def test_multiple_instances_on_same_node(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    unique=True,
                    instances=[
                        fixture_primitive_dto(
                            "primitive", str(i), node_names=[f"node{i % 2}"]
                        )
                        for i in range(4)
                    ],
                )
            ]
        )

        nodes = facade.get_nodes("clone", None)

        self.assertEqual(nodes, ["node0", "node0", "node1", "node1"])

    def test_nonexistent(self):
        with self.assertRaises(ResourceNonExistentException) as cm:
            self.facade.get_nodes("nonexistent", None)
        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)


class TestFacadeIsState(TestCase):
    # pylint: disable=too-many-public-methods
    def test_nonexistent(self):
        facade = ResourcesStatusFacade([])

        with self.assertRaises(ResourceNonExistentException) as cm:
            facade.is_state("nonexistent", None, ResourceState.STARTED)
        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)

    def test_primitive_all_states(self):
        facade = ResourcesStatusFacade(
            [fixture_primitive_dto("primitive", None)]
        )

        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.STARTED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.STOPPED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.PROMOTED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.UNPROMOTED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.STARTING)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.STOPPING)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.DISABLED)
        )
        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.ENABLED)
        )
        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.MANAGED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.UNMANAGED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.MAINTENANCE)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.FAILED)
        )
        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.ACTIVE)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.ORPHANED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.BLOCKED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.FAILURE_IGNORED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.PENDING)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.LOCKED_TO)
        )

    def test_primitive_disabled(self):
        facade = ResourcesStatusFacade(
            [
                fixture_primitive_dto(
                    "primitive", None, target_role=PCMK_ROLE_STOPPED
                )
            ]
        )

        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.DISABLED)
        )
        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.ENABLED)
        )

    def test_primitive_pending_role_attribute(self):
        for role in PCMK_STATUS_ROLES_PENDING:
            with self.subTest(value=role):
                facade = ResourcesStatusFacade(
                    [fixture_primitive_dto("primitive", None, role=role)]
                )

                self.assertTrue(
                    facade.is_state("primitive", None, ResourceState.PENDING)
                )

    def test_primitive_pending_pending_attribute(self):
        facade = ResourcesStatusFacade(
            [fixture_primitive_dto("primitive", None, pending="Monitoring")]
        )

        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.PENDING)
        )

    def test_primitive_locked_to(self):
        facade = ResourcesStatusFacade(
            [fixture_primitive_dto("primitive", None, locked_to="node2")]
        )

        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.LOCKED_TO)
        )

    def test_primitive_on_node(self):
        facade = ResourcesStatusFacade(
            [fixture_primitive_dto("primitive", None)]
        )

        self.assertTrue(
            facade.is_state(
                "primitive",
                None,
                ResourceState.STARTED,
                expected_node_name="node1",
            )
        )
        self.assertFalse(
            facade.is_state(
                "primitive",
                None,
                ResourceState.STARTED,
                expected_node_name="node42",
            )
        )

    def test_primitive_on_node_stopped(self):
        facade = ResourcesStatusFacade(
            [
                fixture_primitive_dto(
                    "primitive",
                    None,
                    role=PCMK_STATUS_ROLE_STOPPED,
                    active=False,
                    node_names=[],
                )
            ]
        )

        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.STOPPED)
        )
        self.assertFalse(
            facade.is_state(
                "primitive",
                None,
                ResourceState.STOPPED,
                expected_node_name="node1",
            )
        )

    def test_group_all(self):
        facade = ResourcesStatusFacade(
            [
                fixture_group_dto(
                    "group",
                    None,
                    members=[
                        fixture_primitive_dto("primitive_1", None),
                        fixture_primitive_dto("primitive_2", None),
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("group", None, ResourceState.STARTED))
        self.assertFalse(facade.is_state("group", None, ResourceState.STOPPED))
        self.assertFalse(facade.is_state("group", None, ResourceState.PROMOTED))
        self.assertFalse(
            facade.is_state("group", None, ResourceState.UNPROMOTED)
        )
        self.assertFalse(facade.is_state("group", None, ResourceState.STARTING))
        self.assertFalse(facade.is_state("group", None, ResourceState.STOPPING))
        self.assertFalse(facade.is_state("group", None, ResourceState.DISABLED))
        self.assertTrue(facade.is_state("group", None, ResourceState.ENABLED))
        self.assertTrue(facade.is_state("group", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state("group", None, ResourceState.UNMANAGED)
        )
        self.assertFalse(
            facade.is_state("group", None, ResourceState.MAINTENANCE)
        )
        self.assertFalse(facade.is_state("group", None, ResourceState.FAILED))
        self.assertTrue(facade.is_state("group", None, ResourceState.ACTIVE))
        self.assertFalse(facade.is_state("group", None, ResourceState.ORPHANED))
        self.assertFalse(facade.is_state("group", None, ResourceState.BLOCKED))
        self.assertFalse(
            facade.is_state("group", None, ResourceState.FAILURE_IGNORED)
        )
        self.assertFalse(facade.is_state("group", None, ResourceState.PENDING))
        self.assertFalse(
            facade.is_state("group", None, ResourceState.LOCKED_TO)
        )

    def test_group_empty(self):
        facade = ResourcesStatusFacade([fixture_group_dto("group", None)])

        self.assertTrue(facade.is_state("group", None, ResourceState.MANAGED))
        self.assertFalse(facade.is_state("group", None, ResourceState.STARTED))

    def test_group_members_different_state(self):
        facade = ResourcesStatusFacade(
            [
                fixture_group_dto(
                    "group",
                    None,
                    members=[
                        fixture_primitive_dto("primitive-1", None),
                        fixture_primitive_dto(
                            "primitive-2",
                            None,
                            role=PCMK_STATUS_ROLE_STOPPED,
                            target_role=PCMK_ROLE_STOPPED,
                            failed=True,
                            active=False,
                            managed=False,
                            node_names=[],
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("group", None, ResourceState.MANAGED))
        self.assertFalse(facade.is_state("group", None, ResourceState.DISABLED))

        self.assertFalse(facade.is_state("group", None, ResourceState.STARTED))
        self.assertFalse(facade.is_state("group", None, ResourceState.STOPPED))
        self.assertFalse(facade.is_state("group", None, ResourceState.FAILED))
        self.assertFalse(facade.is_state("group", None, ResourceState.ACTIVE))

    def test_group_members_quantifier(self):
        facade = ResourcesStatusFacade(
            [
                fixture_group_dto(
                    "group",
                    None,
                    members=[
                        fixture_primitive_dto("primitive-1", None),
                        fixture_primitive_dto(
                            "primitive-2",
                            None,
                            role=PCMK_STATUS_ROLE_STOPPED,
                            active=False,
                            managed=False,
                            node_names=[],
                        ),
                    ],
                )
            ]
        )

        self.assertFalse(facade.is_state("group", None, ResourceState.STARTED))
        self.assertFalse(
            facade.is_state(
                "group",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "group",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "group",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

        self.assertTrue(facade.is_state("group", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state(
                "group",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "group",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "group",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

    def test_group_on_node(self):
        facade = ResourcesStatusFacade(
            [
                fixture_group_dto(
                    "group",
                    None,
                    members=[
                        fixture_primitive_dto("primitive-1", None),
                        fixture_primitive_dto(
                            "primitive-2",
                            None,
                            managed=False,
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("group", None, ResourceState.STARTED))
        self.assertTrue(
            facade.is_state(
                "group", None, ResourceState.STARTED, expected_node_name="node1"
            )
        )
        self.assertFalse(
            facade.is_state(
                "group", None, ResourceState.STARTED, expected_node_name="node2"
            )
        )

        self.assertTrue(facade.is_state("group", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state(
                "group", None, ResourceState.MANAGED, expected_node_name="node1"
            )
        )

    def test_group_on_node_members_quantifier(self):
        facade = ResourcesStatusFacade(
            [
                fixture_group_dto(
                    "group",
                    None,
                    members=[
                        fixture_primitive_dto("primitive-1", None),
                        fixture_primitive_dto(
                            "primitive-2",
                            None,
                            managed=False,
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("group", None, ResourceState.STARTED))
        self.assertTrue(
            facade.is_state(
                "group",
                None,
                ResourceState.STARTED,
                expected_node_name="node1",
                members_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "group",
                None,
                ResourceState.STARTED,
                expected_node_name="node1",
                members_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )

        self.assertTrue(
            facade.is_state(
                "group",
                None,
                ResourceState.STARTED,
                expected_node_name="node2",
                members_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

    def test_clone_bundle_in_status(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto("clone"),
                BundleStatusDto(
                    "bundle", "podman", "", True, False, None, True, False, []
                ),
            ]
        )
        with self.assertRaises(NotImplementedError):
            facade.is_state("clone", None, ResourceState.STARTED)

    def test_clone_all(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    instances=[
                        fixture_primitive_dto(
                            "primitive", None, node_names=[node]
                        )
                        for node in ["node1", "node2"]
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("clone", None, ResourceState.STARTED))
        self.assertFalse(facade.is_state("clone", None, ResourceState.STOPPED))
        self.assertFalse(facade.is_state("clone", None, ResourceState.PROMOTED))
        self.assertFalse(
            facade.is_state("clone", None, ResourceState.UNPROMOTED)
        )
        self.assertFalse(facade.is_state("clone", None, ResourceState.STARTING))
        self.assertFalse(facade.is_state("clone", None, ResourceState.STOPPING))
        self.assertFalse(facade.is_state("clone", None, ResourceState.DISABLED))
        self.assertTrue(facade.is_state("clone", None, ResourceState.ENABLED))
        self.assertTrue(facade.is_state("clone", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state("clone", None, ResourceState.UNMANAGED)
        )
        self.assertFalse(
            facade.is_state("clone", None, ResourceState.MAINTENANCE)
        )
        self.assertFalse(facade.is_state("clone", None, ResourceState.FAILED))
        self.assertTrue(facade.is_state("clone", None, ResourceState.ACTIVE))
        self.assertFalse(facade.is_state("clone", None, ResourceState.ORPHANED))
        self.assertFalse(facade.is_state("clone", None, ResourceState.BLOCKED))
        self.assertFalse(
            facade.is_state("clone", None, ResourceState.FAILURE_IGNORED)
        )
        self.assertFalse(facade.is_state("clone", None, ResourceState.PENDING))
        self.assertFalse(
            facade.is_state("clone", None, ResourceState.LOCKED_TO)
        )

    def test_empty_clone(self):
        facade = ResourcesStatusFacade([fixture_clone_dto("clone")])

        self.assertTrue(facade.is_state("clone", None, ResourceState.MANAGED))
        self.assertFalse(facade.is_state("clone", None, ResourceState.STARTED))

    def test_clone_orphans(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    instances=[
                        fixture_primitive_dto("primitive", None),
                        fixture_primitive_dto(
                            "primitive",
                            None,
                            orphaned=True,
                            role=PCMK_STATUS_ROLE_STOPPED,
                            active=False,
                            node_names=[],
                        ),
                    ],
                ),
            ]
        )

        self.assertFalse(facade.is_state("clone", None, ResourceState.STOPPED))

    def test_clone_orphans_empty(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    instances=[
                        fixture_primitive_dto("primitive", None, orphaned=True)
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("clone", None, ResourceState.MANAGED))
        self.assertFalse(facade.is_state("clone", None, ResourceState.STARTED))

    def test_clone_members_different_state(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    instances=[
                        fixture_primitive_dto(
                            "primitive", None, node_names=["node1"]
                        ),
                        fixture_primitive_dto(
                            "primitive",
                            None,
                            role=PCMK_STATUS_ROLE_STOPPED,
                            target_role=PCMK_ROLE_STOPPED,
                            failed=True,
                            active=False,
                            managed=False,
                            node_names=[],
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("clone", None, ResourceState.STARTED))
        self.assertTrue(facade.is_state("clone", None, ResourceState.STOPPED))
        self.assertTrue(facade.is_state("clone", None, ResourceState.MANAGED))
        self.assertFalse(facade.is_state("clone", None, ResourceState.DISABLED))
        self.assertFalse(facade.is_state("clone", None, ResourceState.FAILED))
        self.assertTrue(facade.is_state("clone", None, ResourceState.ACTIVE))

    def test_clone_instances_quantifier(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    unique=True,
                    instances=[
                        fixture_primitive_dto(
                            "primitive", "0", node_names=["node1"]
                        ),
                        fixture_primitive_dto(
                            "primitive",
                            "1",
                            role=PCMK_STATUS_ROLE_STOPPED,
                            managed=False,
                            node_names=[],
                            active=False,
                        ),
                    ],
                )
            ]
        )

        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

        self.assertTrue(facade.is_state("clone", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

    def test_clone_on_node(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    unique=True,
                    instances=[
                        fixture_primitive_dto(
                            "primitive", "0", node_names=["node1"]
                        ),
                        fixture_primitive_dto(
                            "primitive",
                            "1",
                            managed=False,
                            node_names=["node2"],
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                expected_node_name="node1",
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                expected_node_name="node2",
            )
        )

        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                expected_node_name="node1",
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                expected_node_name="node2",
            )
        )

    def test_clone_on_node_instances_quantifier(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    unique=True,
                    instances=[
                        fixture_primitive_dto(
                            "primitive", "0", node_names=["node1"]
                        ),
                        fixture_primitive_dto(
                            "primitive",
                            "1",
                            managed=False,
                            node_names=["node2"],
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.UNMANAGED,
                expected_node_name="node2",
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.UNMANAGED,
                expected_node_name="node2",
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )

    def test_clone_group_member(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    instances=[
                        fixture_group_dto(
                            "group",
                            "0",
                            members=[
                                fixture_primitive_dto(
                                    "primitive", None, node_names=["node1"]
                                )
                            ],
                        ),
                        fixture_group_dto(
                            "group",
                            "1",
                            members=[
                                fixture_primitive_dto(
                                    "primitive",
                                    None,
                                    role=PCMK_STATUS_ROLE_STOPPED,
                                    active=False,
                                    managed=False,
                                    node_names=[],
                                )
                            ],
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("clone", None, ResourceState.STARTED))
        self.assertTrue(facade.is_state("clone", None, ResourceState.STOPPED))
        self.assertTrue(facade.is_state("clone", None, ResourceState.MANAGED))

    def test_clone_group_member_instances_quantifier(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    instances=[
                        fixture_group_dto(
                            "group",
                            "0",
                            members=[
                                fixture_primitive_dto(
                                    "primitive", None, node_names=["node1"]
                                )
                            ],
                        ),
                        fixture_group_dto(
                            "group",
                            "1",
                            managed=False,
                            members=[
                                fixture_primitive_dto(
                                    "primitive",
                                    None,
                                    role=PCMK_STATUS_ROLE_STOPPED,
                                    active=False,
                                    managed=False,
                                    node_names=[],
                                )
                            ],
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("clone", None, ResourceState.STARTED))
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

        self.assertTrue(facade.is_state("clone", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

    def test_clone_group_member_quantifiers(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    instances=[
                        fixture_group_dto(
                            "group",
                            "0",
                            members=[
                                fixture_primitive_dto(
                                    "primitive", None, node_names=[node]
                                )
                                for node in ["node1", "node2"]
                            ],
                        ),
                        fixture_group_dto(
                            "group",
                            "1",
                            managed=False,
                            members=[
                                fixture_primitive_dto(
                                    "primitive",
                                    None,
                                    role=PCMK_STATUS_ROLE_STOPPED,
                                    active=False,
                                    managed=False,
                                    node_names=[],
                                ),
                                fixture_primitive_dto(
                                    "primitive2", None, node_names=["node2"]
                                ),
                            ],
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("clone", None, ResourceState.STARTED))
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.ALL,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.ALL,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.ALL,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.ANY,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.ANY,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.ANY,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.NONE,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.NONE,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.NONE,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

        self.assertTrue(facade.is_state("clone", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.ALL,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.ALL,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.ALL,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.ANY,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.ANY,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.ANY,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.NONE,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertFalse(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.NONE,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertTrue(
            facade.is_state(
                "clone",
                None,
                ResourceState.MANAGED,
                members_quantifier=MoreChildrenQuantifierType.NONE,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

    def test_clone_instance(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    unique=True,
                    instances=[
                        fixture_primitive_dto(
                            "primitive", "0", node_names=["node1"]
                        ),
                        fixture_primitive_dto(
                            "primitive",
                            "1",
                            role=PCMK_STATUS_ROLE_STOPPED,
                            managed=False,
                            node_names=[],
                            active=False,
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(
            facade.is_state("primitive", "0", ResourceState.STARTED)
        )
        self.assertFalse(
            facade.is_state("primitive", "1", ResourceState.STARTED)
        )
        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.STARTED)
        )

        self.assertFalse(
            facade.is_state("primitive", "0", ResourceState.STOPPED)
        )
        self.assertTrue(
            facade.is_state("primitive", "1", ResourceState.STOPPED)
        )
        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.STOPPED)
        )

        self.assertTrue(
            facade.is_state("primitive", "0", ResourceState.MANAGED)
        )
        self.assertFalse(
            facade.is_state("primitive", "1", ResourceState.MANAGED)
        )
        self.assertTrue(
            facade.is_state("primitive", None, ResourceState.MANAGED)
        )

    def test_clone_instance_orphans(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    instances=[
                        fixture_primitive_dto("primitive", None),
                        fixture_primitive_dto(
                            "primitive",
                            None,
                            orphaned=True,
                            role=PCMK_STATUS_ROLE_STOPPED,
                            active=False,
                            node_names=[],
                        ),
                    ],
                ),
            ]
        )

        self.assertFalse(
            facade.is_state("primitive", None, ResourceState.STOPPED)
        )

    def test_clone_instance_orphans_empty(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    instances=[
                        fixture_primitive_dto("primitive", None, orphaned=True)
                    ],
                ),
            ]
        )

        with self.assertRaises(ResourceNonExistentException) as cm:
            facade.is_state("primitive", None, ResourceState.STARTED)
        self.assertEqual(cm.exception.resource_id, "primitive")
        self.assertEqual(cm.exception.instance_id, None)

    def test_clone_instance_instances_quantifier(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    unique=True,
                    instances=[
                        fixture_primitive_dto(
                            "primitive", "0", node_names=["node1"]
                        ),
                        fixture_primitive_dto(
                            "primitive",
                            "1",
                            role=PCMK_STATUS_ROLE_STOPPED,
                            node_names=[],
                            active=False,
                        ),
                    ],
                )
            ]
        )

        self.assertFalse(
            facade.is_state(
                "primitive",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "primitive",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "primitive",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

        self.assertTrue(
            facade.is_state(
                "primitive",
                None,
                ResourceState.PROMOTED,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

    def test_clone_instance_on_node(self):
        facade = ResourcesStatusFacade(
            [
                fixture_clone_dto(
                    "clone",
                    unique=True,
                    instances=[
                        fixture_primitive_dto(
                            "primitive", "0", node_names=["node1"]
                        ),
                        fixture_primitive_dto(
                            "primitive",
                            "1",
                            managed=False,
                            node_names=["node2"],
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(
            facade.is_state(
                "primitive",
                None,
                ResourceState.MANAGED,
                expected_node_name="node1",
            )
        )
        self.assertFalse(
            facade.is_state(
                "primitive",
                None,
                ResourceState.MANAGED,
                expected_node_name="node2",
            )
        )

    def test_bundle_all(self):
        facade = fixture_bundle_facade()

        self.assertTrue(facade.is_state("bundle", None, ResourceState.STARTED))
        self.assertFalse(facade.is_state("bundle", None, ResourceState.STOPPED))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.PROMOTED)
        )
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.UNPROMOTED)
        )
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.STARTING)
        )
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.STOPPING)
        )
        self.assertTrue(facade.is_state("bundle", None, ResourceState.DISABLED))
        self.assertTrue(facade.is_state("bundle", None, ResourceState.ENABLED))
        self.assertTrue(facade.is_state("bundle", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.UNMANAGED)
        )
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.MAINTENANCE)
        )
        self.assertFalse(facade.is_state("bundle", None, ResourceState.FAILED))
        self.assertTrue(facade.is_state("bundle", None, ResourceState.ACTIVE))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.ORPHANED)
        )
        self.assertFalse(facade.is_state("bundle", None, ResourceState.BLOCKED))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.FAILURE_IGNORED)
        )
        self.assertFalse(facade.is_state("bundle", None, ResourceState.PENDING))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.LOCKED_TO)
        )

    def test_bundle_no_member_all(self):
        facade = ResourcesStatusFacade(
            [
                BundleStatusDto(
                    "bundle",
                    "podman",
                    "",
                    True,
                    False,
                    None,
                    True,
                    False,
                    [
                        BundleReplicaStatusDto(
                            "0",
                            member=None,
                            remote=None,
                            container=fixture_primitive_dto(
                                "bundle-container-0", None, node_names=["node1"]
                            ),
                            ip_address=None,
                        ),
                        BundleReplicaStatusDto(
                            "1",
                            member=None,
                            remote=None,
                            container=fixture_primitive_dto(
                                "bundle-container-0",
                                None,
                                target_role=PCMK_STATUS_ROLE_STOPPED,
                                node_names=["node2"],
                            ),
                            ip_address=None,
                        ),
                    ],
                )
            ]
        )

        self.assertTrue(facade.is_state("bundle", None, ResourceState.STARTED))
        self.assertFalse(facade.is_state("bundle", None, ResourceState.STOPPED))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.PROMOTED)
        )
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.UNPROMOTED)
        )
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.STARTING)
        )
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.STOPPING)
        )
        self.assertTrue(facade.is_state("bundle", None, ResourceState.DISABLED))
        self.assertTrue(facade.is_state("bundle", None, ResourceState.ENABLED))
        self.assertTrue(facade.is_state("bundle", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.UNMANAGED)
        )
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.MAINTENANCE)
        )
        self.assertFalse(facade.is_state("bundle", None, ResourceState.FAILED))
        self.assertTrue(facade.is_state("bundle", None, ResourceState.ACTIVE))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.ORPHANED)
        )
        self.assertFalse(facade.is_state("bundle", None, ResourceState.BLOCKED))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.FAILURE_IGNORED)
        )
        self.assertFalse(facade.is_state("bundle", None, ResourceState.PENDING))
        self.assertFalse(
            facade.is_state("bundle", None, ResourceState.LOCKED_TO)
        )

    def test_bundle_instances_quantifier(self):
        facade = fixture_bundle_facade()

        self.assertTrue(facade.is_state("bundle", None, ResourceState.STARTED))
        self.assertTrue(
            facade.is_state(
                "bundle",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "bundle",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "bundle",
                None,
                ResourceState.STARTED,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

        self.assertTrue(facade.is_state("bundle", None, ResourceState.MANAGED))
        self.assertFalse(
            facade.is_state(
                "bundle",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "bundle",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "bundle",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

    def test_bundle_on_node(self):
        facade = fixture_bundle_facade()

        self.assertTrue(
            facade.is_state(
                "bundle",
                None,
                ResourceState.STARTED,
                expected_node_name="node1",
            )
        )
        self.assertTrue(
            facade.is_state(
                "bundle",
                None,
                ResourceState.STARTED,
                expected_node_name="node2",
            )
        )
        self.assertFalse(
            facade.is_state(
                "bundle",
                None,
                ResourceState.STARTED,
                expected_node_name="bundle-remote-0",
            )
        )

    def test_bundle_member_all(self):
        facade = fixture_bundle_facade()

        self.assertTrue(
            facade.is_state("bundle-member", None, ResourceState.STARTED)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.STOPPED)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.PROMOTED)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.UNPROMOTED)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.STARTING)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.STOPPING)
        )
        self.assertTrue(
            facade.is_state("bundle-member", None, ResourceState.DISABLED)
        )
        self.assertTrue(
            facade.is_state("bundle-member", None, ResourceState.ENABLED)
        )
        self.assertTrue(
            facade.is_state("bundle-member", None, ResourceState.MANAGED)
        )
        self.assertTrue(
            facade.is_state("bundle-member", None, ResourceState.UNMANAGED)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.MAINTENANCE)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.FAILED)
        )
        self.assertTrue(
            facade.is_state("bundle-member", None, ResourceState.ACTIVE)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.ORPHANED)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.BLOCKED)
        )
        self.assertFalse(
            facade.is_state(
                "bundle-member", None, ResourceState.FAILURE_IGNORED
            )
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.PENDING)
        )
        self.assertFalse(
            facade.is_state("bundle-member", None, ResourceState.LOCKED_TO)
        )

    def test_bundle_member_quantifier(self):
        facade = fixture_bundle_facade()

        self.assertTrue(
            facade.is_state("bundle-member", None, ResourceState.MANAGED)
        )
        self.assertFalse(
            facade.is_state(
                "bundle-member",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.ALL,
            )
        )
        self.assertTrue(
            facade.is_state(
                "bundle-member",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.ANY,
            )
        )
        self.assertFalse(
            facade.is_state(
                "bundle-member",
                None,
                ResourceState.MANAGED,
                instances_quantifier=MoreChildrenQuantifierType.NONE,
            )
        )

    def test_bundle_member_on_node(self):
        facade = fixture_bundle_facade()
        self.assertTrue(
            facade.is_state("bundle-member", None, ResourceState.MANAGED)
        )
        self.assertTrue(
            facade.is_state(
                "bundle-member",
                None,
                ResourceState.MANAGED,
                expected_node_name="node1",
            )
        )
        self.assertFalse(
            facade.is_state(
                "bundle-member",
                None,
                ResourceState.MANAGED,
                expected_node_name="node2",
            )
        )

        self.assertFalse(
            facade.is_state(
                "bundle-member",
                None,
                ResourceState.MANAGED,
                expected_node_name="bundle-remote-0",
            )
        )

    def test_bad_members_quantifier(self):
        facade = ResourcesStatusFacade(
            [
                fixture_primitive_dto("primitive", None),
                fixture_clone_dto(
                    "clone",
                    instances=[fixture_primitive_dto("cloned_primitive", None)],
                ),
            ]
        )

        resource_list = ["primitive", "clone", "cloned_primitive"]
        for resource_id in resource_list:
            with self.subTest(value=resource_id):
                with self.assertRaises(MembersQuantifierUnsupportedException):
                    facade.is_state(
                        resource_id,
                        None,
                        ResourceState.STARTED,
                        members_quantifier=MoreChildrenQuantifierType.ALL,
                    )

    def test_bad_members_quantifier_bundle(self):
        facade = fixture_bundle_facade()
        with self.assertRaises(MembersQuantifierUnsupportedException):
            facade.is_state(
                "bundle",
                None,
                ResourceState.STARTED,
                members_quantifier=MoreChildrenQuantifierType.ALL,
            )

    def test_bad_instances_quantifier(self):
        facade = fixture_facade()

        resource_list = ["primitive", "group"]
        for resource_id in resource_list:
            with self.subTest(value=resource_id):
                with self.assertRaises(InstancesQuantifierUnsupportedException):
                    facade.is_state(
                        resource_id,
                        None,
                        ResourceState.STARTED,
                        instances_quantifier=MoreChildrenQuantifierType.ALL,
                    )


class TestStateExactValue(TestCase):
    def test_locked_to(self):
        facade = ResourcesStatusFacade(
            [fixture_primitive_dto("primitive", None, locked_to="node1")]
        )

        result = facade.is_state_exact_value(
            "primitive", None, ResourceState.LOCKED_TO, "node1"
        )
        self.assertTrue(result)

        bad_result = facade.is_state_exact_value(
            "primitive", None, ResourceState.LOCKED_TO, "node42"
        )
        self.assertFalse(bad_result)

    def test_nonexistent(self):
        facade = ResourcesStatusFacade([])

        with self.assertRaises(ResourceNonExistentException) as cm:
            facade.is_state_exact_value(
                "nonexistent", None, ResourceState.PENDING, "42"
            )
        self.assertEqual(cm.exception.resource_id, "nonexistent")
        self.assertEqual(cm.exception.instance_id, None)

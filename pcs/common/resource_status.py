from collections import defaultdict
from typing import (
    Optional,
    Sequence,
    Union,
)

from pcs.common.status_dto import (
    AnyResourceStatusDto,
    BundleReplicaStatusDto,
    BundleStatusDto,
    CloneStatusDto,
    GroupStatusDto,
    PrimitiveStatusDto,
    ResourcesStatusDto,
)
from pcs.common.types import (
    MoreChildrenCheckType,
    ResourceState,
    ResourceStatusQueryResult,
    ResourceType,
)

_TYPE_MAP = {
    PrimitiveStatusDto: ResourceType.PRIMITIVE,
    GroupStatusDto: ResourceType.GROUP,
    CloneStatusDto: ResourceType.CLONE,
    BundleStatusDto: ResourceType.BUNDLE,
}

_ROLE_STATES = {
    ResourceState.STARTED,
    ResourceState.STOPPED,
    ResourceState.PROMOTED,
    ResourceState.UNPROMOTED,
    ResourceState.STARTING,
    ResourceState.STOPPING,
}

_MORE_CHILDREN_CHECK_TYPE_MAP = {
    MoreChildrenCheckType.ALL: all,
    MoreChildrenCheckType.ANY: any,
    MoreChildrenCheckType.NONE: lambda iterable: not any(iterable),
}

StateValueType = Union[str, bool]


class ResourcesStatusFacade:
    def __init__(self, resources: Sequence[AnyResourceStatusDto]):
        self.resources = resources
        self._resource_map: dict[str, list[AnyResourceStatusDto]] = defaultdict(
            list
        )
        self._child_parent_map: dict[str, str] = {}
        self._bundle_member_node_map: dict[int, list[str]] = {}
        self._bundle_defined = False

        for resource in resources:
            self._resource_map[resource.resource_id].append(resource)
            if isinstance(resource, GroupStatusDto):
                self.__add_group_children_to_maps(resource)
            elif isinstance(resource, CloneStatusDto):
                for instance in resource.instances:
                    self._child_parent_map[
                        instance.resource_id
                    ] = resource.resource_id
                    self._resource_map[instance.resource_id].append(instance)
                    if isinstance(instance, GroupStatusDto):
                        self.__add_group_children_to_maps(instance)
            elif isinstance(resource, BundleStatusDto):
                self._bundle_defined = True
                for replica in resource.replicas:
                    member = replica.member
                    if member is not None:
                        self._child_parent_map[
                            member.resource_id
                        ] = resource.resource_id
                        self._resource_map[member.resource_id].append(member)
                        self._bundle_member_node_map[
                            id(member)
                        ] = replica.container.node_names

    @classmethod
    def from_resources_status_dto(
        cls, resources_status_dto: ResourcesStatusDto
    ) -> "ResourcesStatusFacade":
        return cls(resources_status_dto.resources)

    def get_single_resource(
        self, resource_id: str, instance_id: Optional[str]
    ) -> Optional[AnyResourceStatusDto]:
        resource_list = self._resource_map.get(resource_id)
        if resource_list is None:
            return None

        if instance_id is None:
            return resource_list[0]

        for resource in resource_list:
            if (
                hasattr(resource, "instance_id")
                and resource.instance_id == instance_id
            ):
                return resource
        return None

    def get_multiple_resource_instances(
        self, resource_id: str
    ) -> Optional[list[AnyResourceStatusDto]]:
        return self._resource_map.get(resource_id)

    def exists(
        self, resource_id: str, instance_id: Optional[str]
    ) -> ResourceStatusQueryResult:
        return ResourceStatusQueryResult(
            self.get_single_resource(resource_id, instance_id) is not None,
            [],
        )

    def is_type(
        self,
        resource_id: str,
        instance_id: Optional[str],
        expected_type: Optional[ResourceType] = None,
        unique: bool = False,
        promotable: bool = False,
    ) -> ResourceStatusQueryResult:
        resource = self.get_single_resource(resource_id, instance_id)
        if resource is None:
            return ResourceStatusQueryResult(False, [])

        real_type = _TYPE_MAP[type(resource)]
        result = expected_type is None or real_type == expected_type
        if unique:
            result = (
                result and self.is_unique(resource_id, instance_id).query_result
            )
        if promotable:
            result = (
                result
                and self.is_promotable(resource_id, instance_id).query_result
            )

        return ResourceStatusQueryResult(
            result,
            [real_type.value],
        )

    def is_stonith(
        self, resource_id: str, instance_id: Optional[str]
    ) -> ResourceStatusQueryResult:
        resource = self.get_single_resource(resource_id, instance_id)
        is_stonith = (
            resource is not None
            and hasattr(resource, "resource_agent")
            and resource.resource_agent.startswith("stonith")
        )
        return ResourceStatusQueryResult(is_stonith, [])

    def is_promotable(
        self, resource_id: str, instance_id: Optional[str]
    ) -> ResourceStatusQueryResult:
        resource = self.get_single_resource(resource_id, instance_id)

        if resource is None or not hasattr(resource, "multi_state"):
            return ResourceStatusQueryResult(False, [])

        return ResourceStatusQueryResult(resource.multi_state, [])

    def is_unique(
        self, resource_id: str, instance_id: Optional[str]
    ) -> ResourceStatusQueryResult:
        resource = self.get_single_resource(resource_id, instance_id)

        if resource is None or not hasattr(resource, "unique"):
            return ResourceStatusQueryResult(False, [])

        return ResourceStatusQueryResult(resource.unique, [])

    def is_state(
        self,
        resource_id: str,
        instance_id: Optional[str],
        state: ResourceState,
        expected_value: Optional[StateValueType] = None,
        check_node: bool = False,
        expected_node_name: Optional[str] = None,
        members_check: Optional[MoreChildrenCheckType] = None,
        instances_check: Optional[MoreChildrenCheckType] = None,
    ) -> ResourceStatusQueryResult:
        # pylint: disable=too-many-arguments
        is_cloned = self.is_cloned(resource_id, instance_id).query_result
        is_clone = self.is_type(
            resource_id, instance_id, ResourceType.CLONE
        ).query_result

        if self._bundle_defined and (is_cloned or is_clone):
            raise NotImplementedError(
                "Queries on clone state when bundle resources are present "
                "in the cluster are unsupported"
            )

        if instance_id is not None:
            resource = self.get_single_resource(resource_id, instance_id)
            resource_list = [resource] if resource is not None else None
        else:
            resource_list = self.get_multiple_resource_instances(resource_id)

        if resource_list is None:
            return ResourceStatusQueryResult(False, [])

        if is_cloned:
            resource_list = [
                resource
                for resource in resource_list
                if isinstance(resource, PrimitiveStatusDto)
                or isinstance(resource, GroupStatusDto)
                and not _is_orphaned(resource)
            ]

        implicit_expected_value: Union[str, bool] = True
        if state in _ROLE_STATES:
            checked_attribute = "role"
            implicit_expected_value = state.value
        else:
            checked_attribute = state.value

        return self._check_resources_state_attributes(
            resource_list,
            checked_attribute,
            expected_value or implicit_expected_value,
            check_node,
            expected_node_name,
            members_check,
            instances_check,
        )

    def is_grouped(
        self,
        resource_id: str,
        instance_id: Optional[str],
        expected_group_id: Optional[str] = None,
        check_index: bool = False,
        expected_index: Optional[int] = None,
    ) -> ResourceStatusQueryResult:
        if self.get_single_resource(resource_id, instance_id) is None:
            return ResourceStatusQueryResult(False, [])
        if not self._check_parent_type(resource_id, ResourceType.GROUP):
            return ResourceStatusQueryResult(False, [])

        real_group_id = self._child_parent_map[resource_id]

        result = _is_real_id_expected(real_group_id, expected_group_id)

        if result and check_index:
            parent = self.get_single_resource(real_group_id, instance_id)
            assert isinstance(parent, GroupStatusDto)
            real_index = int(
                [res.resource_id for res in parent.members].index(resource_id)
            )

            return ResourceStatusQueryResult(
                result
                and (expected_index is None or expected_index == real_index),
                [real_group_id, str(real_index)],
            )

        return ResourceStatusQueryResult(result, [real_group_id])

    def is_cloned(
        self,
        resource_id: str,
        instance_id: Optional[str],
        expected_clone_id: Optional[str] = None,
    ) -> ResourceStatusQueryResult:
        if self.get_single_resource(resource_id, instance_id) is None:
            return ResourceStatusQueryResult(False, [])

        checked_id = resource_id
        if self._check_parent_type(checked_id, ResourceType.GROUP):
            checked_id = self._child_parent_map[resource_id]

        if not self._check_parent_type(checked_id, ResourceType.CLONE):
            return ResourceStatusQueryResult(False, [])

        real_clone_id = self._child_parent_map[checked_id]
        return ResourceStatusQueryResult(
            _is_real_id_expected(real_clone_id, expected_clone_id),
            [real_clone_id],
        )

    def is_bundled(
        self,
        resource_id: str,
        instance_id: Optional[str],
        expected_bundle_id: Optional[str] = None,
    ) -> ResourceStatusQueryResult:
        if self.get_single_resource(resource_id, instance_id) is None:
            return ResourceStatusQueryResult(False, [])

        if not self._check_parent_type(resource_id, ResourceType.BUNDLE):
            return ResourceStatusQueryResult(False, [])

        real_bundle_id = self._child_parent_map[resource_id]
        return ResourceStatusQueryResult(
            _is_real_id_expected(real_bundle_id, expected_bundle_id),
            [real_bundle_id],
        )

    def list_group(
        self, group_id: str, instance_id: Optional[str]
    ) -> ResourceStatusQueryResult:
        group = self.get_single_resource(group_id, instance_id)
        if not isinstance(group, GroupStatusDto):
            return ResourceStatusQueryResult(False, [])

        return ResourceStatusQueryResult(
            True, [[member.resource_id for member in group.members]]
        )

    def list_clone(
        self,
        clone_id: str,
        instance_id: Optional[str],
        resource: bool = False,
        instances: bool = False,
        nodes: bool = False,
    ) -> ResourceStatusQueryResult:
        clone = self.get_single_resource(clone_id, instance_id)
        if not isinstance(clone, CloneStatusDto):
            return ResourceStatusQueryResult(False, [])

        checked_instances = [
            instance
            for instance in clone.instances
            if not _is_orphaned(instance)
        ]

        if not checked_instances:
            return ResourceStatusQueryResult(True, [])

        text_output: list[Union[str, list[str]]] = []
        if resource:
            text_output.append(checked_instances[0].resource_id)
        if instances:
            text_output.append(str(len(checked_instances)))
        if nodes:
            all_nodes: set[str] = set()
            for res in checked_instances:
                if isinstance(res, GroupStatusDto):
                    for child in res.members:
                        all_nodes.update(child.node_names)
                else:
                    all_nodes.update(res.node_names)

            text_output.append(sorted(all_nodes))

        return ResourceStatusQueryResult(True, text_output)

    def list_bundle(
        self,
        bundle_id: str,
        instance_id: Optional[str],
        resource: bool = False,
        replicas: bool = False,
        nodes: bool = False,
    ) -> ResourceStatusQueryResult:
        bundle = self.get_single_resource(bundle_id, instance_id)
        if not isinstance(bundle, BundleStatusDto):
            return ResourceStatusQueryResult(False, [])

        if not bundle.replicas:
            return ResourceStatusQueryResult(True, [])

        text_output: list[Union[str, list[str]]] = []
        if resource:
            member = bundle.replicas[0].member
            if member is not None:
                text_output.append(member.resource_id)
            else:
                text_output.append("")
        if replicas:
            text_output.append(str(len(bundle.replicas)))
        if nodes:
            all_nodes: set[str] = set()
            for replica in bundle.replicas:
                all_nodes.update(replica.container.node_names)
            text_output.append(sorted(all_nodes))

        return ResourceStatusQueryResult(True, text_output)

    def _check_parent_type(
        self,
        resource_id: str,
        expected_parent_type: ResourceType,
    ) -> bool:
        parent_id = self._child_parent_map.get(resource_id)
        return (
            parent_id is not None
            and self.is_type(parent_id, None, expected_parent_type).query_result
        )

    def __add_group_children_to_maps(self, group: GroupStatusDto) -> None:
        for child in group.members:
            self._resource_map[child.resource_id].append(child)
            self._child_parent_map[child.resource_id] = group.resource_id

    def _check_resources_state_attributes(
        self,
        resources: list[AnyResourceStatusDto],
        checked_state: str,
        expected_value: StateValueType,
        check_nodes: bool = False,
        expected_node_name: Optional[str] = None,
        members_check: Optional[MoreChildrenCheckType] = None,
        instances_check: Optional[MoreChildrenCheckType] = None,
    ) -> ResourceStatusQueryResult:
        # TODO check of pending/locked_to - check only that they are not None
        results = []
        nodes_running_on: set[str] = set()

        for resource in resources:
            if isinstance(resource, PrimitiveStatusDto):
                results.append(
                    self._primitive_state(
                        resource,
                        checked_state,
                        expected_value,
                        expected_node_name,
                        nodes_running_on,
                    )
                )

            elif isinstance(resource, GroupStatusDto):
                results.append(
                    self._group_state(
                        resource,
                        checked_state,
                        expected_value,
                        members_check,
                        expected_node_name,
                        check_nodes,
                        nodes_running_on,
                    )
                )
            elif isinstance(resource, CloneStatusDto):
                results.append(
                    self._clone_state(
                        resource,
                        checked_state,
                        expected_value,
                        members_check,
                        instances_check,
                        expected_node_name,
                        check_nodes,
                        nodes_running_on,
                    )
                )
            elif isinstance(resource, BundleStatusDto):
                results.append(
                    self._bundle_state(
                        resource,
                        checked_state,
                        expected_value,
                        instances_check,
                        expected_node_name,
                        check_nodes,
                        nodes_running_on,
                    )
                )

        more_children_check = MoreChildrenCheckType.ANY
        if instances_check is not None:
            more_children_check = instances_check

        query_result = _MORE_CHILDREN_CHECK_TYPE_MAP[more_children_check](
            results
        )

        return ResourceStatusQueryResult(
            query_result,
            [sorted(nodes_running_on)]
            if check_nodes and nodes_running_on
            else [],
        )

    def _primitive_state(
        self,
        primitive: PrimitiveStatusDto,
        checked_attribute: str,
        expected_value: StateValueType,
        expected_node_name: Optional[str],
        nodes_running_on: set[str],
    ) -> bool:
        if not hasattr(primitive, checked_attribute):
            return False

        result = getattr(primitive, checked_attribute) == expected_value

        node_names = primitive.node_names
        if id(primitive) in self._bundle_member_node_map:
            node_names = self._bundle_member_node_map[id(primitive)]

        if not result:
            return False

        nodes_running_on.update(node_names)
        return expected_node_name is None or expected_node_name in node_names

    def _group_state(
        self,
        group: GroupStatusDto,
        checked_attribute: str,
        expected_value: StateValueType,
        members_check: Optional[MoreChildrenCheckType],
        expected_node_name: Optional[str],
        check_nodes: bool,
        nodes_running_on: set[str],
    ) -> bool:
        if _can_check_non_primitive(
            group, checked_attribute, members_check, check_nodes
        ):
            return getattr(group, checked_attribute) == expected_value

        results = [
            self._primitive_state(
                primitive,
                checked_attribute,
                expected_value,
                expected_node_name,
                nodes_running_on,
            )
            for primitive in group.members
        ]

        if members_check is None:
            members_check = MoreChildrenCheckType.ALL
        return _MORE_CHILDREN_CHECK_TYPE_MAP[members_check](results)

    def _clone_state(
        self,
        clone: CloneStatusDto,
        checked_attribute: str,
        expected_value: StateValueType,
        members_check: Optional[MoreChildrenCheckType],
        instances_check: Optional[MoreChildrenCheckType],
        expected_node_name: Optional[str],
        check_nodes: bool,
        nodes_running_on: set[str],
    ) -> bool:
        # pylint: disable=too-many-arguments
        if _can_check_non_primitive(
            clone, checked_attribute, instances_check, check_nodes
        ):
            return getattr(clone, checked_attribute) == expected_value

        results = [
            self._primitive_state(
                instance,
                checked_attribute,
                expected_value,
                expected_node_name,
                nodes_running_on,
            )
            if isinstance(instance, PrimitiveStatusDto)
            else self._group_state(
                instance,
                checked_attribute,
                expected_value,
                members_check,
                expected_node_name,
                check_nodes,
                nodes_running_on,
            )
            for instance in clone.instances
            if not _is_orphaned(instance)
        ]

        if instances_check is None:
            instances_check = MoreChildrenCheckType.ANY
        return _MORE_CHILDREN_CHECK_TYPE_MAP[instances_check](results)

    def _bundle_state(
        self,
        bundle: BundleStatusDto,
        checked_attribute: str,
        expected_value: StateValueType,
        instances_check: Optional[MoreChildrenCheckType],
        expected_node_name: Optional[str],
        check_nodes: bool,
        nodes_running_on: set[str],
    ) -> bool:
        if _can_check_non_primitive(
            bundle, checked_attribute, instances_check, check_nodes
        ):
            return getattr(bundle, checked_attribute) == expected_value

        results = [
            self._bundle_replica_state(
                replica,
                checked_attribute,
                expected_value,
                expected_node_name,
                nodes_running_on,
            )
            for replica in bundle.replicas
        ]

        if instances_check is None:
            instances_check = MoreChildrenCheckType.ANY
        return _MORE_CHILDREN_CHECK_TYPE_MAP[instances_check](results)

    def _bundle_replica_state(
        self,
        replica: BundleReplicaStatusDto,
        checked_attribute: str,
        expected_value: StateValueType,
        expected_node_name: Optional[str],
        nodes_running_on: set[str],
    ) -> bool:
        if replica.member is None:
            return self._primitive_state(
                replica.container,
                checked_attribute,
                expected_value,
                expected_node_name,
                nodes_running_on,
            )

        return self._primitive_state(
            replica.member,
            checked_attribute,
            expected_value,
            expected_node_name,
            nodes_running_on,
        )


def _can_check_non_primitive(
    resource: AnyResourceStatusDto,
    attribute_name: str,
    more_children_check: Optional[MoreChildrenCheckType],
    check_nodes: bool,
) -> bool:
    return (
        hasattr(resource, attribute_name)
        and more_children_check is None
        # we have to look at primitives if we want to see on which nodes
        # the resource is in given state
        and not check_nodes
    )


def _is_orphaned(resource: Union[PrimitiveStatusDto, GroupStatusDto]) -> bool:
    if isinstance(resource, PrimitiveStatusDto):
        return resource.orphaned
    return all(child.orphaned for child in resource.members)


def _is_real_id_expected(real_id: str, expected_id: Optional[str]) -> bool:
    return expected_id is None or real_id == expected_id

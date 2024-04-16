from collections import defaultdict
from dataclasses import dataclass
from enum import (
    Enum,
    auto,
)
from typing import (
    Final,
    Iterable,
    Literal,
    Optional,
    Sequence,
    Union,
    cast,
)

from pcs.common.const import (
    PCMK_ROLE_STOPPED,
    PCMK_STATUS_ROLE_DEMOTING,
    PCMK_STATUS_ROLE_MIGRATING,
    PCMK_STATUS_ROLE_PROMOTED,
    PCMK_STATUS_ROLE_PROMOTING,
    PCMK_STATUS_ROLE_STARTED,
    PCMK_STATUS_ROLE_STARTING,
    PCMK_STATUS_ROLE_STOPPED,
    PCMK_STATUS_ROLE_STOPPING,
    PCMK_STATUS_ROLE_UNPROMOTED,
    PCMK_STATUS_ROLES_PENDING,
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


class ResourceType(Enum):
    PRIMITIVE = "primitive"
    GROUP = "group"
    CLONE = "clone"
    BUNDLE = "bundle"


# used to check if any value other than None is present
# in optional attributes of status dto
class NotNoneValue:
    pass


NOT_NONE: Final = NotNoneValue()


StateValueType = Union[str, bool, NotNoneValue, set[str]]

AttributeTuple = tuple[str, StateValueType]


class ResourceState(Enum):
    """
    possible values for checking the state of the resource
    """

    STARTED: AttributeTuple = ("role", PCMK_STATUS_ROLE_STARTED)
    STOPPED: AttributeTuple = ("role", PCMK_STATUS_ROLE_STOPPED)
    PROMOTED: AttributeTuple = ("role", PCMK_STATUS_ROLE_PROMOTED)
    UNPROMOTED: AttributeTuple = ("role", PCMK_STATUS_ROLE_UNPROMOTED)
    STARTING: AttributeTuple = ("role", PCMK_STATUS_ROLE_STARTING)
    STOPPING: AttributeTuple = ("role", PCMK_STATUS_ROLE_STOPPING)
    MIGRATING: AttributeTuple = ("role", PCMK_STATUS_ROLE_MIGRATING)
    PROMOTING: AttributeTuple = ("role", PCMK_STATUS_ROLE_PROMOTING)
    DEMOTING: AttributeTuple = ("role", PCMK_STATUS_ROLE_DEMOTING)
    MONITORING: AttributeTuple = ("pending", "Monitoring")
    DISABLED: AttributeTuple = ("disabled", True)
    ENABLED: AttributeTuple = ("disabled", False)
    MANAGED: AttributeTuple = ("managed", True)
    UNMANAGED: AttributeTuple = ("managed", False)
    MAINTENANCE: AttributeTuple = ("maintenance", True)
    FAILED: AttributeTuple = ("failed", True)
    ACTIVE: AttributeTuple = ("active", True)
    ORPHANED: AttributeTuple = ("orphaned", True)
    BLOCKED: AttributeTuple = ("blocked", True)
    FAILURE_IGNORED: AttributeTuple = ("failure_ignored", True)
    PENDING: list[AttributeTuple] = [
        ("role", set(PCMK_STATUS_ROLES_PENDING)),
        ("pending", "Monitoring"),
    ]
    LOCKED_TO: AttributeTuple = ("locked_to", NOT_NONE)


ResourceStateExactCheck = Literal[ResourceState.LOCKED_TO]

EXACT_CHECK_STATES = (ResourceState.LOCKED_TO,)


class MoreChildrenQuantifierType(Enum):
    ALL = auto()
    ANY = auto()
    NONE = auto()


@dataclass(frozen=True)
class PrimitiveInstances:
    instances: Sequence[PrimitiveStatusDto]


@dataclass(frozen=True)
class GroupInstances:
    instances: Sequence[GroupStatusDto]


CheckedResourceType = Union[
    PrimitiveInstances,
    GroupInstances,
    CloneStatusDto,
    BundleStatusDto,
]

_TYPE_MAP = {
    PrimitiveStatusDto: ResourceType.PRIMITIVE,
    GroupStatusDto: ResourceType.GROUP,
    CloneStatusDto: ResourceType.CLONE,
    BundleStatusDto: ResourceType.BUNDLE,
}


_UNIQUE_RESOURCES_TYPES = (CloneStatusDto, BundleStatusDto)
_UNIQUE_RESOURCES_CONST = tuple(
    _TYPE_MAP[res_type] for res_type in _UNIQUE_RESOURCES_TYPES
)

_PROMOTABLE_RESOURCES_TYPES = (CloneStatusDto,)
_PROMOTABLE_RESOURCES_CONST = tuple(
    _TYPE_MAP[res_type] for res_type in _PROMOTABLE_RESOURCES_TYPES
)


def none(iterable: Iterable[object]) -> bool:
    return not any(iterable)


_MORE_CHILDREN_QUANTIFIER_MAP = {
    MoreChildrenQuantifierType.ALL: all,
    MoreChildrenQuantifierType.ANY: any,
    MoreChildrenQuantifierType.NONE: none,
}


class QueryException(Exception):
    pass


class MembersQuantifierUnsupportedException(QueryException):
    pass


class InstancesQuantifierUnsupportedException(QueryException):
    pass


class ResourceException(Exception):
    def __init__(self, resource_id: str, instance_id: Optional[str]):
        self.resource_id = resource_id
        self.instance_id = instance_id


class ResourceNonExistentException(ResourceException):
    pass


class ResourceNotInGroupException(ResourceException):
    pass


class ResourceUnexpectedTypeException(ResourceException):
    def __init__(
        self,
        resource_id: str,
        instance_id: Optional[str],
        resource_type: ResourceType,
        expected_types: list[ResourceType],
    ):
        super().__init__(resource_id, instance_id)
        self.resource_type = resource_type
        self.expected_types = expected_types


def can_be_unique(resource_type: ResourceType) -> bool:
    return resource_type in _UNIQUE_RESOURCES_CONST


def can_be_promotable(resource_type: ResourceType) -> bool:
    return resource_type in _PROMOTABLE_RESOURCES_CONST


class ResourcesStatusFacade:
    def __init__(self, resources: Sequence[AnyResourceStatusDto]):
        self._resources = resources
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
                    self._child_parent_map[instance.resource_id] = (
                        resource.resource_id
                    )
                    self._resource_map[instance.resource_id].append(instance)
                    if isinstance(instance, GroupStatusDto):
                        self.__add_group_children_to_maps(instance)
            elif isinstance(resource, BundleStatusDto):
                self._bundle_defined = True
                for replica in resource.replicas:
                    member = replica.member
                    if member is not None:
                        self._child_parent_map[member.resource_id] = (
                            resource.resource_id
                        )
                        self._resource_map[member.resource_id].append(member)
                        self._bundle_member_node_map[id(member)] = (
                            replica.container.node_names
                        )

    @classmethod
    def from_resources_status_dto(
        cls, resources_status_dto: ResourcesStatusDto
    ) -> "ResourcesStatusFacade":
        """
        Create ResourcesStatusFacade from ResourcesStatusDto

        resources_status_dto -- dto with status of the resources in cluster
        """
        return cls(resources_status_dto.resources)

    def get_resource_one_instance(
        self, resource_id: str, instance_id: Optional[str]
    ) -> Optional[AnyResourceStatusDto]:
        """
        Get one instance of resource with given id. Get instance that
        appears first in the status xml if instance_id is not specified. Return
        None if resource with given id does not exist.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
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

    def get_resource_all_instances(
        self, resource_id: str
    ) -> Optional[list[AnyResourceStatusDto]]:
        """
        Get a list of all the instances of resource with the given id. Return
        None if resource with the given id does not exist.

        resource_id -- id of the resource
        """
        return self._resource_map.get(resource_id)

    def exists(self, resource_id: str, instance_id: Optional[str]) -> bool:
        """
        Check if resource with the given id exists in the cluster

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        return (
            self.get_resource_one_instance(resource_id, instance_id) is not None
        )

    def get_type(
        self, resource_id: str, instance_id: Optional[str]
    ) -> ResourceType:
        """
        Return the type of the resource

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        resource = self.get_resource_one_instance(resource_id, instance_id)
        if resource is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        return _TYPE_MAP[type(resource)]

    def is_stonith(self, resource_id: str, instance_id: Optional[str]) -> bool:
        """
        Check if the resource with the given id is a stonith resource

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        resource = self.get_resource_one_instance(resource_id, instance_id)
        if resource is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        return isinstance(
            resource, PrimitiveStatusDto
        ) and resource.resource_agent.startswith("stonith:")

    def is_promotable(
        self, resource_id: str, instance_id: Optional[str]
    ) -> bool:
        """
        Check if the resource with the given id is promotable. Usable only
        of clone resources.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        resource = self.get_resource_one_instance(resource_id, instance_id)
        if resource is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        if not isinstance(resource, _PROMOTABLE_RESOURCES_TYPES):
            raise ResourceUnexpectedTypeException(
                resource_id,
                instance_id,
                _TYPE_MAP[type(resource)],
                list(_PROMOTABLE_RESOURCES_CONST),
            )

        return resource.multi_state

    def is_unique(self, resource_id: str, instance_id: Optional[str]) -> bool:
        """
        Check if the resource with the given id is globally unique. Usable only
        on clone and bundle resources.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """

        resource = self.get_resource_one_instance(resource_id, instance_id)
        if resource is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        if not isinstance(resource, _UNIQUE_RESOURCES_TYPES):
            raise ResourceUnexpectedTypeException(
                resource_id,
                instance_id,
                _TYPE_MAP[type(resource)],
                list(_UNIQUE_RESOURCES_CONST),
            )

        return resource.unique

    def _get_instances_for_state_check(
        self, resource_id: str, instance_id: Optional[str]
    ) -> CheckedResourceType:
        if not self.exists(resource_id, instance_id):
            raise ResourceNonExistentException(resource_id, instance_id)

        is_in_clone = (
            self.get_type(resource_id, instance_id)
            in (ResourceType.PRIMITIVE, ResourceType.GROUP)
            and self.get_parent_clone_id(resource_id, instance_id) is not None
        )
        is_clone = self.get_type(resource_id, instance_id) == ResourceType.CLONE

        if self._bundle_defined and (is_in_clone or is_clone):
            # This is due to pacemaker providing broken data in this case.
            # See issue: https://projects.clusterlabs.org/T722
            raise NotImplementedError(
                "Queries on clone state when bundle resources are present "
                "in the cluster are unsupported"
            )

        resource = self.get_resource_one_instance(resource_id, instance_id)
        if isinstance(resource, (CloneStatusDto, BundleStatusDto)):
            return resource

        if instance_id is None:
            instance_list = cast(
                Optional[list[Union[PrimitiveStatusDto, GroupStatusDto]]],
                self.get_resource_all_instances(resource_id),
            )
        else:
            instance_list = [resource] if resource is not None else None

        if instance_list is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        if is_in_clone:
            instance_list = _filter_clone_orphans(instance_list)

        if not instance_list:
            raise ResourceNonExistentException(resource_id, instance_id)

        if self.get_type(resource_id, instance_id) == ResourceType.PRIMITIVE:
            return PrimitiveInstances(
                cast(list[PrimitiveStatusDto], instance_list)
            )

        return GroupInstances(cast(list[GroupStatusDto], instance_list))

    def _validate_members_quantifier(
        self,
        resource: CheckedResourceType,
        members_quantifier: Optional[MoreChildrenQuantifierType],
    ) -> None:
        if members_quantifier is None:
            return

        if isinstance(resource, GroupInstances):
            return

        if isinstance(resource, CloneStatusDto):
            member_id_list = self.get_members(resource.resource_id, None)
            if any(
                self.get_type(member_id, None) == ResourceType.GROUP
                for member_id in member_id_list
            ):
                return

        raise MembersQuantifierUnsupportedException()

    def _validate_instance_quantifier(
        self,
        resource: CheckedResourceType,
        instances_quantifier: Optional[MoreChildrenQuantifierType],
    ) -> None:
        # pylint: disable=no-self-use
        if instances_quantifier is None:
            return

        if isinstance(resource, (BundleStatusDto, CloneStatusDto)):
            return

        if len(resource.instances) > 1:
            return

        raise InstancesQuantifierUnsupportedException()

    def is_state(
        self,
        resource_id: str,
        instance_id: Optional[str],
        state: ResourceState,
        expected_node_name: Optional[str] = None,
        members_quantifier: Optional[MoreChildrenQuantifierType] = None,
        instances_quantifier: Optional[MoreChildrenQuantifierType] = None,
    ) -> bool:
        """
        Check if the resource with the given id is in expected state.
        With groups, the state is read and evaluated on the group first. If the
        state cannot be determined from only the group, evaluate the state of
        the member resources and return true if the query is true for ALL of
        the members. With clones and bundles, the state is read and evaluated
        on the clone or bundle first. If the state cannot be determined from
        only the clone or bundle, evaluate the state on the instances and
        return true if the query is true for ANY of the instances.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        state -- expected state of the resource
        expected_node_name -- Check if the resource is in given state on a
            given node. If specified, always check only group members, clone
            instances and bundle replicas even when the attribute is present
            in the group, clone or bundle status dto respectively.
        members_quantifier -- Specify how to treat group members. If specified,
            check only member resources even when the attribute is present in
            the group status dto.
        instances_quantifier -- Specify how to treat instances of clones and
            bundles. If specified, check only instances even when the attribute
            is present in the clone/bundle status dto.
        """
        resource = self._get_instances_for_state_check(resource_id, instance_id)

        self._validate_members_quantifier(resource, members_quantifier)
        self._validate_instance_quantifier(resource, instances_quantifier)

        if not isinstance(state.value, list):
            checked_state = [state.value]
        else:
            checked_state = state.value

        return any(
            self._check_resources_state_attributes(
                resource,
                checked_attribute,
                real_expected_value,
                expected_node_name,
                members_quantifier,
                instances_quantifier,
            )
            for checked_attribute, real_expected_value in checked_state
        )

    def is_state_exact_value(
        self,
        resource_id: str,
        instance_id: Optional[str],
        state: ResourceStateExactCheck,
        expected_state_value: str,
        expected_node_name: Optional[str] = None,
        members_quantifier: Optional[MoreChildrenQuantifierType] = None,
        instances_quantifier: Optional[MoreChildrenQuantifierType] = None,
    ) -> bool:
        """
        Check if the state attribute of the resource contains the expected
        value. With groups, the state is read and evaluated on the group first.
        If the state cannot be determined from only the group, evaluate the
        state of the member resources and return true if the query is true for
        ALL of the members. With clones and bundles, the state is read and
        evaluated on the clone or bundle first. If the state cannot be
        determined from only the clone or bundle, evaluate the state on the
        instances and return true if the query is true for ANY of the instances.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        state -- state describing which state attribute will be checked
        expected_state_value -- expected value of the attribute
        expected_node_name -- Check if the resource is in given state on a
            given node. If specified, always check only group members, clone
            instances and bundle replicas even when the attribute is present
            in the group, clone or bundle status dto respectively.
        members_quantifier -- Specify how to treat group members. If specified,
            check only member resources even when the attribute is present in
            the group status dto.
        instances_quantifier -- Specify how to treat instances of clones and
            bundles. If specified, check only instances even when the attribute
            is present in the clone/bundle status dto.
        """
        resource = self._get_instances_for_state_check(resource_id, instance_id)

        self._validate_members_quantifier(resource, members_quantifier)
        self._validate_instance_quantifier(resource, instances_quantifier)

        if not isinstance(state.value, list):
            checked_state = [state.value]
        else:
            checked_state = state.value

        return any(
            self._check_resources_state_attributes(
                resource,
                checked_attribute,
                expected_state_value,
                expected_node_name,
                members_quantifier,
                instances_quantifier,
            )
            for checked_attribute, _ in checked_state
        )

    def get_parent_group_id(
        self,
        resource_id: str,
        instance_id: Optional[str],
    ) -> Optional[str]:
        """
        Check if the resource is in any group and return group id if the
        resource is in group.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        resource = self.get_resource_one_instance(resource_id, instance_id)
        if resource is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        if not isinstance(resource, PrimitiveStatusDto):
            raise ResourceUnexpectedTypeException(
                resource_id,
                instance_id,
                _TYPE_MAP[type(resource)],
                [ResourceType.PRIMITIVE],
            )

        if not self._check_parent_type(resource_id, ResourceType.GROUP):
            return None

        return self._child_parent_map[resource_id]

    def get_parent_clone_id(
        self,
        resource_id: str,
        instance_id: Optional[str],
    ) -> Optional[str]:
        """
        Check if the resource is inside any clone and return clone id if the
        resource is in clone. Member of a cloned group is in clone as well.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        resource = self.get_resource_one_instance(resource_id, instance_id)
        if resource is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        if not isinstance(resource, (PrimitiveStatusDto, GroupStatusDto)):
            raise ResourceUnexpectedTypeException(
                resource_id,
                instance_id,
                _TYPE_MAP[type(resource)],
                [ResourceType.PRIMITIVE, ResourceType.GROUP],
            )

        checked_id = resource_id
        if self._check_parent_type(checked_id, ResourceType.GROUP):
            checked_id = self._child_parent_map[resource_id]

        if not self._check_parent_type(checked_id, ResourceType.CLONE):
            return None

        return self._child_parent_map[checked_id]

    def get_parent_bundle_id(
        self,
        resource_id: str,
        instance_id: Optional[str],
    ) -> Optional[str]:
        """
        Check if the resource is inside any bundle and return bundle id if the
        resource is in bundle.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        resource = self.get_resource_one_instance(resource_id, instance_id)
        if resource is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        if not isinstance(resource, PrimitiveStatusDto):
            raise ResourceUnexpectedTypeException(
                resource_id,
                instance_id,
                _TYPE_MAP[type(resource)],
                [ResourceType.PRIMITIVE],
            )

        if not self._check_parent_type(resource_id, ResourceType.BUNDLE):
            return None

        return self._child_parent_map[resource_id]

    def get_index_in_group(
        self, resource_id: str, instance_id: Optional[str]
    ) -> int:
        """
        Return the index of the resource in a group. Usable only for primitive
        resources.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        if not self.exists(resource_id, instance_id):
            raise ResourceNonExistentException(resource_id, instance_id)

        resource_type = self.get_type(resource_id, instance_id)
        if resource_type != ResourceType.PRIMITIVE:
            raise ResourceUnexpectedTypeException(
                resource_id,
                instance_id,
                resource_type,
                [ResourceType.PRIMITIVE],
            )

        parent_id = self._child_parent_map.get(resource_id, None)
        if parent_id is None:
            raise ResourceNotInGroupException(resource_id, instance_id)

        parent_resource = self.get_resource_one_instance(parent_id, None)
        if not isinstance(parent_resource, GroupStatusDto):
            raise ResourceNotInGroupException(resource_id, instance_id)

        return [res.resource_id for res in parent_resource.members].index(
            resource_id
        )

    def get_members(
        self, resource_id: str, instance_id: Optional[str]
    ) -> list[str]:
        """
        Return resource ids of members of a group, clone or bundle

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        resource = self.get_resource_one_instance(resource_id, instance_id)
        if resource is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        if isinstance(resource, GroupStatusDto):
            return [member.resource_id for member in resource.members]

        if isinstance(resource, CloneStatusDto):
            return list(
                set(
                    instance.resource_id
                    for instance in resource.instances
                    if not _is_orphaned(instance)
                )
            )

        if isinstance(resource, BundleStatusDto):
            return list(
                set(
                    replica.member.resource_id
                    for replica in resource.replicas
                    if replica.member is not None
                )
            )

        raise ResourceUnexpectedTypeException(
            resource_id,
            instance_id,
            ResourceType.PRIMITIVE,
            [ResourceType.GROUP, ResourceType.CLONE, ResourceType.BUNDLE],
        )

    def get_nodes(
        self, resource_id: str, instance_id: Optional[str]
    ) -> list[str]:
        """
        Return nodes on which resource is running. For groups, return nodes
        on which any of the members is running. For clones or bundles return
        nodes on which any of the instances or replicas are running.

        resource_id -- id of the resource
        instance_id -- id describing unique instance of cloned or bundled
            resource
        """
        if instance_id is not None:
            resource = self.get_resource_one_instance(resource_id, instance_id)
            instance_list = [resource] if resource is not None else None
        else:
            instance_list = self.get_resource_all_instances(resource_id)

        if instance_list is None:
            raise ResourceNonExistentException(resource_id, instance_id)

        nodes = []
        for instance in instance_list:
            if isinstance(instance, PrimitiveStatusDto):
                nodes.extend(self._get_primitive_nodes(instance))
            elif isinstance(instance, GroupStatusDto):
                nodes.extend(self._get_group_nodes(instance))
            elif isinstance(instance, CloneStatusDto):
                nodes.extend(self._get_clone_nodes(instance))
            else:
                nodes.extend(self._get_bundle_nodes(instance))

        return sorted(nodes)

    def _get_primitive_nodes(self, primitive: PrimitiveStatusDto) -> list[str]:
        if id(primitive) in self._bundle_member_node_map:
            return self._bundle_member_node_map[id(primitive)]
        return primitive.node_names

    def _get_group_nodes(self, group: GroupStatusDto) -> list[str]:
        node_set = set()
        for member in group.members:
            node_set.update(self._get_primitive_nodes(member))
        return list(node_set)

    def _get_clone_nodes(self, clone: CloneStatusDto) -> list[str]:
        node_list = []
        instance_list = _filter_clone_orphans(clone.instances)
        for instance in instance_list:
            if isinstance(instance, PrimitiveStatusDto):
                node_list.extend(self._get_primitive_nodes(instance))
            elif isinstance(instance, GroupStatusDto):
                node_list.extend(self._get_group_nodes(instance))
        return node_list

    def _get_bundle_nodes(self, bundle: BundleStatusDto) -> list[str]:
        node_list = []
        for replica in bundle.replicas:
            if replica.member is not None:
                node_list.extend(self._get_primitive_nodes(replica.member))
            else:
                node_list.extend(self._get_primitive_nodes(replica.container))
        return node_list

    def _check_parent_type(
        self,
        resource_id: str,
        expected_parent_type: ResourceType,
    ) -> bool:
        parent_id = self._child_parent_map.get(resource_id)
        return (
            parent_id is not None
            and self.get_type(parent_id, None) == expected_parent_type
        )

    def __add_group_children_to_maps(self, group: GroupStatusDto) -> None:
        for child in group.members:
            self._resource_map[child.resource_id].append(child)
            self._child_parent_map[child.resource_id] = group.resource_id

    def _check_resources_state_attributes(
        self,
        checked_resource: CheckedResourceType,
        checked_attribute: str,
        expected_attribute_value: StateValueType,
        expected_node_name: Optional[str] = None,
        members_quantifier: Optional[MoreChildrenQuantifierType] = None,
        instances_quantifier: Optional[MoreChildrenQuantifierType] = None,
    ) -> bool:
        if isinstance(checked_resource, CloneStatusDto):
            return self._clone_state(
                checked_resource,
                checked_attribute,
                expected_attribute_value,
                members_quantifier,
                instances_quantifier,
                expected_node_name,
            )

        if isinstance(checked_resource, BundleStatusDto):
            return self._bundle_state(
                checked_resource,
                checked_attribute,
                expected_attribute_value,
                instances_quantifier,
                expected_node_name,
            )

        more_children_check = (
            instances_quantifier or MoreChildrenQuantifierType.ANY
        )

        if isinstance(checked_resource, PrimitiveInstances):
            return _MORE_CHILDREN_QUANTIFIER_MAP[more_children_check](
                self._primitive_state(
                    resource,
                    checked_attribute,
                    expected_attribute_value,
                    expected_node_name,
                )
                for resource in checked_resource.instances
            )

        if isinstance(checked_resource, GroupInstances):
            return _MORE_CHILDREN_QUANTIFIER_MAP[more_children_check](
                self._group_state(
                    resource,
                    checked_attribute,
                    expected_attribute_value,
                    members_quantifier,
                    expected_node_name,
                )
                for resource in checked_resource.instances
            )

        return False

    def _primitive_state(
        self,
        primitive: PrimitiveStatusDto,
        checked_attribute: str,
        expected_attribute_value: StateValueType,
        expected_node_name: Optional[str],
    ) -> bool:
        if checked_attribute == ResourceState.DISABLED.value[0]:
            result = (
                primitive.target_role == PCMK_ROLE_STOPPED
            ) == expected_attribute_value
        else:
            result = _check_attribute_value(
                primitive, checked_attribute, expected_attribute_value
            )

        if expected_node_name is None:
            return result

        node_names = primitive.node_names
        if id(primitive) in self._bundle_member_node_map:
            node_names = self._bundle_member_node_map[id(primitive)]

        return result and expected_node_name in node_names

    def _group_state(
        self,
        group: GroupStatusDto,
        checked_attribute: str,
        expected_attribute_value: StateValueType,
        members_quantifier: Optional[MoreChildrenQuantifierType],
        expected_node_name: Optional[str],
    ) -> bool:
        if _can_check_non_primitive(
            group,
            checked_attribute,
            members_quantifier,
            expected_node_name is not None,
        ):
            return _check_attribute_value(
                group, checked_attribute, expected_attribute_value
            )

        if not group.members:
            return False

        if members_quantifier is None:
            members_quantifier = MoreChildrenQuantifierType.ALL

        return _MORE_CHILDREN_QUANTIFIER_MAP[members_quantifier](
            self._primitive_state(
                primitive,
                checked_attribute,
                expected_attribute_value,
                expected_node_name,
            )
            for primitive in group.members
        )

    def _clone_state(
        self,
        clone: CloneStatusDto,
        checked_attribute: str,
        expected_attribute_value: StateValueType,
        members_quantifier: Optional[MoreChildrenQuantifierType],
        instances_quantifier: Optional[MoreChildrenQuantifierType],
        expected_node_name: Optional[str],
    ) -> bool:
        if _can_check_non_primitive(
            clone,
            checked_attribute,
            instances_quantifier,
            expected_node_name is not None,
        ):
            return _check_attribute_value(
                clone, checked_attribute, expected_attribute_value
            )

        instance_list = _filter_clone_orphans(clone.instances)

        if not instance_list:
            return False

        if instances_quantifier is None:
            instances_quantifier = MoreChildrenQuantifierType.ANY

        return _MORE_CHILDREN_QUANTIFIER_MAP[instances_quantifier](
            (
                self._primitive_state(
                    instance,
                    checked_attribute,
                    expected_attribute_value,
                    expected_node_name,
                )
                if isinstance(instance, PrimitiveStatusDto)
                else self._group_state(
                    instance,
                    checked_attribute,
                    expected_attribute_value,
                    members_quantifier,
                    expected_node_name,
                )
            )
            for instance in instance_list
        )

    def _bundle_state(
        self,
        bundle: BundleStatusDto,
        checked_attribute: str,
        expected_attribute_value: StateValueType,
        instances_quantifier: Optional[MoreChildrenQuantifierType],
        expected_node_name: Optional[str],
    ) -> bool:
        if _can_check_non_primitive(
            bundle,
            checked_attribute,
            instances_quantifier,
            expected_node_name is not None,
        ):
            return _check_attribute_value(
                bundle, checked_attribute, expected_attribute_value
            )

        if not bundle.replicas:
            return False

        if instances_quantifier is None:
            instances_quantifier = MoreChildrenQuantifierType.ANY

        return _MORE_CHILDREN_QUANTIFIER_MAP[instances_quantifier](
            self._bundle_replica_state(
                replica,
                checked_attribute,
                expected_attribute_value,
                expected_node_name,
            )
            for replica in bundle.replicas
        )

    def _bundle_replica_state(
        self,
        replica: BundleReplicaStatusDto,
        checked_attribute: str,
        expected_attribute_value: StateValueType,
        expected_node_name: Optional[str],
    ) -> bool:
        if replica.member is None:
            return self._primitive_state(
                replica.container,
                checked_attribute,
                expected_attribute_value,
                expected_node_name,
            )

        return self._primitive_state(
            replica.member,
            checked_attribute,
            expected_attribute_value,
            expected_node_name,
        )


def _can_check_non_primitive(
    resource: AnyResourceStatusDto,
    attribute_name: str,
    more_children_check: Optional[MoreChildrenQuantifierType],
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


def _filter_clone_orphans(
    instance_list: Sequence[Union[PrimitiveStatusDto, GroupStatusDto]]
) -> list[Union[PrimitiveStatusDto, GroupStatusDto]]:
    return [
        instance for instance in instance_list if not _is_orphaned(instance)
    ]


def _check_attribute_value(
    status_dto: AnyResourceStatusDto,
    attribute_name: str,
    expected_value: StateValueType,
) -> bool:
    real_value = getattr(status_dto, attribute_name)

    if isinstance(expected_value, set):
        return real_value in expected_value
    if expected_value == NOT_NONE:
        return real_value is not None

    return real_value == expected_value

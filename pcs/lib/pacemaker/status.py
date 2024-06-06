from collections import Counter
from typing import (
    Optional,
    Sequence,
    cast,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.const import (
    PCMK_ROLES,
    PCMK_STATUS_ROLES,
    PcmkRoleType,
    PcmkStatusRoleType,
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
from pcs.common.str_tools import format_list
from pcs.lib.pacemaker.values import is_true

_PRIMITIVE_TAG = "resource"
_GROUP_TAG = "group"
_CLONE_TAG = "clone"
_BUNDLE_TAG = "bundle"
_REPLICA_TAG = "replica"


class ClusterStatusParsingError(Exception):
    def __init__(self, resource_id: str):
        self.resource_id = resource_id


class EmptyResourceIdError(ClusterStatusParsingError):
    def __init__(self) -> None:
        super().__init__("")


class EmptyNodeNameError(ClusterStatusParsingError):
    pass


class UnknownPcmkRoleError(ClusterStatusParsingError):
    def __init__(self, resource_id: str, role: str):
        super().__init__(resource_id)
        self.role = role


class UnexpectedMemberError(ClusterStatusParsingError):
    def __init__(
        self,
        resource_id: str,
        resource_type: str,
        member_id: str,
        member_type: str,
        expected_types: list[str],
    ):
        super().__init__(resource_id)
        self.resource_type = resource_type
        self.member_id = member_id
        self.member_type = member_type
        self.expected_types = expected_types


class MixedMembersError(ClusterStatusParsingError):
    pass


class DifferentMemberIdsError(ClusterStatusParsingError):
    pass


class BundleReplicaMissingImplicitResourceError(ClusterStatusParsingError):
    def __init__(
        self, resource_id: str, replica_id: str, implicit_resource_type: str
    ):
        super().__init__(resource_id)
        self.replica_id = replica_id
        self.implicit_type = implicit_resource_type


class BundleReplicaInvalidMemberCountError(ClusterStatusParsingError):
    def __init__(self, resource_id: str, replica_id: str):
        super().__init__(resource_id)
        self.replica_id = replica_id


class BundleDifferentReplicas(ClusterStatusParsingError):
    pass


class BundleSameIdAsImplicitResourceError(Exception):
    def __init__(self, bundle_id: str, bad_ids: list[str]):
        self.bundle_id = bundle_id
        self.bad_ids = bad_ids


def cluster_status_parsing_error_to_report(
    e: ClusterStatusParsingError,
    severity: reports.ReportItemSeverity = reports.ReportItemSeverity.error(),
) -> reports.ReportItem:
    reason = ""
    if isinstance(e, EmptyResourceIdError):
        reason = "Resource with an empty id"
    elif isinstance(e, EmptyNodeNameError):
        reason = (
            f"Resource '{e.resource_id}' contains a node with an empty name"
        )
    elif isinstance(e, UnknownPcmkRoleError):
        reason = (
            f"Resource '{e.resource_id}' contains an unknown "
            f"role '{e.role}'"
        )
    elif isinstance(e, UnexpectedMemberError):
        reason = (
            f"Unexpected resource '{e.member_id}' of type '{e.member_type}' "
            f"inside of resource '{e.resource_id}' of type '{e.resource_type}'."
            f" Only resources of type {format_list(e.expected_types)} "
            f"can be in a {e.resource_type}"
        )

    elif isinstance(e, MixedMembersError):
        reason = f"Primitive and group members mixed in clone '{e.resource_id}'"
    elif isinstance(e, DifferentMemberIdsError):
        reason = f"Members with different ids in clone '{e.resource_id}'"
    elif isinstance(e, BundleReplicaMissingImplicitResourceError):
        reason = (
            f"Replica '{e.replica_id}' of bundle '{e.resource_id}' "
            f"is missing implicit {e.implicit_type} resource"
        )
    elif isinstance(e, BundleReplicaInvalidMemberCountError):
        reason = (
            f"Replica '{e.replica_id}' of bundle '{e.resource_id}' has "
            "invalid number of members"
        )
    elif isinstance(e, BundleDifferentReplicas):
        reason = f"Replicas of bundle '{e.resource_id}' are not the same"

    return reports.ReportItem(
        severity,
        reports.messages.BadClusterStateData(reason),
    )


def _primitive_to_dto(
    primitive_el: _Element, remove_instance_suffix: bool = False
) -> PrimitiveStatusDto:
    resource_id = _get_resource_id(primitive_el)
    clone_suffix = None
    if remove_instance_suffix:
        resource_id, clone_suffix = _remove_clone_suffix(resource_id)

    role = _get_role(primitive_el)
    target_role = _get_target_role(primitive_el)

    node_names = [
        str(node.attrib["name"]) for node in primitive_el.iterfind("node")
    ]

    if node_names and any(not name for name in node_names):
        raise EmptyNodeNameError(resource_id)

    return PrimitiveStatusDto(
        resource_id,
        clone_suffix,
        str(primitive_el.attrib["resource_agent"]),
        role,
        target_role,
        is_true(primitive_el.get("active", "false")),
        is_true(primitive_el.get("orphaned", "false")),
        is_true(primitive_el.get("blocked", "false")),
        is_true(primitive_el.get("maintenance", "false")),
        primitive_el.get("description"),
        is_true(primitive_el.get("failed", "false")),
        is_true(primitive_el.get("managed", "false")),
        is_true(primitive_el.get("failure_ignored", "false")),
        node_names,
        primitive_el.get("pending"),
        primitive_el.get("locked_to"),
    )


def _group_to_dto(
    group_el: _Element, remove_instance_suffix: bool = False
) -> GroupStatusDto:
    # clone instance id present even when the clone is non unique
    group_id, clone_instance_id = _remove_clone_suffix(
        _get_resource_id(group_el)
    )

    member_list = []

    for member in group_el:
        if member.tag == _PRIMITIVE_TAG:
            member_list.append(
                _primitive_to_dto(member, remove_instance_suffix)
            )
        else:
            raise UnexpectedMemberError(
                group_id,
                "group",
                str(member.attrib["id"]),
                member.tag,
                ["primitive"],
            )

    return GroupStatusDto(
        group_id,
        clone_instance_id,
        is_true(group_el.get("maintenance", "false")),
        group_el.get("description"),
        is_true(group_el.get("managed", "false")),
        is_true(group_el.get("disabled", "false")),
        member_list,
    )


def _clone_to_dto(
    clone_el: _Element, _remove_instance_suffix: bool = False
) -> CloneStatusDto:
    clone_id = _get_resource_id(clone_el)
    is_unique = is_true(clone_el.get("unique", "false"))

    target_role = _get_target_role(clone_el)

    primitive_list = []
    group_list = []

    for member in clone_el:
        if member.tag == _PRIMITIVE_TAG:
            primitive_list.append(_primitive_to_dto(member, is_unique))
        elif member.tag == _GROUP_TAG:
            group_list.append(_group_to_dto(member, is_unique))
        else:
            raise UnexpectedMemberError(
                clone_id,
                "clone",
                str(member.attrib["id"]),
                member.tag,
                ["primitive", "group"],
            )

    if primitive_list and group_list:
        raise MixedMembersError(clone_id)

    if primitive_list:
        if len(set(res.resource_id for res in primitive_list)) > 1:
            raise DifferentMemberIdsError(clone_id)
    if group_list:
        group_ids = set(group.resource_id for group in group_list)
        children_ids = set(
            tuple(child.resource_id for child in group.members)
            for group in group_list
        )
        if len(group_ids) > 1 or len(children_ids) > 1:
            raise DifferentMemberIdsError(clone_id)

    return CloneStatusDto(
        clone_id,
        is_true(clone_el.get("multi_state", "false")),
        is_unique,
        is_true(clone_el.get("maintenance", "false")),
        clone_el.get("description"),
        is_true(clone_el.get("managed", "false")),
        is_true(clone_el.get("disabled", "false")),
        is_true(clone_el.get("failed", "false")),
        is_true(clone_el.get("failure_ignored", "false")),
        target_role,
        primitive_list or group_list,
    )


def _bundle_to_dto(
    bundle_el: _Element, _remove_instance_suffix: bool = False
) -> BundleStatusDto:
    bundle_id = _get_resource_id(bundle_el)
    bundle_type = str(bundle_el.attrib["type"])
    is_unique = is_true(bundle_el.get("unique", "false"))

    replica_list = [
        _replica_to_dto(replica, bundle_id, bundle_type, is_unique)
        for replica in bundle_el.iterfind(_REPLICA_TAG)
    ]

    if not _replicas_valid(replica_list):
        raise BundleDifferentReplicas(bundle_id)

    return BundleStatusDto(
        bundle_id,
        bundle_type,
        str(bundle_el.attrib["image"]),
        is_unique,
        is_true(bundle_el.get("maintenance", "false")),
        bundle_el.get("description"),
        is_true(bundle_el.get("managed", "false")),
        is_true(bundle_el.get("failed", "false")),
        replica_list,
    )


class ClusterStatusParser:
    TAG_TO_FUNCTION = {
        _PRIMITIVE_TAG: _primitive_to_dto,
        _GROUP_TAG: _group_to_dto,
        _CLONE_TAG: _clone_to_dto,
        _BUNDLE_TAG: _bundle_to_dto,
    }

    def __init__(self, status: _Element):
        """
        status -- xml element from crm_mon xml, validated using the appropriate
            rng schema
        """
        self._status = status
        self._warnings: reports.ReportItemList = []

    def status_xml_to_dto(self) -> ResourcesStatusDto:
        """
        Return dto containing status of configured resources in the cluster
        """
        resource_list = cast(list[_Element], self._status.xpath("resources/*"))

        resource_dto_list = []
        for resource in resource_list:
            try:
                resource_dto = cast(
                    AnyResourceStatusDto,
                    self.TAG_TO_FUNCTION[resource.tag](resource),
                )
                resource_dto_list.append(resource_dto)
            except BundleSameIdAsImplicitResourceError as e:
                # This is the only error that the user can cause directly by
                # setting the name of the bundle member to be same as one of
                # the implicitly created resource.
                # We only skip such bundles while still providing status of the
                # other resources.
                self._warnings.append(
                    reports.ReportItem.warning(
                        reports.messages.ClusterStatusBundleMemberIdAsImplicit(
                            e.bundle_id, e.bad_ids
                        )
                    )
                )
            except BundleReplicaMissingImplicitResourceError as e:
                # TODO crm_mon on Fedora 39 returns resource_agent in legacy
                # format "ocf::*:*" instead of the new "ocf:*:*" and the parser
                # then cannot find the proper resources in the replicas.
                # Skip bundles when the legacy format is used.
                self._warnings.append(
                    cluster_status_parsing_error_to_report(
                        e, reports.ReportItemSeverity.warning()
                    )
                )

        return ResourcesStatusDto(resource_dto_list)

    def get_warnings(self) -> reports.ReportItemList:
        return self._warnings


def _get_resource_id(resource: _Element) -> str:
    resource_id = resource.attrib["id"]
    if not resource_id:
        raise EmptyResourceIdError()
    return str(resource_id)


def _get_role(resource: _Element) -> PcmkStatusRoleType:
    role = resource.get("role")
    if role is None or role not in PCMK_STATUS_ROLES:
        raise UnknownPcmkRoleError(str(resource.get("id")), str(role))
    return PcmkStatusRoleType(role)


def _get_target_role(resource: _Element) -> Optional[PcmkRoleType]:
    target_role = resource.get("target_role")
    if target_role is None:
        return None
    if target_role not in PCMK_ROLES:
        raise UnknownPcmkRoleError(str(resource.get("id")), target_role)
    return PcmkRoleType(target_role)


def _remove_clone_suffix(resource_id: str) -> tuple[str, Optional[str]]:
    if ":" in resource_id:
        resource_id, clone_suffix = resource_id.rsplit(":", 1)
        return resource_id, clone_suffix
    return resource_id, None


def _replica_to_dto(
    replica_el: _Element,
    bundle_id: str,
    bundle_type: str,
    remove_instance_suffix: bool = False,
) -> BundleReplicaStatusDto:
    replica_id = str(replica_el.attrib["id"])

    resource_list = [
        _primitive_to_dto(resource, remove_instance_suffix)
        for resource in replica_el.iterfind(_PRIMITIVE_TAG)
    ]

    duplicate_ids = [
        id
        for id, count in Counter(
            resource.resource_id for resource in resource_list
        ).items()
        if count > 1
    ]

    if duplicate_ids:
        raise BundleSameIdAsImplicitResourceError(bundle_id, duplicate_ids)

    # TODO pacemaker will probably add prefix
    # "pcmk-internal" to all implicit resources

    container_resource = _pop_implicit_resource(
        resource_list,
        f"{bundle_id}-{bundle_type}-{replica_id}",
        True,
        f"ocf:heartbeat:{bundle_type}",
    )

    if container_resource is None:
        raise BundleReplicaMissingImplicitResourceError(
            bundle_id, replica_id, "container"
        )

    remote_resource = _pop_implicit_resource(
        resource_list, f"{bundle_id}-{replica_id}", True, "ocf:pacemaker:remote"
    )

    # implicit ip address resource might be present
    ip_resource = None
    if (remote_resource is not None and len(resource_list) == 2) or (
        remote_resource is None and len(resource_list) == 1
    ):
        ip_resource = _pop_implicit_resource(
            resource_list, f"{bundle_id}-ip-", False, "ocf:heartbeat:IPaddr2"
        )

    if remote_resource is None and resource_list:
        raise BundleReplicaMissingImplicitResourceError(
            bundle_id, replica_id, "remote"
        )

    member = None
    if remote_resource:
        if len(resource_list) == 1:
            member = resource_list[0]
        else:
            raise BundleReplicaInvalidMemberCountError(bundle_id, replica_id)

    return BundleReplicaStatusDto(
        replica_id,
        member,
        remote_resource,
        container_resource,
        ip_resource,
    )


def _pop_implicit_resource(
    primitive_list: list[PrimitiveStatusDto],
    expected_id: str,
    exact_match: bool,
    resource_agent: str,
) -> Optional[PrimitiveStatusDto]:
    for primitive in primitive_list:
        matching_id = (
            exact_match
            and primitive.resource_id == expected_id
            or not exact_match
            and primitive.resource_id.startswith(expected_id)
        )

        if matching_id and primitive.resource_agent == resource_agent:
            primitive_list.remove(primitive)
            return primitive

    return None


def _replicas_valid(replica_list: Sequence[BundleReplicaStatusDto]) -> bool:
    if not replica_list:
        return True

    member = replica_list[0].member
    ip = replica_list[0].ip_address
    container = replica_list[0].container

    for replica in replica_list:
        if (
            not _cmp_replica_members(member, replica.member, True)
            or not _cmp_replica_members(ip, replica.ip_address, False)
            or not _cmp_replica_members(container, replica.container, False)
        ):
            return False
    return True


def _cmp_replica_members(
    left: Optional[PrimitiveStatusDto],
    right: Optional[PrimitiveStatusDto],
    compare_ids: bool,
) -> bool:
    if left is None and right is None:
        return True
    if left is None:
        return False
    if right is None:
        return False

    if left.resource_agent != right.resource_agent:
        return False

    return not compare_ids or left.resource_id == right.resource_id

from typing import (
    Optional,
    Sequence,
    Union,
    cast,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.const import (
    PCMK_ROLE_UNKNOWN,
    PCMK_ROLES,
    PCMK_STATUS_ROLE_UNKNOWN,
    PCMK_STATUS_ROLES,
    PcmkRoleType,
    PcmkStatusRoleType,
)
from pcs.common.reports import ReportProcessor
from pcs.common.status_dto import (
    AnyResourceStatusDto,
    BundleReplicaStatusDto,
    BundleStatusDto,
    CloneStatusDto,
    GroupStatusDto,
    PrimitiveStatusDto,
    ResourcesStatusDto,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import is_true

_PRIMITIVE_TAG = "resource"
_GROUP_TAG = "group"
_CLONE_TAG = "clone"
_BUNDLE_TAG = "bundle"
_REPLICA_TAG = "replica"


def _primitive_to_dto(
    reporter: ReportProcessor,
    primitive_el: _Element,
    remove_clone_suffix: bool = False,
) -> PrimitiveStatusDto:
    resource_id = _get_resource_id(reporter, primitive_el)
    if remove_clone_suffix:
        resource_id = _remove_clone_suffix(resource_id)

    role = _get_role(reporter, primitive_el, resource_id)
    target_role = _get_target_role(reporter, primitive_el, resource_id)

    node_names = [
        str(node.get("name")) for node in primitive_el.iterfind("node")
    ]

    if node_names and any(not name for name in node_names):
        reporter.report(
            reports.ReportItem.error(
                reports.messages.ClusterStatusEmptyNodeName(resource_id)
            )
        )

    if reporter.has_errors:
        raise LibraryError()

    return PrimitiveStatusDto(
        resource_id,
        str(primitive_el.get("resource_agent")),
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
        [str(node.get("name")) for node in primitive_el.iterfind("node")],
        primitive_el.get("pending"),
        primitive_el.get("locked_to"),
    )


def _group_to_dto(
    reporter: ReportProcessor,
    group_el: _Element,
    remove_clone_suffix: bool = False,
) -> GroupStatusDto:
    # clone suffix is added even when the clone is non unique
    group_id = _remove_clone_suffix(_get_resource_id(reporter, group_el))
    members = []

    for member in group_el:
        if member.tag == _PRIMITIVE_TAG:
            members.append(
                _primitive_to_dto(reporter, member, remove_clone_suffix)
            )
        else:
            reporter.report(
                reports.ReportItem.error(
                    reports.messages.ClusterStatusUnexpectedMember(
                        group_id, "group", str(member.get("id")), ["primitive"]
                    )
                )
            )

    if reporter.has_errors:
        raise LibraryError()

    return GroupStatusDto(
        group_id,
        is_true(group_el.get("maintenance", "false")),
        group_el.get("description"),
        is_true(group_el.get("managed", "false")),
        is_true(group_el.get("disabled", "false")),
        members,
    )


def _clone_to_dto(
    reporter: ReportProcessor,
    clone_el: _Element,
    _remove_clone_suffix: bool = False,
) -> CloneStatusDto:
    clone_id = _get_resource_id(reporter, clone_el)
    is_unique = is_true(clone_el.get("unique", "false"))

    target_role = _get_target_role(reporter, clone_el, clone_id)

    primitives = []
    groups = []

    for member in clone_el:
        if member.tag == _PRIMITIVE_TAG:
            primitives.append(_primitive_to_dto(reporter, member, is_unique))
        elif member.tag == _GROUP_TAG:
            groups.append(_group_to_dto(reporter, member, is_unique))
        else:
            reporter.report(
                reports.ReportItem.error(
                    reports.messages.ClusterStatusUnexpectedMember(
                        clone_id,
                        "clone",
                        str(member.get("id")),
                        ["primitive", "group"],
                    )
                )
            )

    reporter.report_list(
        _validate_mixed_instance_types(primitives, groups, clone_id)
    )

    instances: Union[list[PrimitiveStatusDto], list[GroupStatusDto]]
    if primitives:
        reporter.report_list(
            _validate_primitive_instance_ids(primitives, clone_id)
        )
        instances = primitives
    else:
        reporter.report_list(_validate_group_instance_ids(groups, clone_id))
        instances = groups

    if reporter.has_errors:
        raise LibraryError()

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
        instances,
    )


def _bundle_to_dto(
    reporter: ReportProcessor,
    bundle_el: _Element,
    _remove_clone_suffix: bool = False,
) -> Optional[BundleStatusDto]:
    bundle_id = _get_resource_id(reporter, bundle_el)
    bundle_type = str(bundle_el.get("type"))

    replicas = []
    for replica in bundle_el.iterfind(_REPLICA_TAG):
        replica_dto = _replica_to_dto(reporter, replica, bundle_id, bundle_type)
        if replica_dto is None:
            # skip this bundle in status
            return None
        replicas.append(replica_dto)

    reporter.report_list(_validate_replicas(replicas, bundle_id))

    if reporter.has_errors:
        raise LibraryError()

    return BundleStatusDto(
        bundle_id,
        bundle_type,
        str(bundle_el.get("image")),
        is_true(bundle_el.get("unique", "false")),
        is_true(bundle_el.get("maintenance", "false")),
        bundle_el.get("description"),
        is_true(bundle_el.get("managed", "false")),
        is_true(bundle_el.get("failed", "false")),
        replicas,
    )


_TAG_TO_FUNCTION = {
    _PRIMITIVE_TAG: _primitive_to_dto,
    _GROUP_TAG: _group_to_dto,
    _CLONE_TAG: _clone_to_dto,
    _BUNDLE_TAG: _bundle_to_dto,
}


def status_xml_to_dto(
    reporter: ReportProcessor, status: _Element
) -> ResourcesStatusDto:
    """
    Return dto containing status of configured resources in the cluster

    reporter -- ReportProcessor
    status -- status xml document from crm_mon, validated using
        the appropriate rng schema
    """
    resources = cast(list[_Element], status.xpath("resources/*"))

    resource_dtos = [
        _TAG_TO_FUNCTION[resource.tag](reporter, resource)
        for resource in resources
        if resource.tag in _TAG_TO_FUNCTION
    ]

    if reporter.has_errors:
        raise LibraryError()

    return ResourcesStatusDto(
        cast(
            list[AnyResourceStatusDto],
            [dto for dto in resource_dtos if dto is not None],
        )
    )


def _get_resource_id(reporter: ReportProcessor, resource: _Element) -> str:
    resource_id = resource.get("id")
    if not resource_id:
        reporter.report(
            reports.ReportItem.error(
                reports.messages.InvalidIdIsEmpty("resource id")
            )
        )
    return str(resource_id)


def _get_role(
    reporter: ReportProcessor, resource: _Element, resource_id: str
) -> PcmkStatusRoleType:
    role = resource.get("role")
    if role is None or role not in PCMK_STATUS_ROLES:
        reporter.report(
            reports.ReportItem.warning(
                reports.messages.ClusterStatusUnknownPcmkRole(role, resource_id)
            )
        )
        return PCMK_STATUS_ROLE_UNKNOWN
    return PcmkStatusRoleType(role)


def _get_target_role(
    reporter: ReportProcessor, resource: _Element, resource_id: str
) -> Optional[PcmkRoleType]:
    target_role = resource.get("target_role")
    if target_role is None:
        return None
    if target_role not in PCMK_ROLES:
        reporter.report(
            reports.ReportItem.warning(
                reports.messages.ClusterStatusUnknownPcmkRole(
                    target_role, resource_id
                )
            )
        )
        return PCMK_ROLE_UNKNOWN
    return PcmkRoleType(target_role)


def _remove_clone_suffix(resource_id: str) -> str:
    if ":" in resource_id:
        return resource_id.rsplit(":", 1)[0]
    return resource_id


def _validate_mixed_instance_types(
    primitives: list[PrimitiveStatusDto],
    groups: list[GroupStatusDto],
    clone_id: str,
) -> reports.ReportItemList:
    if primitives and groups:
        return [
            reports.ReportItem.error(
                reports.messages.ClusterStatusCloneMixedMembers(clone_id)
            )
        ]
    return []


def _validate_primitive_instance_ids(
    instances: list[PrimitiveStatusDto], clone_id: str
) -> reports.ReportItemList:
    if len(set(res.resource_id for res in instances)) > 1:
        return [
            reports.ReportItem.error(
                reports.messages.ClusterStatusCloneMembersDifferentIds(clone_id)
            )
        ]
    return []


def _validate_group_instance_ids(
    instances: list[GroupStatusDto], clone_id: str
) -> reports.ReportItemList:
    group_ids = set(group.resource_id for group in instances)
    children_ids = set(
        tuple(child.resource_id for child in group.members)
        for group in instances
    )

    if len(group_ids) > 1 or len(children_ids) > 1:
        return [
            reports.ReportItem.error(
                reports.messages.ClusterStatusCloneMembersDifferentIds(clone_id)
            )
        ]
    return []


def _replica_to_dto(
    reporter: ReportProcessor,
    replica_el: _Element,
    bundle_id: str,
    bundle_type: str,
) -> Optional[BundleReplicaStatusDto]:
    replica_id = str(replica_el.get("id"))

    resources = [
        _primitive_to_dto(reporter, resource)
        for resource in replica_el.iterfind(_PRIMITIVE_TAG)
    ]

    duplicate_ids = _find_duplicate_ids(resources)
    if duplicate_ids:
        reporter.report(
            reports.ReportItem.warning(
                reports.messages.ClusterStatusBundleMemberIdAsImplicit(
                    bundle_id, duplicate_ids
                )
            )
        )
        return None

    # TODO pacemaker will probably add prefix
    # "pcmk-internal" to all implicit resources

    container_resource = _get_implicit_resource(
        resources,
        f"{bundle_id}-{bundle_type}-{replica_id}",
        True,
        f"ocf:heartbeat:{bundle_type}",
    )

    if container_resource is None:
        reporter.report(
            reports.ReportItem.error(
                reports.messages.ClusterStatusBundleReplicaNoContainer(
                    bundle_id, replica_id
                )
            )
        )
        raise LibraryError()

    remote_resource = _get_implicit_resource(
        resources, f"{bundle_id}-{replica_id}", True, "ocf:pacemaker:remote"
    )

    # implicit ip address resource might be present
    ip_resource = None
    if (remote_resource is not None and len(resources) == 2) or (
        remote_resource is None and len(resources) == 1
    ):
        ip_resource = _get_implicit_resource(
            resources, f"{bundle_id}-ip-", False, "ocf:heartbeat:IPaddr2"
        )

    if remote_resource is None and resources:
        reporter.report(
            reports.ReportItem.error(
                reports.messages.ClusterStatusBundleReplicaMissingRemote(
                    bundle_id, replica_id
                )
            )
        )
        raise LibraryError()

    member = None
    if remote_resource:
        if len(resources) == 1:
            member = resources[0]
        else:
            reporter.report(
                reports.ReportItem.error(
                    reports.messages.ClusterStatusBundleReplicaInvalidCount(
                        bundle_id, replica_id
                    )
                )
            )
            raise LibraryError()

    return BundleReplicaStatusDto(
        replica_id,
        member,
        remote_resource,
        container_resource,
        ip_resource,
    )


def _find_duplicate_ids(resources: Sequence[AnyResourceStatusDto]) -> list[str]:
    seen = set()
    duplicates = []
    for resource in resources:
        if resource.resource_id in seen:
            duplicates.append(resource.resource_id)
        else:
            seen.add(resource.resource_id)
    return duplicates


def _get_implicit_resource(
    primitives: list[PrimitiveStatusDto],
    expected_id: str,
    exact_match: bool,
    resource_agent: str,
) -> Optional[PrimitiveStatusDto]:
    for primitive in primitives:
        matching_id = (
            exact_match
            and primitive.resource_id == expected_id
            or not exact_match
            and primitive.resource_id.startswith(expected_id)
        )

        if matching_id and primitive.resource_agent == resource_agent:
            primitives.remove(primitive)
            return primitive

    return None


def _validate_replicas(
    replicas: Sequence[BundleReplicaStatusDto], bundle_id: str
) -> reports.ReportItemList:
    if not replicas:
        return []

    member = replicas[0].member
    ip = replicas[0].ip_address
    container = replicas[0].container

    for replica in replicas:
        if (
            not _cmp_replica_members(member, replica.member, True)
            or not _cmp_replica_members(ip, replica.ip_address, False)
            or not _cmp_replica_members(container, replica.container, False)
        ):
            return [
                reports.ReportItem.error(
                    reports.messages.ClusterStatusBundleDifferentReplicas(
                        bundle_id
                    )
                )
            ]
    return []


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

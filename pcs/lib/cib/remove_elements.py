from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from typing import (
    Iterable,
    Mapping,
    Sequence,
    cast,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.resource_status import (
    MoreChildrenQuantifierType,
    ResourcesStatusFacade,
    ResourceState,
)
from pcs.common.types import (
    StringCollection,
    StringSequence,
)
from pcs.lib.cib import const
from pcs.lib.cib.constraint.common import (
    is_constraint,
    is_set_constraint,
)
from pcs.lib.cib.constraint.location import (
    is_location_constraint,
    is_location_rule,
)
from pcs.lib.cib.fencing_topology import (
    find_levels_with_device,
    has_any_devices,
    remove_device_from_level,
)
from pcs.lib.cib.resource.clone import is_any_clone
from pcs.lib.cib.resource.common import (
    disable,
    get_inner_resources,
    is_resource,
)
from pcs.lib.cib.resource.group import is_group
from pcs.lib.cib.resource.guest_node import (
    get_node_name_from_resource as get_node_name_from_guest,
)
from pcs.lib.cib.resource.guest_node import is_guest_node
from pcs.lib.cib.resource.remote_node import (
    get_node_name_from_resource as get_node_name_from_remote,
)
from pcs.lib.cib.tag import is_tag
from pcs.lib.cib.tools import (
    ElementNotFound,
    IdProvider,
    find_elements_referencing_id,
    find_location_constraints_referencing_node_name,
    get_element_by_id,
    get_elements_by_ids,
    get_fencing_topology,
    remove_element_by_id,
    remove_one_element,
)
from pcs.lib.pacemaker.live import parse_cib_xml
from pcs.lib.pacemaker.state import (
    ensure_resource_state,
    is_resource_managed,
)
from pcs.lib.pacemaker.status import (
    ClusterStatusParser,
    ClusterStatusParsingError,
    cluster_status_parsing_error_to_report,
)
from pcs.lib.xml_tools import get_root


@dataclass(frozen=True)
class DependantElements:
    id_tag_map: dict[str, str]

    def to_reports(self) -> reports.ReportItemList:
        if not self.id_tag_map:
            return []

        return [
            reports.ReportItem.info(
                reports.messages.CibRemoveDependantElements(self.id_tag_map)
            )
        ]


@dataclass(frozen=True)
class ElementReferences:
    reference_map: dict[str, set[str]]
    id_tag_map: dict[str, str]

    def to_reports(self) -> reports.ReportItemList:
        if not self.reference_map:
            return []

        return [
            reports.ReportItem.info(
                reports.messages.CibRemoveReferences(
                    self.id_tag_map, self.reference_map
                )
            )
        ]


@dataclass(frozen=True)
class UnsupportedElements:
    id_tag_map: Mapping[str, str]
    supported_element_types: StringCollection


class ElementsToRemove:
    """
    Find ids of all elements that should be removed. This function is aware
    of relations and references between elements and will also return ids of
    elements that are somehow referencing elements with specified ids.

    cib -- the whole cib
    ids -- ids of configuration elements to remove
    """

    def __init__(self, cib: _Element, ids: StringCollection):
        wip_cib = parse_cib_xml(etree.tostring(cib).decode())

        initial_ids = set(ids)
        elements_to_process, missing_ids = get_elements_by_ids(
            wip_cib, initial_ids
        )

        supported_elements, unsupported_elements = _validate_element_types(
            elements_to_process
        )

        element_ids_to_remove, removing_references_from = (
            _get_dependencies_to_remove(supported_elements)
        )

        # We need to use ids of the elements, since we will work with cib, but
        # the the elements were instantiated using the wip_cib, which means we
        # cannot reuse the elements
        self._ids_to_remove = element_ids_to_remove
        self._dependant_element_ids = self._ids_to_remove - initial_ids
        self._missing_ids = set(missing_ids)
        self._unsupported_ids = {
            str(el.attrib["id"]) for el in unsupported_elements
        }

        all_ids = set(
            chain(
                self._ids_to_remove,
                self._unsupported_ids,
                *removing_references_from.values(),
            )
        )
        self._id_tag_map = {
            str(el.attrib["id"]): el.tag
            for el in get_elements_by_ids(cib, all_ids)[0]
        }
        self._element_references = removing_references_from
        self._resources_to_remove = [
            el
            for el in get_elements_by_ids(cib, sorted(element_ids_to_remove))[0]
            if is_resource(el)
        ]

    @property
    def ids_to_remove(self) -> set[str]:
        """
        Ids of ALL cib elements with id that should be removed, including all
        resource and dependant elements
        """
        return set(self._ids_to_remove)

    @property
    def resources_to_remove(self) -> list[_Element]:
        """
        List of cib resources that should be removed. Used for operations
        needed for resources before their deletion, e.g. disabling them.
        """
        return list(self._resources_to_remove)

    @property
    def dependant_elements(self) -> DependantElements:
        """
        Information about cib elements that are removed indirectly as
        dependencies of other removed cib elements
        """
        return DependantElements(
            {
                element_id: self._id_tag_map[element_id]
                for element_id in self._dependant_element_ids
            }
        )

    @property
    def element_references(self) -> ElementReferences:
        """
        Information about cib element references that need to be removed.
        These references does not have their own id and need special handling
        while removing, e.g. references to stonith devices in fencing-level
        elements, or obj-ref elements inside tag elements.
        """
        return ElementReferences(
            dict(self._element_references),
            {
                element_id: self._id_tag_map[element_id]
                for element_id in chain(
                    self._element_references,
                    *self._element_references.values(),
                )
            },
        )

    @property
    def missing_ids(self) -> set[str]:
        """
        Set of ids not present in the cib
        """
        return set(self._missing_ids)

    @property
    def unsupported_elements(self) -> UnsupportedElements:
        """
        Information about cib elements that cannot be removed using this
        mechanism
        """
        return UnsupportedElements(
            id_tag_map={
                element_id: self._id_tag_map[element_id]
                for element_id in self._unsupported_ids
            },
            # the list of tags should match the validations done in
            # _validate_element_types function
            supported_element_types=["constraint", "location rule", "resource"],
        )


def warn_resource_unmanaged(
    state: _Element, resource_ids: StringSequence
) -> reports.ReportItemList:
    """
    Warn about unmanaged resources

    state -- state of the cluster
    resource_ids -- ids of resources to be checked
    """
    report_list: reports.ReportItemList = []
    try:
        parser = ClusterStatusParser(state)
        try:
            status_dto = parser.status_xml_to_dto()
        except ClusterStatusParsingError as e:
            report_list.append(cluster_status_parsing_error_to_report(e))
            return report_list
        report_list.extend(parser.get_warnings())

        status = ResourcesStatusFacade.from_resources_status_dto(status_dto)
        report_list.extend(
            reports.ReportItem.warning(
                reports.messages.ResourceIsUnmanaged(resource_id)
            )
            for resource_id in resource_ids
            if status.is_state(
                resource_id,
                None,
                ResourceState.UNMANAGED,
            )
        )
    except NotImplementedError:
        # TODO remove when issue with bundles in status is fixed
        report_list.extend(
            reports.ReportItem.warning(
                reports.messages.ResourceIsUnmanaged(resource_id)
            )
            for resource_id in resource_ids
            if not is_resource_managed(state, resource_id)
        )

    return report_list


def stop_resources(
    cib: _Element, resource_elements: Sequence[_Element]
) -> None:
    """
    Stop all resources that are going to be removed.

    cib -- the whole cib
    resource_elements -- sequence of elements that should be stopped
    """
    provider = IdProvider(cib)
    for el in resource_elements:
        disable(el, provider)


def ensure_resources_stopped(
    state: _Element, resource_ids: StringSequence
) -> reports.ReportItemList:
    """
    Ensure that all resources that should be stopped are stopped.

    state -- state of the cluster
    elements -- elements planned to be removed
    """
    not_stopped_ids = []
    report_list: reports.ReportItemList = []
    try:
        parser = ClusterStatusParser(state)
        try:
            status_dto = parser.status_xml_to_dto()
        except ClusterStatusParsingError as e:
            report_list.append(cluster_status_parsing_error_to_report(e))
            return report_list
        report_list.extend(parser.get_warnings())

        status = ResourcesStatusFacade.from_resources_status_dto(status_dto)
        not_stopped_ids = [
            resource_id
            for resource_id in resource_ids
            if not status.is_state(
                resource_id,
                None,
                ResourceState.STOPPED,
                instances_quantifier=(
                    MoreChildrenQuantifierType.ALL
                    if status.can_have_multiple_instances(resource_id)
                    else None
                ),
            )
        ]
    except NotImplementedError:
        # TODO remove when issue with bundles in status is fixed
        not_stopped_ids = [
            resource_id
            for resource_id in resource_ids
            if ensure_resource_state(False, state, resource_id).severity.level
            == reports.item.ReportItemSeverity.ERROR
        ]

    if not_stopped_ids:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotStopResourcesBeforeDeleting(
                    not_stopped_ids
                ),
                force_code=reports.codes.FORCE,
            )
        )

    return report_list


def remove_specified_elements(
    cib: _Element, elements: ElementsToRemove
) -> None:
    """
    Remove all elements that need to be removed.

    state -- state of the cluster
    elements -- elements planned to be removed
    """
    for element_id in elements.ids_to_remove:
        remove_element_by_id(cib, element_id)

    element_references = elements.element_references
    for (
        referenced_id,
        referenced_in_ids,
    ) in element_references.reference_map.items():
        for element_id in referenced_in_ids:
            _remove_element_reference(
                cib,
                referenced_id,
                element_id,
                element_references.id_tag_map[element_id],
            )


def _validate_element_types(
    elements: Iterable[_Element],
) -> tuple[list[_Element], list[_Element]]:
    supported_elements = []
    unsupported_elements = []

    for el in elements:
        # valid elements should match the valid tags reported from
        # ElementsToRemove.unsupported_elements property
        if is_constraint(el) or is_location_rule(el) or is_resource(el):
            supported_elements.append(el)
        else:
            unsupported_elements.append(el)

    return supported_elements, unsupported_elements


_REFERENCE_TAG_XPATH_MAP = {
    const.TAG_RESOURCE_SET: f"./{const.TAG_RESOURCE_REF}[@id=$referenced_id]",
    const.TAG_TAG: f"./{const.TAG_OBJREF}[@id=$referenced_id]",
}


def _remove_element_reference(
    cib: _Element,
    element_id: str,
    referenced_in_id: str,
    referenced_in_tag: str,
) -> None:
    # If element has id, then it was already removed using its id and does not
    # need to be removed using this reference mapping. Therefore, we need to
    # only remove elements that do not have id here, such as obj_ref and
    # resource_ref.
    try:
        element = get_element_by_id(cib, referenced_in_id)
    except ElementNotFound:
        return

    if referenced_in_tag == const.TAG_FENCING_LEVEL:
        remove_device_from_level(element, element_id)
        return

    if referenced_in_tag not in _REFERENCE_TAG_XPATH_MAP:
        return
    for el in cast(
        list[_Element],
        element.xpath(
            _REFERENCE_TAG_XPATH_MAP[referenced_in_tag],
            referenced_id=element_id,
        ),
    ):
        remove_one_element(el)


def _get_dependencies_to_remove(
    elements: Iterable[_Element],
) -> tuple[set[str], dict[str, set[str]]]:
    """
    Get ids of all elements that need to be removed (including specified
    elements) together with specified elements based on their relations.
    Also return mapping for elements whose references are going to be
    deleted from their respective parent elements, without deleting the
    parent itself.

    WARNING: this is a destructive operation for elements and their etree.

    elements -- iterable of elements that are planned to be removed
    """
    elements_to_process = list(elements)
    element_ids_to_remove: set[str] = set()
    removing_references_from: dict[str, set[str]] = defaultdict(set)

    while elements_to_process:
        el = elements_to_process.pop(0)
        element_id = str(el.attrib["id"])

        # Elements with these tags are only used for referencing other elements.
        # The 'id' attribute in these does not represent the id of the element
        # itself, but the id of the element that they refer to.
        # Therefore, it does not make sense to try finding any references to
        # these elements.
        if el.tag not in (
            const.TAG_OBJREF,
            const.TAG_RESOURCE_REF,
            const.TAG_ROLE,
        ):
            if element_id in element_ids_to_remove:
                continue
            element_ids_to_remove.add(element_id)
            elements_to_process.extend(_get_element_references(el))
            elements_to_process.extend(_get_inner_references(el))
            elements_to_process.extend(
                _get_remote_node_name_constraint_references(el)
            )

            for level_el in find_levels_with_device(
                get_fencing_topology(get_root(el)), element_id
            ):
                removing_references_from[element_id].add(
                    str(level_el.attrib["id"])
                )
                remove_device_from_level(level_el, element_id)
                if not has_any_devices(level_el):
                    elements_to_process.append(level_el)

        parent_el = el.getparent()
        if parent_el is not None:
            # We only want to remove parent elements that are invalid when
            # empty. There may be ACLs set in pacemaker which allow "write" for
            # the child elements (adding, changing and removing) but not their
            # parent elements. In such case, removing the parent element would
            # cause the whole change to be rejected by pacemaker with a
            # "permission denied" message.
            # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
            if _is_empty_after_inner_el_removal(parent_el):
                elements_to_process.append(parent_el)
            parent_el.remove(el)

            parent_id = parent_el.get("id")
            if parent_id is not None:
                removing_references_from[element_id].add(parent_id)

    # Removing references from parent elements that are going to be removed
    # (they are present in the 'element_ids_to_remove') is unncesary, since all
    # of the child elements are removed when parent is removed. This means we
    # can filter out such references from the resulting mapping.
    for key in list(removing_references_from):
        removing_references_from[key].difference_update(element_ids_to_remove)
        if not removing_references_from[key]:
            del removing_references_from[key]

    return element_ids_to_remove, removing_references_from


def _get_element_references(element: _Element) -> Iterable[_Element]:
    """
    Return all CIB elements that are referencing specified element

    element -- references to this element will be
    """
    return find_elements_referencing_id(element, str(element.attrib["id"]))


def _get_inner_references(element: _Element) -> Iterable[_Element]:
    """
    Get all inner elements with attribute id, which means that they might be
    referenced in IDREF. Elements with attribute id and type IDREF are also
    returned.
    """
    # return cast(Iterable[_Element], element.xpath("./*[@id]"))
    if is_resource(element):
        try:
            # we are removing elements from the tree, therefore assertions of
            # this function can fail
            return get_inner_resources(element)
        except IndexError:
            return []
    # if element.tag == "alert":
    #     return element.findall("recipient")
    # if is_set_constraint(element):
    #     return element.findall("resource_set")
    # if element.tag == "acl_role":
    #     return element.findall("acl_permission")
    return []


def _is_last_element(parent_element: _Element, child_tag: str) -> bool:
    return len(parent_element.findall(f"./{child_tag}")) == 1


def _is_empty_after_inner_el_removal(  # noqa: PLR0911
    parent_el: _Element,
) -> bool:
    # pylint: disable=too-many-return-statements
    if is_any_clone(parent_el):
        return True
    if is_group(parent_el):
        return len(get_inner_resources(parent_el)) == 1
    if is_tag(parent_el):
        return _is_last_element(parent_el, const.TAG_OBJREF)
    if parent_el.tag == const.TAG_RESOURCE_SET:
        return _is_last_element(parent_el, const.TAG_RESOURCE_REF)
    if is_set_constraint(parent_el):
        return _is_last_element(parent_el, const.TAG_RESOURCE_SET)
    if is_location_constraint(parent_el):
        return _is_last_element(parent_el, const.TAG_RULE)
    return False


def _get_remote_node_name_constraint_references(
    element: _Element,
) -> Iterable[_Element]:
    """
    Return all location constraints referencing remote or guest node name.
    """
    if not is_resource(element):
        return []

    if is_guest_node(element):
        return find_location_constraints_referencing_node_name(
            element, get_node_name_from_guest(element)
        )

    remote_node_name = get_node_name_from_remote(element)
    if remote_node_name is not None:
        return find_location_constraints_referencing_node_name(
            element, remote_node_name
        )

    return []

from collections import defaultdict

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.resource import (
    clone,
    common,
    group,
    primitive,
)
from pcs.lib.cib.tools import ElementSearcher

class ValidateMoveResourcesToGroup():
    # Base class for validating moving resources to a group. It holds common
    # code and hides flags which should not be exposed to users of validating
    # classes.
    def __init__(self):
        self._group_element = None
        self._resource_element_list = []
        self._adjacent_resource_element = None

    def _validate_elements(
        self, bad_or_missing_group_specified=False,
        bad_resources_specified=False, bad_adjacent_specified=False
    ):
        return (
            self._validate_resource_elements(
                bad_or_missing_group_specified,
                bad_resources_specified,
                bad_adjacent_specified,
            )
            +
            self._validate_adjacent_resource_element()
        )

    def _validate_resource_elements(
        self, bad_or_missing_group_specified, bad_resources_specified,
        bad_adjacent_specified
    ):
        report_list = []

        # Check if the group element is really a group unless it has been
        # checked before.
        if (
            not bad_or_missing_group_specified
            and
            not group.is_group(self._group_element)
        ):
            bad_or_missing_group_specified = True
            report_list.append(
                ReportItem.error(
                    reports.messages.IdBelongsToUnexpectedType(
                        self._group_element.attrib.get("id"),
                        expected_types=[group.TAG],
                        current_type=self._group_element.tag,
                    )
                )
            )

        # Report an error if no resources were specified. If resource ids have
        # been specified but they are not valid resource ids, then some
        # resources were specified, even though not valid ones.
        if not bad_resources_specified and not self._resource_element_list:
            report_list.append(
                ReportItem.error(
                    reports.messages.CannotGroupResourceNoResources()
                )
            )

        resources_already_in_the_group = set()
        resources_count = defaultdict(int)
        for resource in self._resource_element_list:
            resource_id = resource.attrib.get("id")
            if not primitive.is_primitive(resource):
                report_list.append(
                    ReportItem.error(
                        reports.messages.CannotGroupResourceWrongType(
                            resource_id,
                            resource.tag
                        )
                    )
                )
                continue
            resources_count[resource_id] = resources_count[resource_id] + 1
            parent = resource.getparent()
            if parent is not None:
                if group.is_group(parent):
                    # If no adjacent resource has been specified (either valid
                    # or invalid), the resources must not already be in the
                    # group, if the group already exists.
                    if (
                        not bad_or_missing_group_specified
                        and
                        not bad_adjacent_specified
                        and
                        self._adjacent_resource_element is None
                        and
                        (
                            parent.attrib.get("id")
                            ==
                            self._group_element.attrib.get("id")
                        )
                    ):
                        resources_already_in_the_group.add(resource_id)
                elif parent.tag != "resources":
                    # If the primitive is not in a 'group' or 'resources' tag,
                    # it is either in a clone, master, bundle or similar tag
                    # and cannot be put into a group.
                    report_list.append(
                        ReportItem.error(
                            reports.messages.CannotGroupResourceWrongType(
                                resource_id,
                                parent.tag
                            )
                        )
                    )
        if resources_already_in_the_group:
            report_list.append(
                ReportItem.error(
                    reports.messages.CannotGroupResourceAlreadyInTheGroup(
                        sorted(resources_already_in_the_group),
                        self._group_element.attrib.get("id")
                    )
                )
            )
        more_than_once_resources = [
            resource for resource, count in resources_count.items()
            if count > 1
        ]
        if more_than_once_resources:
            report_list.append(
                ReportItem.error(
                    reports.messages.CannotGroupResourceMoreThanOnce(
                        sorted(more_than_once_resources)
                    )
                )
            )
        return report_list

    def _validate_adjacent_resource_element(self):
        report_list = []
        if self._adjacent_resource_element is not None:
            if self._group_element is not None:
                adjacent_parent = self._adjacent_resource_element.getparent()
                if not (
                    adjacent_parent is not None
                    and
                    group.is_group(adjacent_parent)
                    and
                    (
                        adjacent_parent.attrib.get("id")
                        ==
                        self._group_element.attrib.get("id")
                    )
                ):
                    report_list.append(
                        ReportItem.error(
                            reports.messages
                            .CannotGroupResourceAdjacentResourceNotInGroup(
                                self._adjacent_resource_element
                                    .attrib.get("id"),
                                self._group_element.attrib.get("id")
                            )
                        )
                    )
            for resource in self._resource_element_list:
                if (
                    self._adjacent_resource_element.attrib.get("id")
                    ==
                    resource.attrib.get("id")
                ):
                    report_list.append(
                        ReportItem.error(
                            reports.messages.CannotGroupResourceNextToItself(
                                self._adjacent_resource_element.attrib.get("id")
                            )
                        )
                    )
                    break
        return report_list

class ValidateMoveResourcesToGroupByElements(ValidateMoveResourcesToGroup):
    """
    Validate putting resources into a group or moving them within their group
    """
    def __init__(
        self, group_element, resource_element_list,
        adjacent_resource_element=None
    ):
        """
        etree.Element group_element -- the group to put resources into
        iterable resource_element_list -- resources to put into the group
        etree.Element adjacent_resource_element -- put resources beside this one
        """
        super().__init__()
        self._group_element = group_element
        self._resource_element_list = resource_element_list
        self._adjacent_resource_element = adjacent_resource_element

    def validate(self):
        """
        Run the validation and return a report item list
        """
        return self._validate_elements()

class ValidateMoveResourcesToGroupByIds(ValidateMoveResourcesToGroup):
    """
    Validate putting resources into a group or moving them within their group
    """
    def __init__(
        self, group_id, resource_id_list, adjacent_resource_id=None
    ):
        """
        string group_id -- id of the group to put resources into
        iterable resource_id_list -- ids of resources to put into the group
        string adjacent_resource_id -- put resources beside this one
        """
        super().__init__()
        self._group_id = group_id
        self._resource_id_list = resource_id_list
        self._adjacent_resource_id = adjacent_resource_id

    def validate(self, resources_section, id_provider):
        """
        Run the validation and return a report item list

        etree.Element resources_section -- resources section of a cib
        IdProvider id_provider -- elements' ids generator and uniqueness checker
        """
        report_list = []

        # Check that group_id either matches an existing group element or is
        # not occupied by any other element.
        group_missing_id_valid = False
        group_searcher = ElementSearcher(
            group.TAG, self._group_id, resources_section
        )
        if group_searcher.element_found():
            self._group_element = group_searcher.get_element()
        elif group_searcher.validate_book_id(
            id_provider, id_description="group name"
        ):
            group_missing_id_valid = True
        else:
            report_list.extend(group_searcher.get_errors())

        # Get resource elements to move to the group.
        # Get all types of resources, so that validation can later tell for
        # example: 'C' is a clone, clones cannot be put into a group. If we
        # only searched for primitives here, we would get 'C' is not a
        # resource, which is not that informative.
        self._resource_element_list = common.find_resources_and_report(
            resources_section, self._resource_id_list, report_list
        )

        # Get an adjacent resource element.
        if self._adjacent_resource_id is not None:
            # If the group already exists, check the adjacent resource is in it.
            if self._group_element is not None:
                adjacent_searcher = ElementSearcher(
                    primitive.TAG,
                    self._adjacent_resource_id,
                    self._group_element,
                )
                if adjacent_searcher.element_found():
                    self._adjacent_resource_element = (
                        adjacent_searcher.get_element()
                    )
                else:
                    report_list.append(
                        ReportItem.error(
                            reports.messages
                            .CannotGroupResourceAdjacentResourceNotInGroup(
                                self._adjacent_resource_id,
                                self._group_id,
                            )
                        )
                    )
            # The group will be created so there is no adjacent resource in it.
            elif group_missing_id_valid:
                report_list.append(
                    ReportItem.error(
                        reports.messages
                        .CannotGroupResourceAdjacentResourceForNewGroup(
                            self._adjacent_resource_id,
                            self._group_id,
                        )
                    )
                )
            # else: The group_id belongs to a non-group element, checking the
            # adjacent_reource is pointless.

        report_list.extend(
            self._validate_elements(
                bad_or_missing_group_specified=(
                    self._group_element is None
                ),
                bad_resources_specified=(
                    self._resource_id_list
                    and
                    not self._resource_element_list
                ),
                bad_adjacent_specified=(
                    self._adjacent_resource_id
                    and
                    self._adjacent_resource_element is None
                )
            )
        )

        return report_list

    def group_element(self):
        return self._group_element

    def resource_element_list(self):
        return self._resource_element_list

    def adjacent_resource_element(self):
        return self._adjacent_resource_element


def move_resources_to_group(
    group_element, primitives_to_place, adjacent_resource=None,
    put_after_adjacent=True
):
    """
    Put resources into a group or move them within their group

    etree.Element group_element -- the group to put resources into
    iterable primitives_to_place -- resource elements to put into the group
    etree.Element adjacent_resource -- put resources beside this one if set
    bool put_after_adjacent -- put resources after or before the adjacent one
    """
    for resource in primitives_to_place:
        old_parent = resource.getparent()

        # Move a resource to the group.
        if (
            adjacent_resource is not None
            and
            adjacent_resource.getnext() is not None
            and
            put_after_adjacent
        ):
            adjacent_resource.getnext().addprevious(resource)
            adjacent_resource = resource
        elif (
            adjacent_resource is not None
            and
            not put_after_adjacent
        ):
            adjacent_resource.addprevious(resource)
        else:
            group_element.append(resource)
            adjacent_resource = resource

        # If the resource was the last resource in another group, that group is
        # now empty and must be deleted. If the group is in a clone element,
        # delete that as well.
        if (
            old_parent is not None
            and
            group.is_group(old_parent)
            and
            not group.get_inner_resources(old_parent)
            and
            old_parent.getparent() is not None
        ):
            old_grandparent = old_parent.getparent()
            if (
                clone.is_any_clone(old_grandparent)
                and
                old_grandparent.getparent() is not None
            ):
                old_grandparent.getparent().remove(old_grandparent)
            else:
                old_grandparent.remove(old_parent)

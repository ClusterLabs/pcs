import abc
from typing import Iterable, Mapping, Sequence, TypedDict

from lxml.etree import SubElement, _Element

from pcs.common import reports
from pcs.common.types import StringSequence
from pcs.lib.cib.const import (
    TAG_LIST_CONSTRAINABLE,
    TAG_LIST_CONSTRAINT,
    TAG_LIST_RESOURCE_MULTIINSTANCE,
    TAG_RESOURCE_SET,
)
from pcs.lib.cib.constraint import resource_set
from pcs.lib.cib.tools import IdProvider, Version
from pcs.lib.pacemaker.values import sanitize_id
from pcs.lib.validate import TypeOptionMap
from pcs.lib.xml_tools import find_parent


# structure of a parameter of a command for creating set constraints
class CmdInputResourceSet(TypedDict):
    ids: StringSequence
    options: Mapping[str, str]


# structure of a parameter of a command for creating set constraints
CmdInputResourceSetList = Sequence[CmdInputResourceSet]


# structure of a parameter of a command for creating set constraints prepared
# for further validation and processing
class CmdInputResourceSetLoaded(TypedDict):
    constrained_elements: Sequence[_Element]
    options: TypeOptionMap


# structure of a parameter of a command for creating set constraints prepared
# for further validation and processing
CmdInputResourceSetLoadedList = list[CmdInputResourceSetLoaded]


def is_constraint(element: _Element) -> bool:
    return element.tag in TAG_LIST_CONSTRAINT


def is_set_constraint(element: _Element) -> bool:
    return (
        is_constraint(element)
        and element.find(f"./{TAG_RESOURCE_SET}") is not None
    )


def find_constraints_of_same_type(
    constraint_section: _Element,
    constraint_to_check: _Element,
) -> Iterable[_Element]:
    """
    Find constraints of the same type and setness as a specified constraint

    constraint_section -- where to look for constraints
    constraint_to_check -- defines a type and a setness to look for
    """
    looking_for_set_constraint = is_set_constraint(constraint_to_check)
    return (
        element
        for element in constraint_section.iterfind(constraint_to_check.tag)
        if element is not constraint_to_check
        and is_set_constraint(element) == looking_for_set_constraint
    )


def _create_set_constraint_id(
    id_provider: IdProvider, prefix: str, rsc_set_list: CmdInputResourceSetList
) -> str:
    # Create a semi-random id. We need it to be predictable (for testing), short
    # and somehow different than other ids so that we don't spend much time in
    # finding a unique id
    # Avoid using actual resource names. It makes the id very long (consider 10
    # or more resources in a set constraint). Also, if a resource is deleted
    # and therefore removed from the constraint, the id no longer matches the
    # constraint.
    resource_ids: list[str] = []
    for rsc_set in rsc_set_list:
        resource_ids += rsc_set["ids"]
    id_part = "".join([_id[0] + _id[-1] for _id in resource_ids][:3])
    return id_provider.allocate_id(sanitize_id(f"{prefix}_set_{id_part}"))


def create_constraint_with_set(
    parent_element: _Element,
    id_provider: IdProvider,
    cib_schema_version: Version,
    constraint_tag: str,
    id_prefix: str,
    rsc_set_list: CmdInputResourceSetList,
    options: Mapping[str, str],
) -> _Element:
    """
    Create a constraint with resource sets

    parent_element -- where to place the constraint
    id_provider -- elements' ids generator
    cib_schema_version -- current CIB schema version
    constraint_tag -- constraint xml tag
    id_prefix -- constraint id prefix
    rsc_set_list -- definition of resource sets: resources and set options
    options -- additional options for the constraint
    """
    constraint_el = SubElement(parent_element, constraint_tag)

    if "id" not in options:
        constraint_el.attrib["id"] = _create_set_constraint_id(
            id_provider, id_prefix, rsc_set_list
        )

    for name, value in options.items():
        if value != "":
            constraint_el.attrib[name] = value

    for rsc_set in rsc_set_list:
        resource_set.create(
            constraint_el,
            id_provider,
            cib_schema_version,
            rsc_set["ids"],
            rsc_set["options"],
        )

    return constraint_el


class DuplicatesChecker:
    """
    Base class for finding duplicate constraints

    To use it, create a subclass and implement _are_duplicate method to compare
    constraints of a specific type
    """

    def __init__(self) -> None:
        pass

    def check(
        self,
        constraint_section: _Element,
        constraint_to_check: _Element,
        force_flags: reports.types.ForceFlags = (),
    ) -> reports.ReportItemList:
        """
        Check if a constraint is a duplicate of an already existing constraint

        constraint_section -- where to look for existing constraints
        constraint_to_check -- search for duplicates of this constraint
        force_flags -- list of flags codes
        """
        self._check_init(constraint_to_check)
        report_list: reports.ReportItemList = []
        duplication_allowed = reports.codes.FORCE in force_flags

        duplicate_constraint_list = [
            constraint_el
            for constraint_el in find_constraints_of_same_type(
                constraint_section, constraint_to_check
            )
            if self._are_duplicate(constraint_to_check, constraint_el)
        ]

        if duplicate_constraint_list:
            report_list.append(
                reports.ReportItem(
                    severity=reports.item.get_severity(
                        reports.codes.FORCE, duplication_allowed
                    ),
                    message=reports.messages.DuplicateConstraintsExist(
                        [
                            str(duplicate_el.attrib["id"])
                            for duplicate_el in duplicate_constraint_list
                        ]
                    ),
                ),
            )

        return report_list

    def _check_init(self, constraint_to_check: _Element) -> None:
        """
        For descendants to do their initialization for each check
        """

    @abc.abstractmethod
    def _are_duplicate(
        self,
        constraint_to_check: _Element,
        constraint_el: _Element,
    ) -> bool:
        """
        Compare two constraints and decide if they are duplicate to each other

        constraint_to_check -- search for duplicates of this constraint
        constraint_el -- an already existing constraint
        """
        raise NotImplementedError()


class DuplicatesCheckerSetConstraint(DuplicatesChecker):
    _constraint_id_set_list: list[list[str]]

    @staticmethod
    def _get_id_set_list(constraint_el: _Element) -> list[list[str]]:
        return [
            resource_set.get_resource_id_set_list(resource_set_item)
            for resource_set_item in constraint_el.findall(
                f".//{resource_set.TAG_RESOURCE_SET}"
            )
        ]

    def _check_init(self, constraint_to_check: _Element) -> None:
        self._constraint_id_set_list = self._get_id_set_list(
            constraint_to_check
        )

    def _are_duplicate(
        self,
        constraint_to_check: _Element,
        constraint_el: _Element,
    ) -> bool:
        del constraint_to_check
        return (
            self._get_id_set_list(constraint_el) == self._constraint_id_set_list
        )


def validate_constrainable_elements(
    element_list: Iterable[_Element], in_multiinstance_allowed: bool = False
) -> reports.ReportItemList:
    """
    Validate that a constraint can be created for each of the specified elements

    element_list -- the elements to be validated
    in_multiinstance_allowed -- allow constraints for resources in clones/bundles
    """
    report_list: reports.ReportItemList = []

    for element in element_list:
        if element.tag not in TAG_LIST_CONSTRAINABLE:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.IdBelongsToUnexpectedType(
                        str(element.attrib["id"]),
                        sorted(TAG_LIST_CONSTRAINABLE),
                        element.tag,
                    )
                )
            )
            continue

        if element.tag not in TAG_LIST_RESOURCE_MULTIINSTANCE:
            multiinstance_parent = find_parent(
                element, TAG_LIST_RESOURCE_MULTIINSTANCE
            )
            if multiinstance_parent is not None:
                report_list.append(
                    reports.ReportItem(
                        reports.item.get_severity(
                            reports.codes.FORCE, in_multiinstance_allowed
                        ),
                        reports.messages.ResourceForConstraintIsMultiinstance(
                            str(element.attrib["id"]),
                            multiinstance_parent.tag,
                            str(multiinstance_parent.attrib["id"]),
                        ),
                    )
                )

    return report_list

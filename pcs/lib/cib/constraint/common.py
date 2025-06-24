import abc
from typing import Iterable

from lxml.etree import _Element

from pcs.common import reports
from pcs.lib.cib.const import (
    TAG_LIST_CONSTRAINABLE,
    TAG_LIST_CONSTRAINT,
    TAG_LIST_RESOURCE_MULTIINSTANCE,
    TAG_RESOURCE_SET,
)
from pcs.lib.xml_tools import find_parent


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

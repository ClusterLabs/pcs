from lxml import etree

from pcs.common import (
    const,
    pacemaker,
    reports,
)
from pcs.common.const import PcmkAction
from pcs.common.pacemaker.constraint import CibResourceSetDto
from pcs.common.pacemaker.types import (
    CibResourceSetOrdering,
    CibResourceSetOrderType,
)
from pcs.common.reports.item import ReportItem
from pcs.lib import validate
from pcs.lib.cib.resource import group
from pcs.lib.cib.resource.common import get_parent_resource
from pcs.lib.cib.tools import (
    are_new_role_names_supported,
    find_unique_id,
    get_elements_by_ids,
    role_constructor,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import is_true
from pcs.lib.tools import get_optional_value

_ATTRIBUTES = ("action", "require-all", "role", "sequential")


def prepare_set(
    find_valid_id, resource_set, report_processor: reports.ReportProcessor
):
    """return resource_set with corrected ids"""
    if report_processor.report_list(
        _validate_options(resource_set["options"])
    ).has_errors:
        raise LibraryError()
    return {
        "ids": [find_valid_id(id) for id in resource_set["ids"]],
        "options": resource_set["options"],
    }


def _validate_options(options) -> reports.ReportItemList:
    # Pacemaker does not care currently about meaningfulness for concrete
    # constraint, so we use all attribs.
    validators = [
        validate.NamesIn(_ATTRIBUTES, option_type="set"),
        validate.ValueIn("action", const.PCMK_ACTIONS),
        validate.ValuePcmkBoolean("require-all"),
        validate.ValueIn("role", const.PCMK_ROLES),
        validate.ValuePcmkBoolean("sequential"),
        validate.ValueDeprecated(
            "role",
            {
                const.PCMK_ROLE_PROMOTED_LEGACY: const.PCMK_ROLE_PROMOTED,
                const.PCMK_ROLE_UNPROMOTED_LEGACY: const.PCMK_ROLE_UNPROMOTED,
            },
            reports.ReportItemSeverity.deprecation(),
        ),
    ]
    return validate.ValidatorAll(validators).validate(options)


def create(parent, resource_set):
    """
    parent - lxml element for append new resource_set
    """
    element = etree.SubElement(parent, "resource_set")
    if "role" in resource_set["options"]:
        resource_set["options"]["role"] = pacemaker.role.get_value_for_cib(
            resource_set["options"]["role"],
            is_latest_supported=are_new_role_names_supported(parent),
        )
    element.attrib.update(resource_set["options"])
    element.attrib["id"] = find_unique_id(
        parent.getroottree(),
        "{0}_set".format(parent.attrib.get("id", "constraint_set")),
    )

    for _id in resource_set["ids"]:
        etree.SubElement(element, "resource_ref").attrib["id"] = _id

    return element


def get_resource_id_set_list(element):
    return [
        resource_ref_element.attrib["id"]
        for resource_ref_element in element.findall(".//resource_ref")
    ]


def is_resource_in_same_group(cib, resource_id_list):
    # We don't care about not found elements here, that is a job of another
    # validator. We do not care if the id doesn't belong to a resource either
    # for the same reason.
    element_list, _ = get_elements_by_ids(cib, set(resource_id_list))

    parent_list = []
    for element in element_list:
        parent = get_parent_resource(element)
        if parent is not None and group.is_group(parent):
            parent_list.append(parent)

    if len(set(parent_list)) != len(parent_list):
        raise LibraryError(
            ReportItem.error(
                reports.messages.CannotSetOrderConstraintsForResourcesInTheSameGroup()
            )
        )


def _resource_set_element_to_dto(
    resource_set_el: etree._Element,
) -> CibResourceSetDto:
    return CibResourceSetDto(
        set_id=resource_set_el.get("id", ""),
        sequential=get_optional_value(
            is_true, resource_set_el.get("sequential")
        ),
        require_all=get_optional_value(
            is_true, resource_set_el.get("require-all")
        ),
        ordering=get_optional_value(
            CibResourceSetOrdering, resource_set_el.get("ordering")
        ),
        action=get_optional_value(PcmkAction, resource_set_el.get("action")),
        role=get_optional_value(role_constructor, resource_set_el.get("role")),
        score=resource_set_el.get("score"),
        kind=get_optional_value(
            CibResourceSetOrderType, resource_set_el.get("kind")
        ),
        resources_ids=[
            str(rsc_ref.attrib["id"])
            for rsc_ref in resource_set_el.findall("./resource_ref")
        ],
    )


def constraint_element_to_resource_set_dto_list(
    constraint_el: etree._Element,
) -> list[CibResourceSetDto]:
    return [
        _resource_set_element_to_dto(set_el)
        for set_el in constraint_el.findall("./resource_set")
    ]

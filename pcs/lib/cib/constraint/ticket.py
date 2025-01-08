from functools import partial
from typing import Callable

from lxml.etree import (
    SubElement,
    _Element,
)

from pcs.common import (
    const,
    pacemaker,
    reports,
)
from pcs.common.pacemaker.constraint import (
    CibConstraintTicketAttributesDto,
    CibConstraintTicketDto,
    CibConstraintTicketSetDto,
)
from pcs.common.pacemaker.types import CibTicketLossPolicy
from pcs.common.reports.item import ReportItem
from pcs.lib import validate
from pcs.lib.booth.config_validators import validate_ticket_name
from pcs.lib.cib import tools
from pcs.lib.cib.const import TAG_CONSTRAINT_TICKET as TAG
from pcs.lib.cib.constraint import constraint
from pcs.lib.cib.constraint.common import is_set_constraint
from pcs.lib.cib.constraint.resource_set import (
    constraint_element_to_resource_set_dto_list,
)
from pcs.lib.cib.tools import role_constructor
from pcs.lib.errors import LibraryError
from pcs.lib.tools import get_optional_value
from pcs.lib.xml_tools import remove_when_pointless

_DESCRIPTION = "constraint id"
ATTRIB = {
    "loss-policy": ("fence", "stop", "freeze", "demote"),
    "ticket": None,
}
ATTRIB_PLAIN = {
    "rsc": None,
    "rsc-role": const.PCMK_ROLES,
}


def is_ticket_constraint(element: _Element) -> bool:
    return element.tag == TAG


def _validate_options_common(options):
    report_list = []
    if "loss-policy" in options:
        loss_policy = options["loss-policy"].lower()
        if options["loss-policy"] not in ATTRIB["loss-policy"]:
            report_list.append(
                ReportItem.error(
                    reports.messages.InvalidOptionValue(
                        "loss-policy",
                        options["loss-policy"],
                        ATTRIB["loss-policy"],
                    )
                )
            )
        options["loss-policy"] = loss_policy
    return report_list


def _create_id(cib, ticket, resource_id, resource_role):
    return tools.find_unique_id(
        cib,
        "-".join(("ticket", ticket, resource_id))
        + (f"-{resource_role}" if resource_role else ""),
    )


def prepare_options_with_set(cib, options, resource_set_list):
    options = constraint.prepare_options(
        tuple(ATTRIB.keys()),
        options,
        create_id_fn=partial(
            constraint.create_id, cib, "ticket", resource_set_list
        ),
        validate_id=partial(tools.check_new_id_applicable, cib, _DESCRIPTION),
    )
    report_list = _validate_options_common(options)
    if "ticket" not in options or not options["ticket"].strip():
        report_list.append(
            ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["ticket"])
            )
        )
    else:
        report_list.extend(validate_ticket_name(options["ticket"]))
    if report_list:
        raise LibraryError(*report_list)
    return options


def prepare_options_plain(
    cib: _Element,
    report_processor: reports.ReportProcessor,
    options,
    ticket: str,
    resource_id,
):
    options = options.copy()

    report_processor.report_list(_validate_options_common(options))

    if not ticket:
        report_processor.report(
            ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["ticket"])
            )
        )
    else:
        report_processor.report_list(validate_ticket_name(ticket))

    if not resource_id:
        report_processor.report(
            ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["rsc"])
            )
        )

    role_value_validator = validate.ValueIn(
        "rsc-role", const.PCMK_ROLES, option_name_for_report="role"
    )
    role_value_validator.empty_string_valid = True

    validators = [
        role_value_validator,
        validate.ValueDeprecated(
            "rsc-role",
            {
                const.PCMK_ROLE_PROMOTED_LEGACY: const.PCMK_ROLE_PROMOTED,
                const.PCMK_ROLE_UNPROMOTED_LEGACY: const.PCMK_ROLE_UNPROMOTED,
            },
            reports.ReportItemSeverity.deprecation(),
            option_name_for_report="role",
        ),
    ]
    report_processor.report_list(
        validate.ValidatorAll(validators).validate(
            validate.values_to_pairs(
                options,
                validate.option_value_normalization(
                    {"rsc-role": lambda value: value.capitalize()}
                ),
            )
        )
    )
    report_processor.report_list(
        validate.NamesIn(
            # rsc and rsc-ticket are passed as parameters not as items in the
            # options dict
            (set(ATTRIB) | set(ATTRIB_PLAIN) | {"id"}) - {"rsc", "ticket"}
        ).validate(options)
    )

    if report_processor.has_errors:
        raise LibraryError()

    options["ticket"] = ticket
    options["rsc"] = resource_id

    if "rsc-role" in options:
        if options["rsc-role"]:
            options["rsc-role"] = pacemaker.role.get_value_for_cib(
                options["rsc-role"].capitalize(),
                tools.are_new_role_names_supported(cib),
            )
        else:
            del options["rsc-role"]

    if "id" not in options:
        options["id"] = _create_id(
            cib,
            options["ticket"],
            resource_id,
            options.get("rsc-role", ""),
        )
    else:
        tools.check_new_id_applicable(cib, _DESCRIPTION, options["id"])
    return options


def create_plain(constraint_section, options):
    element = SubElement(constraint_section, TAG)
    element.attrib.update(options)
    return element


def remove_plain(constraint_section, ticket_key, resource_id):
    ticket_element_list = constraint_section.xpath(
        ".//rsc_ticket[@ticket=$ticket and @rsc=$resource]",
        ticket=ticket_key,
        resource=resource_id,
    )

    for ticket_element in ticket_element_list:
        ticket_element.getparent().remove(ticket_element)

    return len(ticket_element_list) > 0


def remove_with_resource_set(constraint_section, ticket_key, resource_id):
    ref_element_list = constraint_section.xpath(
        ".//rsc_ticket[@ticket=$ticket]/resource_set/resource_ref[@id=$resource]",
        ticket=ticket_key,
        resource=resource_id,
    )

    for ref_element in ref_element_list:
        set_element = ref_element.getparent()
        set_element.remove(ref_element)
        # set_element is lxml element, therefore we have to use len() here
        # pylint: disable=len-as-condition
        if not len(set_element):
            ticket_element = set_element.getparent()
            ticket_element.remove(set_element)
            # We do not care about attributes since without an attribute "rsc"
            # they are pointless. Attribute "rsc" is mutually exclusive with
            # resource_set (see rng) so it cannot be in this ticket_element.
            remove_when_pointless(ticket_element, attribs_important=False)

    return len(ref_element_list) > 0


def get_duplicit_checker_callback(
    new_roles_supported: bool,
) -> Callable[[_Element, _Element], bool]:
    def are_duplicate_plain(element: _Element, other_element: _Element) -> bool:
        def convert_role(_el):
            return pacemaker.role.get_value_for_cib(
                _el.attrib.get("rsc-role", ""), new_roles_supported
            )

        if convert_role(element) != convert_role(other_element):
            return False
        return all(
            element.attrib.get(name, "") == other_element.attrib.get(name, "")
            for name in ("ticket", "rsc")
        )

    return are_duplicate_plain


def are_duplicate_with_resource_set(element, other_element):
    return element.attrib["ticket"] == other_element.attrib[
        "ticket"
    ] and constraint.have_duplicate_resource_sets(element, other_element)


def _element_to_attributes_dto(
    element: _Element,
) -> CibConstraintTicketAttributesDto:
    return CibConstraintTicketAttributesDto(
        constraint_id=str(element.attrib["id"]),
        ticket=str(element.attrib["ticket"]),
        loss_policy=get_optional_value(
            CibTicketLossPolicy, element.get("loss-policy")
        ),
    )


def _constraint_el_to_dto(element: _Element) -> CibConstraintTicketDto:
    return CibConstraintTicketDto(
        resource_id=str(element.attrib["rsc"]),
        role=get_optional_value(role_constructor, element.get("rsc-role")),
        attributes=_element_to_attributes_dto(element),
    )


def _set_constraint_el_to_dto(element: _Element) -> CibConstraintTicketSetDto:
    return CibConstraintTicketSetDto(
        resource_sets=constraint_element_to_resource_set_dto_list(element),
        attributes=_element_to_attributes_dto(element),
    )


def get_all_as_dtos(
    constraints_el: _Element,
) -> tuple[list[CibConstraintTicketDto], list[CibConstraintTicketSetDto]]:
    plain_list: list[CibConstraintTicketDto] = []
    set_list: list[CibConstraintTicketSetDto] = []
    for constraint_el in constraints_el.findall(f"./{TAG}"):
        if is_set_constraint(constraint_el):
            set_list.append(_set_constraint_el_to_dto(constraint_el))
        else:
            plain_list.append(_constraint_el_to_dto(constraint_el))
    return plain_list, set_list

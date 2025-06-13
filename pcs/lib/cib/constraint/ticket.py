from functools import partial
from typing import Mapping, Optional

from lxml.etree import SubElement, _Element

from pcs.common import const, reports
from pcs.common.pacemaker.constraint import (
    CibConstraintTicketAttributesDto,
    CibConstraintTicketDto,
    CibConstraintTicketSetDto,
)
from pcs.common.pacemaker.role import (
    get_value_for_cib as get_role_value_for_cib,
)
from pcs.common.pacemaker.types import CibTicketLossPolicy
from pcs.lib import validate
from pcs.lib.booth.config_validators import validate_ticket_name
from pcs.lib.cib.const import TAG_CONSTRAINT_TICKET as TAG
from pcs.lib.cib.tools import (
    IdProvider,
    Version,
    check_new_id_applicable,
    role_constructor,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import sanitize_id
from pcs.lib.tools import get_optional_value
from pcs.lib.xml_tools import remove_when_pointless

from .common import (
    DuplicatesChecker,
    is_set_constraint,
    validate_constrainable_elements,
)
from .constraint import create_id, have_duplicate_resource_sets, prepare_options
from .resource_set import constraint_element_to_resource_set_dto_list

_LOSS_POLICY_VALUES = ("fence", "stop", "freeze", "demote")


def is_ticket_constraint(element: _Element) -> bool:
    return element.tag == TAG


def prepare_options_with_set(cib, options, resource_set_list):
    options = prepare_options(
        ("loss-policy", "ticket"),
        options,
        create_id_fn=partial(create_id, cib, "ticket", resource_set_list),
        validate_id=partial(check_new_id_applicable, cib, "constraint id"),
    )

    report_list = []
    if "loss-policy" in options:
        loss_policy = options["loss-policy"].lower()
        if options["loss-policy"] not in _LOSS_POLICY_VALUES:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.InvalidOptionValue(
                        "loss-policy",
                        options["loss-policy"],
                        _LOSS_POLICY_VALUES,
                    )
                )
            )
        options["loss-policy"] = loss_policy

    if "ticket" not in options or not options["ticket"].strip():
        report_list.append(
            reports.ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["ticket"])
            )
        )
    else:
        report_list.extend(validate_ticket_name(options["ticket"]))
    if report_list:
        raise LibraryError(*report_list)
    return options


def validate_create_plain(
    id_provider: IdProvider,
    ticket: str,
    constrained_el: Optional[_Element],
    options: validate.TypeOptionMap,
    in_multiinstance_allowed: bool,
) -> reports.ReportItemList:
    """
    Validator for creating new plain ticket constraint

    id_provider -- elements' ids generator
    ticket -- name of the ticket
    constrained_el -- an element to be constrained
    options -- additional options for the constraint
    in_multiinstance_allowed -- allow constraints for resources in clones/bundles
    """
    report_list: reports.ReportItemList = []

    # validate resource specification
    # caller is responsible for handling the 'resource not found' case
    if constrained_el is not None:
        report_list.extend(
            validate_constrainable_elements(
                [constrained_el], in_multiinstance_allowed
            )
        )

    # use a booth ticket validator for validate a ticket
    if not ticket:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["ticket"])
            )
        )
    else:
        report_list += validate_ticket_name(ticket)

    # validate options
    validators = [
        validate.NamesIn(
            # rsc and ticket are passed as parameters, not as items in the
            # options dict
            {"id", "loss-policy", "rsc-role"}
        ),
        # with id_provider it validates that the id is available as well
        validate.ValueId(
            "id",
            option_name_for_report="constraint id",
            id_provider=id_provider,
        ),
        validate.ValueIn(
            "rsc-role", const.PCMK_ROLES, option_name_for_report="role"
        ),
        validate.ValueIn("loss-policy", _LOSS_POLICY_VALUES),
    ]
    report_list.extend(validate.ValidatorAll(validators).validate(options))

    return report_list


def create_plain(
    parent_element: _Element,
    id_provider: IdProvider,
    cib_schema_version: Version,
    ticket: str,
    resource_id: str,
    options: Mapping[str, str],
) -> _Element:
    """
    Create a plain ticket constraint

    parent_element -- where to place the constraint
    id_provider -- elements' ids generator
    cib_schema_version -- current CIB schema version
    ticket -- name of the ticket
    resource_id -- resource to be constrained
    options -- additional options for the constraint
    """
    options = dict(options)  # make a modifiable copy

    # prepare resource role
    if "rsc-role" in options:
        options["rsc-role"] = get_role_value_for_cib(
            const.PcmkRoleType(options["rsc-role"]),
            cib_schema_version >= const.PCMK_NEW_ROLES_CIB_VERSION,
        )
    resource_role = options.get("rsc-role", "")

    # autogenerate id if not provided
    if "id" not in options:
        options["id"] = id_provider.allocate_id(
            sanitize_id(
                "-".join(["ticket", ticket, resource_id])
                + (f"-{resource_role}" if resource_role else ""),
            )
        )

    # create the constraint element
    options["ticket"] = ticket
    options["rsc"] = resource_id
    constraint_el = SubElement(parent_element, TAG)
    for name, value in options.items():
        if value != "":
            constraint_el.attrib[name] = value

    return constraint_el


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


class DuplicatesCheckerTicketPlain(DuplicatesChecker):
    """
    Searcher of duplicate plain ticket constraints
    """

    def __init__(self) -> None:
        super().__init__()
        self._constraint_characteristics: Optional[
            Mapping[str, Optional[str]]
        ] = None

    def check(
        self,
        constraint_section: _Element,
        constraint_to_check: _Element,
        force_flags: reports.types.ForceFlags = (),
    ) -> reports.ReportItemList:
        self._constraint_characteristics = None
        return super().check(
            constraint_section, constraint_to_check, force_flags
        )

    @staticmethod
    def _characteristics(constraint_el: _Element) -> dict[str, Optional[str]]:
        return {
            "ticket": constraint_el.get("ticket"),
            "rsc": constraint_el.get("rsc"),
            "rsc-role": get_optional_value(
                role_constructor, constraint_el.get("rsc-role")
            ),
        }

    def _are_duplicate(
        self,
        constraint_to_check: _Element,
        constraint_el: _Element,
    ) -> bool:
        if self._constraint_characteristics is None:
            self._constraint_characteristics = self._characteristics(
                constraint_to_check
            )
        return (
            self._characteristics(constraint_el)
            == self._constraint_characteristics
        )


def are_duplicate_with_resource_set(element, other_element):
    return element.attrib["ticket"] == other_element.attrib[
        "ticket"
    ] and have_duplicate_resource_sets(element, other_element)


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

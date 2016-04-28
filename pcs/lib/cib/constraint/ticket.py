from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from lxml import etree

from pcs.lib import reports
from pcs.lib.cib.constraint import constraint
from pcs.lib.cib import tools
from pcs.lib.errors import LibraryError

TAG_NAME = 'rsc_ticket'
DESCRIPTION = "constraint ticket"
ATTRIB = {
    "loss-policy": ("fence", "stop", "freeze", "demote"),
    "ticket": None,
}
ATTRIB_PLAIN = {
    "rsc": None,
    "rsc-role": ("Stopped", "Started", "Master", "Slave"),
}

def _validate_options_common(options):
    report = []
    if "loss-policy" in options:
        loss_policy = options["loss-policy"].lower()
        if options["loss-policy"] not in ATTRIB["loss-policy"]:
            report.append(reports.value_out_of_set(
                'loss-policy value',
                ATTRIB["loss-policy"],
                options["loss-policy"]
            ))
        options["loss-policy"] = loss_policy
    return report

def _create_id(cib, ticket, resource_id, resource_role):
    return tools.find_unique_id(
        cib,
        "-".join(('ticket', ticket, resource_id, resource_role))
    )

def prepare_options_with_set(cib, options, resource_set_list):
    options = constraint.prepare_options(
        tuple(ATTRIB.keys()),
        options,
        create_id=partial(
            constraint.create_id, cib, TAG_NAME, resource_set_list
        ),
        validate_id=partial(tools.check_new_id_applicable, cib, DESCRIPTION),
    )
    report  = _validate_options_common(options)
    if "ticket" not in options:
        report.append(reports.required_option_is_missing('ticket'))
    if report:
        raise LibraryError(*report)
    return options

def prepare_options_plain(cib, options, ticket, resource_id, resource_role):
    options = options.copy()

    report  = _validate_options_common(options)

    if not ticket:
        report.append(reports.required_option_is_missing('ticket'))
    options["ticket"] = ticket

    if not ticket:
        report.append(reports.required_option_is_missing('rsc'))
    options["rsc"] = resource_id

    if resource_role:
        options["rsc-role"] = resource_role

    #resource role can be teorethicaly there even if resource_role variable
    #is empty
    if "rsc-role" in options:
        resource_role = options["rsc-role"].lower().capitalize()
        if resource_role not in ATTRIB_PLAIN["rsc-role"]:
            report.append(reports.value_out_of_set(
                'rsc-role',
                ATTRIB_PLAIN["rsc-role"],
                options["rsc-role"]
            ))
        options["rsc-role"] = resource_role

    if report:
        raise LibraryError(*report)

    return constraint.prepare_options(
        tuple(list(ATTRIB) + list(ATTRIB_PLAIN)),
        options,
        partial(
            _create_id,
            cib,
            options["ticket"],
            resource_id,
            options["rsc-role"]
        ),
        partial(tools.check_new_id_applicable, cib, DESCRIPTION)
    )

def create_plain(constraint_section, options):
    element = etree.SubElement(constraint_section, TAG_NAME)
    element.attrib.update(options)
    return element

def are_duplicit_plain(element, other_element):
    return all(
        element.attrib.get(name, "") == other_element.attrib.get(name, "")
        for name in ("ticket", "rsc", "rsc-role")
    )

def are_duplicit_with_resource_set(element, other_element):
    return (
        element.attrib["ticket"] == other_element.attrib["ticket"]
        and
        constraint.have_duplicit_resource_sets(element, other_element)
    )

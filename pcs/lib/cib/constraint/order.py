from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from pcs.lib import reports
from pcs.lib.cib.constraint import constraint
from pcs.lib.cib.tools import check_new_id_applicable
from pcs.lib.errors import LibraryError


TAG_NAME = "rsc_order"
DESCRIPTION = "constraint id"
ATTRIB = {
    "symmetrical": ("true", "false"),
    "kind": ("Optional", "Mandatory", "Serialize"),
}

def prepare_options_with_set(cib, options, resource_set_list):
    options = constraint.prepare_options(
        tuple(ATTRIB.keys()),
        options,
        create_id=partial(
            constraint.create_id, cib, TAG_NAME, resource_set_list
        ),
        validate_id=partial(check_new_id_applicable, cib, DESCRIPTION),
    )

    report_items = []
    if "kind" in options:
        kind = options["kind"].lower().capitalize()
        if kind not in ATTRIB["kind"]:
            report_items.append(reports.invalid_option_value(
                "kind", options["kind"], ATTRIB["kind"]
            ))
        options["kind"] = kind

    if "symmetrical" in options:
        symmetrical = options["symmetrical"].lower()
        if symmetrical not in ATTRIB["symmetrical"]:
            report_items.append(reports.invalid_option_value(
                "symmetrical", options["symmetrical"], ATTRIB["symmetrical"]
            ))
        options["symmetrical"] = symmetrical

    if report_items:
        raise LibraryError(*report_items)

    return options

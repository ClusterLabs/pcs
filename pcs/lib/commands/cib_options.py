from functools import partial

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.cib import sections
from pcs.lib.cib.nvpair import arrange_first_meta_attributes
from pcs.lib.cib.tools import IdProvider
from pcs.lib.env import LibraryEnvironment


def _set_any_defaults(section_name, env: LibraryEnvironment, options):
    """
    string section_name -- determine the section of defaults
    env -- provides access to outside environment
    dict options -- are desired options with its values; when value is empty the
        option have to be removed
    """
    # Do not ever remove the nvset element, even if it is empty. There may be
    # ACLs set in pacemaker which allow "write" for nvpairs (adding, changing
    # and removing) but not nvsets. In such a case, removing the nvset would
    # cause the whole change to be rejected by pacemaker with a "permission
    # denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    env.report_processor.report(
        ReportItem.warning(reports.messages.DefaultsCanBeOverriden())
    )

    if not options:
        return

    cib = env.get_cib()

    # Do not create new defaults element if we are only removing values from it.
    only_removing = True
    for value in options.values():
        if value != "":
            only_removing = False
            break
    if only_removing and not sections.exists(cib, section_name):
        return

    defaults_section = sections.get(cib, section_name)
    arrange_first_meta_attributes(
        defaults_section,
        options,
        IdProvider(cib),
        new_id="{0}-options".format(section_name),
    )

    env.push_cib()


set_operations_defaults = partial(_set_any_defaults, sections.OP_DEFAULTS)
set_resources_defaults = partial(_set_any_defaults, sections.RSC_DEFAULTS)

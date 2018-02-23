from functools import partial

from pcs.lib import reports
from pcs.lib.cib import sections
from pcs.lib.xml_tools import remove_when_pointless
from pcs.lib.cib.nvpair import arrange_first_meta_attributes


def _set_any_defaults(section_name, env, options):
    """
    string section_name -- determine the section of defaults
    LibraryEnvironment env -- provides access to outside environment
    dict options -- are desired options with its values; when value is empty the
        option have to be removed
    """
    env.report_processor.process(reports.defaults_can_be_overriden())

    if not options:
        return

    defaults_section = sections.get(env.get_cib(), section_name)
    arrange_first_meta_attributes(
        defaults_section,
        options,
        new_id="{0}-options".format(section_name)
    )
    remove_when_pointless(defaults_section)

    env.push_cib()

set_operations_defaults = partial(_set_any_defaults, sections.OP_DEFAULTS)
set_resources_defaults = partial(_set_any_defaults, sections.RSC_DEFAULTS)

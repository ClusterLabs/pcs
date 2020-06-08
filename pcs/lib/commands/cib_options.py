from functools import partial
from typing import (
    Any,
    Container,
    List,
    Mapping,
    Optional,
)

from pcs.common import reports
from pcs.common.pacemaker.nvset import CibNvsetDto
from pcs.common.reports.item import ReportItem
from pcs.common.tools import Version
from pcs.lib.cib import (
    nvpair_multi,
    sections,
)
from pcs.lib.cib.nvpair import arrange_first_meta_attributes
from pcs.lib.cib.tools import IdProvider
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def resource_defaults_create(
    env: LibraryEnvironment,
    nvpairs: Mapping[str, str],
    nvset_options: Mapping[str, str],
    nvset_rule: Optional[str] = None,
    force_flags: Optional[Container] = None,
) -> None:
    """
    Create new resource defaults nvset

    env --
    nvpairs -- name-value pairs to be put into the new nvset
    nvset_options -- additional attributes of the created nvset
    nvset_rule -- optional rule describing when the created nvset applies
    force_flags -- list of flags codes
    """
    return _defaults_create(
        env,
        sections.RSC_DEFAULTS,
        dict(rule_allows_rsc_expr=True, rule_allows_op_expr=False),
        nvpairs,
        nvset_options,
        nvset_rule=nvset_rule,
        force_flags=force_flags,
    )


def operation_defaults_create(
    env: LibraryEnvironment,
    nvpairs: Mapping[str, str],
    nvset_options: Mapping[str, str],
    nvset_rule: Optional[str] = None,
    force_flags: Optional[Container] = None,
) -> None:
    """
    Create new operation defaults nvset

    env --
    nvpairs -- name-value pairs to be put into the new nvset
    nvset_options -- additional attributes of the created nvset
    nvset_rule -- optional rule describing when the created nvset applies
    force_flags -- list of flags codes
    """
    return _defaults_create(
        env,
        sections.OP_DEFAULTS,
        dict(rule_allows_rsc_expr=True, rule_allows_op_expr=True),
        nvpairs,
        nvset_options,
        nvset_rule=nvset_rule,
        force_flags=force_flags,
    )


def _defaults_create(
    env: LibraryEnvironment,
    cib_section: str,
    validator_options: Mapping[str, Any],
    nvpairs: Mapping[str, str],
    nvset_options: Mapping[str, str],
    nvset_rule: Optional[str] = None,
    force_flags: Optional[Container] = None,
) -> None:
    if force_flags is None:
        force_flags = set()
    force = (reports.codes.FORCE in force_flags) or (
        reports.codes.FORCE_OPTIONS in force_flags
    )

    required_cib_version = None
    if nvset_rule:
        required_cib_version = Version(3, 4, 0)
    cib = env.get_cib(required_cib_version)
    id_provider = IdProvider(cib)

    validator = nvpair_multi.ValidateNvsetAppendNew(
        id_provider,
        nvpairs,
        nvset_options,
        nvset_rule=nvset_rule,
        **validator_options,
    )
    if env.report_processor.report_list(
        validator.validate(force_options=force)
    ).has_errors:
        raise LibraryError()

    parent_el = sections.get(cib, cib_section)
    nvpair_multi.nvset_append_new(
        parent_el,
        id_provider,
        nvpair_multi.NVSET_META,
        nvpairs,
        nvset_options,
        nvset_rule=validator.get_parsed_rule(),
    )

    env.report_processor.report(
        ReportItem.warning(reports.messages.DefaultsCanBeOverriden())
    )
    env.push_cib()


def resource_defaults_config(env: LibraryEnvironment) -> List[CibNvsetDto]:
    """
    List all resource defaults nvsets
    """
    return _defaults_config(env, sections.RSC_DEFAULTS)


def operation_defaults_config(env: LibraryEnvironment) -> List[CibNvsetDto]:
    """
    List all operation defaults nvsets
    """
    return _defaults_config(env, sections.OP_DEFAULTS)


def _defaults_config(
    env: LibraryEnvironment, cib_section: str,
) -> List[CibNvsetDto]:
    return [
        nvpair_multi.nvset_element_to_dto(nvset_el)
        for nvset_el in nvpair_multi.find_nvsets(
            sections.get(env.get_cib(), cib_section)
        )
    ]


def _set_any_defaults(
    section_name: str, env: LibraryEnvironment, options: Mapping[str, str]
) -> None:
    # TODO remove
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


# TODO remove
set_operations_defaults = partial(_set_any_defaults, sections.OP_DEFAULTS)
# TODO remove
set_resources_defaults = partial(_set_any_defaults, sections.RSC_DEFAULTS)

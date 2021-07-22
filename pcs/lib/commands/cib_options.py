from typing import (
    Any,
    Container,
    Iterable,
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
from pcs.lib.cib.rule import (
    RuleInEffectEval,
    RuleInEffectEvalDummy,
    RuleInEffectEvalOneByOne,
    RuleParseError,
    has_node_attr_expr_with_type_integer,
    has_rsc_or_op_expression,
    parse_rule,
)
from pcs.lib.cib.tools import (
    IdProvider,
    get_pacemaker_version_by_which_cib_was_validated,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.live import has_rule_in_effect_status_tool


def resource_defaults_create(
    env: LibraryEnvironment,
    nvpairs: Mapping[str, str],
    nvset_options: Mapping[str, str],
    nvset_rule: Optional[str] = None,
    force_flags: Container[reports.types.ForceCode] = (),
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
        dict(
            rule_allows_rsc_expr=True,
            rule_allows_op_expr=False,
            rule_allows_node_attr_expr=False,
        ),
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
    force_flags: Container[reports.types.ForceCode] = (),
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
        dict(
            rule_allows_rsc_expr=True,
            rule_allows_op_expr=True,
            rule_allows_node_attr_expr=True,
        ),
        nvpairs,
        nvset_options,
        nvset_rule=nvset_rule,
        force_flags=force_flags,
    )


def _defaults_create(
    env: LibraryEnvironment,
    cib_section_name: str,
    validator_options: Mapping[str, Any],
    nvpairs: Mapping[str, str],
    nvset_options: Mapping[str, str],
    nvset_rule: Optional[str] = None,
    force_flags: Container[reports.types.ForceCode] = (),
) -> None:
    required_cib_version = None
    nice_to_have_cib_version = None
    if nvset_rule:
        # Parse the rule to see if we need to upgrade CIB schema. All errors
        # would be properly reported by a validator called bellow, so we can
        # safely ignore them here.
        try:
            rule_tree = parse_rule(nvset_rule)
            if has_rsc_or_op_expression(rule_tree):
                required_cib_version = Version(3, 4, 0)
            if has_node_attr_expr_with_type_integer(rule_tree):
                nice_to_have_cib_version = Version(3, 5, 0)
        except RuleParseError:
            pass

    cib = env.get_cib(
        minimal_version=required_cib_version,
        nice_to_have_version=nice_to_have_cib_version,
    )
    id_provider = IdProvider(cib)

    validator = nvpair_multi.ValidateNvsetAppendNew(
        id_provider,
        nvpairs,
        nvset_options,
        nvset_rule=nvset_rule,
        **validator_options,
    )
    if env.report_processor.report_list(
        validator.validate(force_options=reports.codes.FORCE in force_flags)
    ).has_errors:
        raise LibraryError()

    nvpair_multi.nvset_append_new(
        sections.get(cib, cib_section_name),
        id_provider,
        get_pacemaker_version_by_which_cib_was_validated(cib),
        nvpair_multi.NVSET_META,
        nvpairs,
        nvset_options,
        nvset_rule=validator.get_parsed_rule(),
    )

    env.report_processor.report(
        ReportItem.warning(reports.messages.DefaultsCanBeOverriden())
    )
    env.push_cib()


def resource_defaults_config(
    env: LibraryEnvironment, evaluate_expired: bool
) -> List[CibNvsetDto]:
    """
    List all resource defaults nvsets

    env --
    evaluate_expired -- also evaluate whether rules are expired or in effect
    """
    return _defaults_config(env, sections.RSC_DEFAULTS, evaluate_expired)


def operation_defaults_config(
    env: LibraryEnvironment, evaluate_expired: bool
) -> List[CibNvsetDto]:
    """
    List all operation defaults nvsets

    env --
    evaluate_expired -- also evaluate whether rules are expired or in effect
    """
    return _defaults_config(env, sections.OP_DEFAULTS, evaluate_expired)


def _defaults_config(
    env: LibraryEnvironment, cib_section_name: str, evaluate_expired: bool
) -> List[CibNvsetDto]:
    runner = env.cmd_runner()
    cib = env.get_cib()

    if evaluate_expired:
        if has_rule_in_effect_status_tool():
            in_effect_eval: RuleInEffectEval = RuleInEffectEvalOneByOne(
                cib, runner
            )
        else:
            in_effect_eval = RuleInEffectEvalDummy()
            env.report_processor.report(
                ReportItem.warning(
                    reports.messages.RuleInEffectStatusDetectionNotSupported()
                )
            )
    else:
        in_effect_eval = RuleInEffectEvalDummy()

    return [
        nvpair_multi.nvset_element_to_dto(nvset_el, in_effect_eval)
        for nvset_el in nvpair_multi.find_nvsets(
            sections.get(cib, cib_section_name)
        )
    ]


def resource_defaults_remove(
    env: LibraryEnvironment, nvset_id_list: Iterable[str]
) -> None:
    """
    Remove specified resource defaults nvsets

    env --
    nvset_id_list -- nvset IDs to be removed
    """
    return _defaults_remove(env, sections.RSC_DEFAULTS, nvset_id_list)


def operation_defaults_remove(
    env: LibraryEnvironment, nvset_id_list: Iterable[str]
) -> None:
    """
    Remove specified operation defaults nvsets

    env --
    nvset_id_list -- nvset IDs to be removed
    """
    return _defaults_remove(env, sections.OP_DEFAULTS, nvset_id_list)


def _defaults_remove(
    env: LibraryEnvironment, cib_section_name: str, nvset_id_list: Iterable[str]
) -> None:
    if not nvset_id_list:
        return
    nvset_elements, report_list = nvpair_multi.find_nvsets_by_ids(
        sections.get(env.get_cib(), cib_section_name), nvset_id_list
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    nvpair_multi.nvset_remove(nvset_elements)
    env.push_cib()


def resource_defaults_update(
    env: LibraryEnvironment,
    nvset_id: Optional[str],
    nvpairs: Mapping[str, str],
) -> None:
    """
    Update specified resource defaults nvset

    env --
    nvset_id -- nvset ID to be updated; if None, update an existing nvset if
        there is only one
    nvpairs -- name-value pairs to be put into the nvset
    """
    return _defaults_update(
        env,
        sections.RSC_DEFAULTS,
        nvset_id,
        nvpairs,
        reports.const.PCS_COMMAND_RESOURCE_DEFAULTS_UPDATE,
    )


def operation_defaults_update(
    env: LibraryEnvironment,
    nvset_id: Optional[str],
    nvpairs: Mapping[str, str],
) -> None:
    """
    Update specified operation defaults nvset

    env --
    nvset_id -- nvset ID to be updated; if None, update an existing nvset if
        there is only one
    nvpairs -- name-value pairs to be put into the nvset
    """
    return _defaults_update(
        env,
        sections.OP_DEFAULTS,
        nvset_id,
        nvpairs,
        reports.const.PCS_COMMAND_OPERATION_DEFAULTS_UPDATE,
    )


def _defaults_update(
    env: LibraryEnvironment,
    cib_section_name: str,
    nvset_id: Optional[str],
    nvpairs: Mapping[str, str],
    pcs_command: reports.types.PcsCommand,
) -> None:
    cib = env.get_cib()
    id_provider = IdProvider(cib)

    if nvset_id is None:
        # Backward compatibility code to support an old use case where no id
        # was requested and provided and the first meta_attributes nvset was
        # created / updated. However, we check that there is only one nvset
        # present in the CIB to prevent breaking the configuration with
        # multiple nvsets in place.

        # This is to be supported as it provides means of easily managing
        # defaults if only one set of defaults is needed.

        # TODO move this to a separate lib command.

        if not nvpairs:
            return

        # Do not create new defaults element if we are only removing values
        # from it.
        only_removing = True
        for value in nvpairs.values():
            if value != "":
                only_removing = False
                break
        if only_removing and not sections.exists(cib, cib_section_name):
            env.report_processor.report(
                ReportItem.warning(reports.messages.DefaultsCanBeOverriden())
            )
            return

        nvset_elements = nvpair_multi.find_nvsets(
            sections.get(cib, cib_section_name)
        )
        if len(nvset_elements) > 1:
            env.report_processor.report(
                reports.item.ReportItem.error(
                    reports.messages.CibNvsetAmbiguousProvideNvsetId(
                        pcs_command
                    )
                )
            )
            raise LibraryError()
        env.report_processor.report(
            ReportItem.warning(reports.messages.DefaultsCanBeOverriden())
        )
        if len(nvset_elements) == 1:
            nvpair_multi.nvset_update(nvset_elements[0], id_provider, nvpairs)
        elif only_removing:
            # do not create new nvset if there is none and we are only removing
            # nvpairs
            return
        else:
            nvpair_multi.nvset_append_new(
                sections.get(cib, cib_section_name),
                id_provider,
                get_pacemaker_version_by_which_cib_was_validated(cib),
                nvpair_multi.NVSET_META,
                nvpairs,
                {},
            )
        env.push_cib()
        return

    nvset_elements, report_list = nvpair_multi.find_nvsets_by_ids(
        sections.get(cib, cib_section_name), [nvset_id]
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    nvpair_multi.nvset_update(nvset_elements[0], id_provider, nvpairs)
    env.report_processor.report(
        ReportItem.warning(reports.messages.DefaultsCanBeOverriden())
    )
    env.push_cib()

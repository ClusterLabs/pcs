from typing import (
    cast,
    Mapping,
    NewType,
    Optional,
)
from xml.etree.ElementTree import Element

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.lib import validate
from pcs.lib.cib.rule import (
    RuleParseError,
    RuleRoot,
    parse_rule,
    rule_to_cib,
)
from pcs.lib.cib.tools import (
    IdProvider,
    create_subelement_id,
)


NvsetTag = NewType("NvsetTag", str)
NVSET_INSTANCE = NvsetTag("instance_attributes")
NVSET_META = NvsetTag("meta_attributes")


class ValidateNvsetAppendNew:
    """
    Validator for creating new nvset and appending it to CIB
    """

    def __init__(
        self,
        id_provider: IdProvider,
        nvpair_dict: Mapping[str, str],
        nvset_options: Mapping[str, str],
        nvset_rule: Optional[str] = None,
        rule_allows_rsc_expr: bool = False,
        rule_allows_op_expr: bool = False,
    ):
        """
        id_provider -- elements' ids generator
        nvpair_dict -- nvpairs to be put into the new nvset
        nvset_options -- additional attributes of the created nvset
        nvset_rule -- optional rule describing when the created nvset applies
        rule_allows_rsc_expr -- is rsc_expression element allowed in nvset_rule?
        rule_allows_op_expr -- is op_expression element allowed in nvset_rule?
        """
        self._id_provider = id_provider
        self._nvpair_dict = nvpair_dict
        self._nvset_options = nvset_options
        self._nvset_rule = nvset_rule
        self._allow_rsc_expr = rule_allows_rsc_expr
        self._allow_op_expr = rule_allows_op_expr
        self._nvset_rule_parsed: Optional[RuleRoot] = None

    def validate(self, force_options: bool = False) -> reports.ReportItemList:
        report_list: reports.ReportItemList = []

        # Nvpair dict is intentionally not validated: it may contain any keys
        # and values. This can change in the future and then we add a
        # validation. Until then there is really nothing to validate there.

        # validate nvset options
        validators = [
            validate.NamesIn(
                ("id", "score"),
                **validate.set_warning(
                    reports.codes.FORCE_OPTIONS, force_options
                ),
            ),
            # with id_provider it validates that the id is available as well
            validate.ValueId(
                "id", option_name_for_report="id", id_provider=self._id_provider
            ),
            validate.ValueScore("score"),
        ]
        report_list.extend(
            validate.ValidatorAll(validators).validate(self._nvset_options)
        )

        # parse and validate rule
        # TODO write and call parsed rule validation and cleanup and tests
        if self._nvset_rule:
            try:
                # TODO Instead of setting allow flags we want to have them set
                # to True always and check the parsed rule tree in validator
                # instead. That will give us better error messages, such as "op
                # expression cannot be used in this context" instead of an
                # universal "parse error"
                self._nvset_rule_parsed = parse_rule(
                    self._nvset_rule,
                    allow_rsc_expr=self._allow_rsc_expr,
                    allow_op_expr=self._allow_op_expr,
                )
            except RuleParseError as e:
                report_list.append(
                    reports.ReportItem.error(
                        reports.messages.CibRuleParseError(
                            e.rule_string,
                            e.msg,
                            e.rule_line,
                            e.lineno,
                            e.colno,
                            e.pos,
                        )
                    )
                )

        return report_list

    def get_parsed_rule(self) -> Optional[RuleRoot]:
        return self._nvset_rule_parsed


def nvset_append_new(
    parent_element: Element,
    id_provider: IdProvider,
    nvset_tag: NvsetTag,
    nvpair_dict: Mapping[str, str],
    nvset_options: Mapping[str, str],
    nvset_rule: Optional[RuleRoot] = None,
) -> Element:
    """
    Create new nvset and append it to CIB

    parent_element -- the created nvset will be appended into this element
    id_provider -- elements' ids generator
    nvset_tag -- type and actual tag of the nvset
    nvpair_dict -- nvpairs to be put into the new nvset
    nvset_options -- additional attributes of the created nvset
    nvset_rule -- optional rule describing when the created nvset applies
    """
    nvset_options = dict(nvset_options)  # make a copy which we can modify
    if "id" not in nvset_options or not nvset_options["id"]:
        nvset_options["id"] = create_subelement_id(
            parent_element, nvset_tag, id_provider
        )

    nvset_el = etree.SubElement(cast(_Element, parent_element), nvset_tag)
    for name, value in nvset_options.items():
        if value != "":
            # for whatever reason, mypy thinks "_Element" has no attribute
            # "set"
            nvset_el.set(name, value)  # type: ignore
    if nvset_rule:
        rule_to_cib(cast(Element, nvset_el), id_provider, nvset_rule)
    for name, value in nvpair_dict.items():
        _set_nvpair(cast(Element, nvset_el), id_provider, name, value)
    return cast(Element, nvset_el)


def _set_nvpair(
    nvset_element: Element, id_provider: IdProvider, name: str, value: str
):
    """
    Ensure name-value pair is set / removed in specified nvset

    nvset_element -- container for nvpair elements to update
    id_provider -- elements' ids generator
    name -- name of the nvpair to be set
    value -- value of the nvpair to be set, if "" the nvpair will be removed
    """
    nvpair_el_list = nvset_element.findall("./nvpair[@name='{0}']".format(name))

    if not nvpair_el_list:
        if value != "":
            etree.SubElement(
                cast(_Element, nvset_element),
                "nvpair",
                {
                    "id": create_subelement_id(
                        nvset_element,
                        # limit id length to prevent excessively long ids
                        name[:20],
                        id_provider,
                    ),
                    "name": name,
                    "value": value,
                },
            )
        return

    if value != "":
        nvpair_el_list[0].set("value", value)
    else:
        nvset_element.remove(nvpair_el_list[0])
    for nvpair_el in nvpair_el_list[1:]:
        nvset_element.remove(nvpair_el)

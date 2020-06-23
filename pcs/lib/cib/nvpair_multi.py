from typing import (
    cast,
    Iterable,
    List,
    Mapping,
    NewType,
    Optional,
    Tuple,
)
from xml.etree.ElementTree import Element

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
)
from pcs.common.reports import ReportItemList
from pcs.common.types import CibNvsetType
from pcs.lib import validate
from pcs.lib.cib.rule import (
    RuleParseError,
    RuleRoot,
    RuleValidator,
    parse_rule,
    rule_element_to_dto,
    rule_to_cib,
)
from pcs.lib.cib.tools import (
    ElementSearcher,
    IdProvider,
    create_subelement_id,
)
from pcs.lib.xml_tools import (
    export_attributes,
    remove_one_element,
)


NvsetTag = NewType("NvsetTag", str)
NVSET_INSTANCE = NvsetTag("instance_attributes")
NVSET_META = NvsetTag("meta_attributes")

_tag_to_type = {
    str(NVSET_META): CibNvsetType.META,
    str(NVSET_INSTANCE): CibNvsetType.INSTANCE,
}


def nvpair_element_to_dto(nvpair_el: Element) -> CibNvpairDto:
    """
    Export an nvpair xml element to its DTO
    """
    return CibNvpairDto(
        nvpair_el.get("id", ""),
        nvpair_el.get("name", ""),
        nvpair_el.get("value", ""),
    )


def nvset_element_to_dto(nvset_el: Element) -> CibNvsetDto:
    """
    Export an nvset xml element to its DTO
    """
    rule_el = nvset_el.find("./rule")
    return CibNvsetDto(
        nvset_el.get("id", ""),
        _tag_to_type[nvset_el.tag],
        export_attributes(nvset_el, with_id=False),
        None if rule_el is None else rule_element_to_dto(rule_el),
        [
            nvpair_element_to_dto(nvpair_el)
            for nvpair_el in nvset_el.iterfind("./nvpair")
        ],
    )


def find_nvsets(parent_element: Element) -> List[Element]:
    """
    Get all nvset xml elements in the given parent element

    parent_element -- an element to look for nvsets in
    """
    return cast(
        # The xpath method has a complicated return value, but we know our xpath
        # expression returns only elements.
        List[Element],
        cast(_Element, parent_element).xpath(
            "./*[{nvset_tags}]".format(
                nvset_tags=" or ".join(f"self::{tag}" for tag in _tag_to_type)
            )
        ),
    )


def find_nvsets_by_ids(
    parent_element: Element, id_list: Iterable[str]
) -> Tuple[List[Element], ReportItemList]:
    """
    Find nvset elements by their IDs and return them with non-empty report
    list in case of errors.

    parent_element -- an element to look for nvsets in
    id_list -- nvset IDs to be looked for
    """
    element_list = []
    report_list: ReportItemList = []
    for nvset_id in id_list:
        searcher = ElementSearcher(
            _tag_to_type.keys(),
            nvset_id,
            parent_element,
            element_type_desc="options set",
        )
        if searcher.element_found():
            element_list.append(searcher.get_element())
        else:
            report_list.extend(searcher.get_errors())
    return element_list, report_list


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
                # Allow flags are set to True always, the parsed rule tree is
                # checked in the validator instead. That gives us better error
                # messages, such as "op expression cannot be used in this
                # context" instead of a universal "parse error".
                self._nvset_rule_parsed = parse_rule(
                    self._nvset_rule, allow_rsc_expr=True, allow_op_expr=True
                )
                report_list.extend(
                    RuleValidator(
                        self._nvset_rule_parsed,
                        allow_rsc_expr=self._allow_rsc_expr,
                        allow_op_expr=self._allow_op_expr,
                    ).get_reports()
                )
            except RuleParseError as e:
                report_list.append(
                    reports.ReportItem.error(
                        reports.messages.RuleExpressionParseError(
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
            nvset_el.attrib[name] = value
    if nvset_rule:
        rule_to_cib(cast(Element, nvset_el), id_provider, nvset_rule)
    for name, value in nvpair_dict.items():
        _set_nvpair(cast(Element, nvset_el), id_provider, name, value)
    return cast(Element, nvset_el)


def nvset_remove(nvset_el_list: Iterable[Element]) -> None:
    """
    Remove given nvset elements from CIB

    nvset_el_list -- nvset elements to be removed
    """
    for nvset_el in nvset_el_list:
        remove_one_element(nvset_el)


def nvset_update(
    nvset_el: Element, id_provider: IdProvider, nvpair_dict: Mapping[str, str],
) -> None:
    """
    Update an existing nvset

    nvset_el -- nvset to be updated
    id_provider -- elements' ids generator
    nvpair_dict -- nvpairs to be put into the nvset
    """
    # Do not ever remove the nvset element, even if it is empty. There may be
    # ACLs set in pacemaker which allow "write" for nvpairs (adding, changing
    # and removing) but not nvsets. In such a case, removing the nvset would
    # cause the whole change to be rejected by pacemaker with a "permission
    # denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    for name, value in nvpair_dict.items():
        _set_nvpair(nvset_el, id_provider, name, value)


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
    nvpair_el_list = cast(
        # The xpath method has a complicated return value, but we know our xpath
        # expression returns only elements.
        List[Element],
        cast(_Element, nvset_element).xpath("./nvpair[@name=$name]", name=name),
    )

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

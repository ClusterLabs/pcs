from contextlib import contextmanager
from typing import (
    Dict,
    Iterable,
    Iterator,
    Optional,
    Sequence,
)
from xml.etree.ElementTree import Element

from pcs.common.tools import Version
from pcs.lib.cib import tag
from pcs.lib.cib.tools import (
    get_constraints,
    get_resources,
    get_tags,
    IdProvider,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.xml_tools import get_root


REQUIRED_CIB_VERSION = Version(1, 3, 0)


@contextmanager
def cib_tags_section(env: LibraryEnvironment) -> Iterator[Element]:
    yield get_tags(env.get_cib(REQUIRED_CIB_VERSION))
    env.push_cib()


def create(
    env: LibraryEnvironment, tag_id: str, idref_list: Sequence[str],
) -> None:
    """
    Create a tag in a cib.

    env -- provides all for communication with externals
    tag_id -- identifier of new tag
    idref_list -- reference ids which we want to tag
    """
    with cib_tags_section(env) as tags_section:
        env.report_processor.report_list(
            tag.validate_create_tag(
                get_resources(get_root(tags_section)),
                tag_id,
                idref_list,
                IdProvider(tags_section),
            )
        )
        if env.report_processor.has_errors:
            raise LibraryError()
        tag.create_tag(tags_section, tag_id, idref_list)


def config(
    env: LibraryEnvironment, tag_filter: Sequence[str],
) -> Iterable[Dict[str, Iterable[str]]]:
    """
    Get tags specified in tag_filter or if empty, then get all the tags
    configured.

    env -- provides all for communication with externals
    tag_filter -- list of tags we want to get
    """
    tags_section: Element = get_tags(env.get_cib(REQUIRED_CIB_VERSION))
    if tag_filter:
        tag_element_list, report_list = tag.find_tag_elements_by_ids(
            tags_section, tag_filter,
        )
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()
    else:
        tag_element_list = tag.get_list_of_tag_elements(tags_section)
    return [
        tag.tag_element_to_dict(tag_element) for tag_element in tag_element_list
    ]


def remove(env: LibraryEnvironment, tag_list: Iterable[str]) -> None:
    """
    Remove specified tags from a cib.

    env -- provides all for communication with externals
    tag_list -- list of tags for the removal
    """
    with cib_tags_section(env) as tags_section:
        env.report_processor.report_list(
            tag.validate_remove_tag(
                get_constraints(get_root(tags_section)), tag_list,
            )
        )
        tag_elements, report_list = tag.find_tag_elements_by_ids(
            tags_section, tag_list,
        )
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()
        tag.remove_tag(tag_elements)


def update(
    env: LibraryEnvironment,
    tag_id: str,
    idref_add: Sequence[str],
    idref_remove: Sequence[str],
    adjacent_idref: Optional[str] = None,
    put_after_adjacent: bool = False,
) -> None:
    """
    Update specified tag by given id references.

    env -- provides all for communication with externals
    tag_id -- identifier of new tag
    idref_add -- reference ids to add
    idref_remove -- reference ids to remove
    adjacent_idref -- id of the existing reference in tag
    put_after_adjacent -- flag where to put references
    """
    with cib_tags_section(env) as tags_section:
        tag_list, report_list = tag.find_tag_elements_by_ids(
            tags_section, [tag_id],
        )
        report_list += tag.validate_add_remove_ids(
            get_resources(get_root(tags_section)),
            tag_id,
            idref_add,
            idref_remove,
            adjacent_idref,
        )
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()

        adjacent_element, report_list = tag.find_adjacent_obj_ref(
            tag_list[0], adjacent_idref,
        )
        env.report_processor.report_list(report_list)
        obj_ref_list, _ = tag.find_obj_ref_elements_in_tag(
            tag_list[0], idref_add,
        )
        env.report_processor.report_list(
            tag.validate_add_obj_ref(obj_ref_list, adjacent_element, tag_id)
        )

        remove_el_list, report_list = tag.find_obj_ref_elements_in_tag(
            tag_list[0], idref_remove,
        )
        # avoid removing all references from tag that would leave tag empty
        if not idref_add:
            report_list += tag.validate_remove_obj_ref(remove_el_list)
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()
        tag.add_obj_ref(
            tag_list[0],
            tag.create_obj_ref_elements(idref_add, obj_ref_list),
            adjacent_element,
            put_after_adjacent,
        )
        tag.remove_obj_ref(remove_el_list)

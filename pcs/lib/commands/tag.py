from contextlib import contextmanager
from typing import (
    Iterator,
    Optional,
    Union,
)

from lxml.etree import _Element

from pcs.common.types import StringSequence
from pcs.lib.cib import tag
from pcs.lib.cib.tools import (
    IdProvider,
    get_constraints,
    get_resources,
    get_tags,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.xml_tools import get_root


@contextmanager
def cib_tags_section(env: LibraryEnvironment) -> Iterator[_Element]:
    yield get_tags(env.get_cib())
    env.push_cib()


def create(
    env: LibraryEnvironment, tag_id: str, idref_list: StringSequence
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
    env: LibraryEnvironment,
    tag_filter: StringSequence,
) -> list[dict[str, Union[str, list[str]]]]:
    """
    Get tags specified in tag_filter or if empty, then get all the tags
    configured.

    env -- provides all for communication with externals
    tag_filter -- list of tags we want to get
    """
    tags_section: _Element = get_tags(env.get_cib())
    if tag_filter:
        tag_element_list, report_list = tag.find_tag_elements_by_ids(
            tags_section,
            tag_filter,
        )
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()
    else:
        tag_element_list = tag.get_list_of_tag_elements(tags_section)
    return [
        tag.tag_element_to_dict(tag_element) for tag_element in tag_element_list
    ]


def remove(env: LibraryEnvironment, tag_list: StringSequence) -> None:
    """
    Remove specified tags from a cib.

    env -- provides all for communication with externals
    tag_list -- list of tags for the removal
    """
    with cib_tags_section(env) as tags_section:
        env.report_processor.report_list(
            tag.validate_remove_tag(
                get_constraints(get_root(tags_section)),
                tag_list,
            )
        )
        tag_elements, report_list = tag.find_tag_elements_by_ids(
            tags_section,
            tag_list,
        )
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()
        tag.remove_tag(tag_elements)


def update(
    env: LibraryEnvironment,
    tag_id: str,
    idref_add: StringSequence,
    idref_remove: StringSequence,
    adjacent_idref: Optional[str] = None,
    put_after_adjacent: bool = False,
) -> None:
    """
    Update specified tag by given id references.

    env -- provides all for communication with externals
    tag_id -- id of an existing tag to be updated
    idref_add -- reference ids to be added
    idref_remove -- reference ids to be removed
    adjacent_idref -- id of the element next to which the added elements will
        be put
    put_after_adjacent -- put elements after (True) or before (False) the
        adjacent element
    """
    with cib_tags_section(env) as tags_section:
        validator = tag.ValidateTagUpdateByIds(
            tag_id,
            idref_add,
            idref_remove,
            adjacent_idref,
        )
        if env.report_processor.report_list(
            validator.validate(
                get_resources(get_root(tags_section)),
                tags_section,
            )
        ).has_errors:
            raise LibraryError()
        # check for mypy
        tag_element = validator.tag_element()
        if tag_element is not None:
            tag.add_obj_ref(
                tag_element,
                validator.add_obj_ref_element_list(),
                validator.adjacent_obj_ref_element(),
                put_after_adjacent,
            )
            tag.remove_obj_ref(validator.remove_obj_ref_element_list())

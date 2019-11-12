from contextlib import contextmanager
from typing import Iterator, Sequence
from xml.etree.ElementTree import Element

from pcs.common.reports import SimpleReportProcessor
from pcs.common.tools import Version
from pcs.lib.cib import tag
from pcs.lib.cib.tools import (
    get_tags,
    IdProvider,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


REQUIRED_CIB_VERSION = Version(1, 3, 0)

@contextmanager
def cib_tags_section(env: LibraryEnvironment) -> Iterator[Element]:
    yield get_tags(env.get_cib(REQUIRED_CIB_VERSION))
    env.push_cib()

def create(
    env: LibraryEnvironment,
    tag_id: str,
    idref_list: Sequence[str],
) -> None:
    """
    Create a tag in a cib.

    env -- provides all for communication with externals
    tag_id -- identifier of new tag
    idref_list -- reference ids which we want to tag
    """
    with cib_tags_section(env) as tags_section:
        report_processor = SimpleReportProcessor(env.report_processor)
        report_processor.report_list(
            tag.validate_create_tag(
                tag_id,
                idref_list,
                tags_section,
                IdProvider(tags_section),
            )
        )
        if report_processor.has_errors:
            raise LibraryError()
        tag.create_tag(tags_section, tag_id, idref_list)

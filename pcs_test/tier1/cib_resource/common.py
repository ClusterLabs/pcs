from unittest import TestCase

from lxml import etree

from pcs.common.str_tools import format_list, format_optional, format_plural
from pcs.lib.resource_agent import const as ra_const

from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.metadata_dto import (
    FIXTURE_KNOWN_META_NAMES_PRIMITIVE_META,
    FIXTURE_KNOWN_META_NAMES_STONITH_META,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


def get_cib_resources(cib):
    return etree.tostring(etree.parse(cib).findall(".//resources")[0])


class ResourceTest(TestCase, get_assert_pcs_effect_mixin(get_cib_resources)):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_resource_common")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()


def fixture_meta_attributes_warning(meta_attrs, agent_type):
    type_to_name_list = {
        ra_const.PRIMITIVE_META: FIXTURE_KNOWN_META_NAMES_PRIMITIVE_META,
        ra_const.STONITH_META: FIXTURE_KNOWN_META_NAMES_STONITH_META,
    }
    type_to_rsc_desc = {
        ra_const.PRIMITIVE_META: "resource",
        ra_const.STONITH_META: "stonith",
    }
    if agent_type not in type_to_name_list:
        raise AssertionError(
            f"Unknown agent type '{agent_type}', known types: "
            f"{', '.join(type_to_name_list.keys())}"
        )

    rsc_desc = type_to_rsc_desc[agent_type].capitalize()
    attributes = format_plural(meta_attrs, "attribute")
    have = format_plural(meta_attrs, "has")
    known_meta = format_list(type_to_name_list[agent_type])
    attributes_known = format_plural(type_to_name_list[agent_type], "attribute")
    return (
        f"Warning: {rsc_desc} meta {attributes} {format_list(meta_attrs)} "
        f"{have} no effect on cluster resource handling, meta "
        f"{attributes_known} with effect: {known_meta}\n"
    )


def fixture_meta_attributes_not_validated_warning(meta_type_list):
    resource_desc = format_optional(
        " / ".join(sorted(meta_type_list)), template="of {} "
    )
    return f"Warning: Meta attributes {resource_desc}are not validated\n"

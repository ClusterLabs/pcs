from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.xml import etree_to_str


def replace_element(element_xpath, new_content):
    """
    Return function that replace element (defined by element_xpath) in the
    cib_tree with new_content.

    string element_xpath -- its destination must be one element: replacement
        is applied only on the first occurence
    string new_content -- contains a content that have to be placed instead of
        a element found by element_xpath
    """
    def replace(cib_tree):
        element_to_replace = cib_tree.find(element_xpath)
        if element_to_replace is None:
            raise AssertionError(
                "Cannot find '{0}' in given cib:\n{1}".format(
                    element_xpath,
                    etree_to_str(cib_tree)
                )
            )

        try:
            new_element = etree.fromstring(new_content)
        except etree.XMLSyntaxError:
            raise AssertionError(
                "Cannot put to the cib a non-xml fragment:\n'{0}'"
                .format(new_content)
            )

        parent = element_to_replace.getparent()
        for child in parent:
            if element_to_replace == child:
                index = list(parent).index(child)
                parent.remove(child)
                parent.insert(index, new_element)
                return
    return replace

def modify_cib(cib_xml, modifiers=None, resources=None):
    """
    Apply modifiers to cib_xml and return the result cib_xml

    string cib_xml -- initial cib
    list of callable modifiers -- each takes cib (etree.Element)
    string resources -- xml - resources section, current resources section will
        be replaced by this
    """
    modifiers = modifiers if modifiers else []
    if resources:
        modifiers.append(replace_element(".//resources", resources))

    if not modifiers:
        return cib_xml

    cib_tree = etree.fromstring(cib_xml)
    for modify in modifiers:
        modify(cib_tree)

    return etree_to_str(cib_tree)


def complete_state_resources(resource_status):
    for resource in resource_status.xpath(".//resource"):
        _default_element_attributes(
            resource,
            {
                "active": "true",
                "managed": "true",
                "failed": "false",
                "failure_ignored": "false",
                "nodes_running_on": "1",
                "orphaned": "false",
                "resource_agent": "ocf::heartbeat:Dummy",
                "role": "Started",
            }
        )
    for clone in resource_status.xpath(".//clone"):
        _default_element_attributes(
            clone,
            {
                "failed": "false",
                "failure_ignored": "false",
            }
        )
    for bundle in resource_status.xpath(".//bundle"):
        _default_element_attributes(
            bundle,
            {
                "type": "docker",
                "image": "image:name",
                "unique": "false",
                "failed": "false",
            }
        )
    return resource_status


def _default_element_attributes(element, default_attributes):
    for name, value in default_attributes.items():
        if name not in element.attrib:
            element.attrib[name] = value

def debug(code, force_code=None, **kwargs):
    return severities.DEBUG, code, kwargs, None

def warn(code, force_code=None, **kwargs):
    return severities.WARNING, code, kwargs, None

def error(code, force_code=None, **kwargs):
    return severities.ERROR, code, kwargs, force_code

def info(code, **kwargs):
    return severities.INFO, code, kwargs, None

def report_not_found(res_id, context_type=""):
    return (
        severities.ERROR,
        report_codes.ID_NOT_FOUND,
        {
            "context_type": context_type,
            "context_id": "",
            "id": res_id,
            "id_description": "resource/clone/master/group/bundle",
        },
        None
    )

def report_resource_not_running(resource, severity=severities.INFO):
    return (
        severity,
        report_codes.RESOURCE_DOES_NOT_RUN,
        {
            "resource_id": resource,
        },
        None
    )

def report_resource_running(resource, roles, severity=severities.INFO):
    return (
        severity,
        report_codes.RESOURCE_RUNNING_ON_NODES,
        {
            "resource_id": resource,
            "roles_with_nodes": roles,
        },
        None
    )

def report_unexpected_element(element_id, elemet_type, expected_types):
    return (
        severities.ERROR,
        report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
        {
            "id": element_id,
            "expected_types": expected_types,
            "current_type": elemet_type,
        },
        None
    )

def report_not_for_bundles(element_id):
    return report_unexpected_element(
        element_id,
        "bundle",
        ["clone", "master", "group", "primitive"]
    )

def report_wait_for_idle_timed_out(reason):
    return (
        severities.ERROR,
        report_codes.WAIT_FOR_IDLE_TIMED_OUT,
        {
            "reason": reason.strip(),
        },
        None
    )

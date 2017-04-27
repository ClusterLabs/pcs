from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.integration_lib import Call
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.xml import etree_to_str


def call_cib_load(cib):
    return [
        Call("cibadmin --local --query", cib),
    ]

def call_cib_push(cib):
    return [
        Call(
            "cibadmin --replace --verbose --xml-pipe --scope configuration",
            check_stdin=Call.create_check_stdin_xml(cib)
        ),
    ]

def call_cib_upgrade():
    return [
        Call("cibadmin --upgrade --force"),
    ]

def call_status(status):
    return [
        Call("/usr/sbin/crm_mon --one-shot --as-xml --inactive", status),
    ]

def call_wait_supported():
    return [
        Call("crm_resource -?", "--wait"),
    ]

def call_wait(timeout, retval=0, stderr=""):
    return [
        Call(
            "crm_resource --wait --timeout={0}".format(timeout),
            stderr=stderr,
            returncode=retval
        ),
    ]

def calls_cib(cib_pre, cib_post, cib_base_file=None):
    return (
        call_cib_load(cib_resources(cib_pre, cib_base_file=cib_base_file))
        +
        call_cib_push(cib_resources(cib_post, cib_base_file=cib_base_file))
    )

def calls_cib_and_status(cib_pre, status, cib_post, cib_base_file=None):
    return (
        call_cib_load(cib_resources(cib_pre, cib_base_file=cib_base_file))
        +
        call_status(state_complete(status))
        +
        call_cib_push(cib_resources(cib_post, cib_base_file=cib_base_file))
    )

def calls_cib_load_and_upgrade(cib_old_version):
    return (
        call_cib_load(cib_resources(cib_old_version))
        +
        call_cib_upgrade()
    )



def cib_resources(cib_resources_xml, cib_base_file=None):
    cib_xml = open(rc(cib_base_file or "cib-empty.xml")).read()
    cib = etree.fromstring(cib_xml)
    resources_section = cib.find(".//resources")
    for child in etree.fromstring(cib_resources_xml):
        resources_section.append(child)
    return etree_to_str(cib)


def state_complete(resource_status_xml):
    status = etree.parse(rc("crm_mon.minimal.xml")).getroot()
    resource_status = etree.fromstring(resource_status_xml)
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
    status.append(resource_status)
    return etree_to_str(status)

def _default_element_attributes(element, default_attributes):
    for name, value in default_attributes.items():
        if name not in element.attrib:
            element.attrib[name] = value


def report_not_found(res_id, context_type=""):
    return (
        severities.ERROR,
        report_codes.ID_NOT_FOUND,
        {
            "context_type": context_type,
            "context_id": "",
            "id": res_id,
            "id_description": "resource/clone/master/group",
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

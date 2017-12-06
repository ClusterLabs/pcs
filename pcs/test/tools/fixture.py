from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severities


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

def debug(code, **kwargs):
    return severities.DEBUG, code, kwargs, None

def warn(code, **kwargs):
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
            "expected_types": [
                "bundle", "clone", "group", "master", "primitive"
            ],
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

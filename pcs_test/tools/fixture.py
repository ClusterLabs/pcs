import json

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes


def state_node(
    id,
    name,
    type="member",
    online=True,
    standby=False,
    standby_onfail=False,
    maintenance=False,
    pending=False,
    unclean=False,
    shutdown=False,
    expected_up=True,
    is_dc=False,
    resources_running=0,
):
    # pylint: disable=invalid-name, too-many-arguments, redefined-builtin, unused-argument
    return locals()


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
            },
        )
    for clone in resource_status.xpath(".//clone"):
        _default_element_attributes(
            clone, {"failed": "false", "failure_ignored": "false",}
        )
    for bundle in resource_status.xpath(".//bundle"):
        _default_element_attributes(
            bundle,
            {
                "type": "docker",
                "image": "image:name",
                "unique": "false",
                "failed": "false",
            },
        )
    return resource_status


def _default_element_attributes(element, default_attributes):
    for name, value in default_attributes.items():
        if name not in element.attrib:
            element.attrib[name] = value


def report_variation(report, **_info):
    updated_info = report[2].copy()
    updated_info.update(_info)
    return report[0], report[1], updated_info, report[3]


def debug(code, **kwargs):
    return severities.DEBUG, code, kwargs, None


def warn(code, **kwargs):
    return severities.WARNING, code, kwargs, None


def error(code, force_code=None, **kwargs):
    return severities.ERROR, code, kwargs, force_code


def info(code, **kwargs):
    return severities.INFO, code, kwargs, None


class ReportStore:
    def __init__(self, names=None, reports=None):
        if not names:
            names = []

        duplicate_names = {n for n in names if names.count(n) > 1}
        if duplicate_names:
            raise AssertionError(
                "Duplicate names are not allowed in ReportStore. "
                " Found duplications:\n  '{0}'".format(
                    "'\n  '".join(duplicate_names)
                )
            )

        self.__names = names
        self.__reports = reports or []
        if len(self.__names) != len(self.__reports):
            raise AssertionError("Same count reports as names required")

    @property
    def reports(self):
        return list(self.__reports)

    def adapt(self, name, **_info):
        index = self.__names.index(name)
        return ReportStore(
            self.__names,
            [
                report if i != index else report_variation(report, **_info)
                for i, report in enumerate(self.__reports)
            ],
        )

    def adapt_multi(self, name_list, **_info):
        names, reports = zip(
            *[
                (
                    name,
                    report_variation(self[name], **_info)
                    if name in name_list
                    else self[name],
                )
                for name in self.__names
            ]
        )
        return ReportStore(list(names), list(reports))

    def info(self, name, code, **kwargs):
        return self.__append(name, info(code, **kwargs))

    def warn(self, name, code, **kwargs):
        return self.__append(name, warn(code, **kwargs))

    def error(self, name, code, force_code=None, **kwargs):
        return self.__append(name, error(code, force_code=force_code, **kwargs))

    def as_warn(self, name, as_name):
        report = self[name]
        return self.__append(as_name, warn(report[1], **report[2]))

    def copy(self, name, as_name, **_info):
        return self.__append(as_name, report_variation(self[name], **_info))

    def remove(self, *name_list):
        names, reports = zip(
            *[
                (name, self[name])
                for name in self.__names
                if name not in name_list
            ]
        )
        return ReportStore(list(names), list(reports))

    def select(self, *name_list):
        names, reports = zip(*[(name, self[name]) for name in name_list])
        return ReportStore(list(names), list(reports))

    def only(self, name, **_info):
        return ReportStore([name], [report_variation(self[name], **_info)])

    def __getitem__(self, spec):
        if not isinstance(spec, slice):
            return self.__reports[self.__names.index(spec)]

        assert spec.step is None, "Step is not supported in slicing"
        start = None if spec.start is None else self.__names.index(spec.start)
        stop = None if spec.stop is None else self.__names.index(spec.stop)

        return ReportStore(self.__names[start:stop], self.__reports[start:stop])

    def __add__(self, other):
        return ReportStore(
            # pylint: disable=protected-access
            self.__names + other.__names,
            self.__reports + other.__reports,
        )

    def __append(self, name, report):
        return ReportStore(self.__names + [name], self.__reports + [report])


def report_not_found(res_id, context_type="", expected_types=None):
    return (
        severities.ERROR,
        report_codes.ID_NOT_FOUND,
        {
            "context_type": context_type,
            "context_id": "",
            "id": res_id,
            "expected_types": [
                "bundle",
                "clone",
                "group",
                "master",
                "primitive",
            ]
            if expected_types is None
            else expected_types,
        },
        None,
    )


def report_invalid_id(_id, invalid_char, id_description="id"):
    return (
        severities.ERROR,
        report_codes.INVALID_ID_BAD_CHAR,
        {
            "id": _id,
            "id_description": id_description,
            "is_first_char": _id.index(invalid_char) == 0,
            "invalid_character": invalid_char,
        },
        None,
    )


def report_resource_not_running(resource, severity=severities.INFO):
    return (
        severity,
        report_codes.RESOURCE_DOES_NOT_RUN,
        {"resource_id": resource,},
        None,
    )


def report_resource_running(resource, roles, severity=severities.INFO):
    return (
        severity,
        report_codes.RESOURCE_RUNNING_ON_NODES,
        {"resource_id": resource, "roles_with_nodes": roles,},
        None,
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
        None,
    )


def report_not_for_bundles(element_id):
    return report_unexpected_element(
        element_id, "bundle", ["clone", "master", "group", "primitive"]
    )


def report_wait_for_idle_timed_out(reason):
    return (
        severities.ERROR,
        report_codes.WAIT_FOR_IDLE_TIMED_OUT,
        {"reason": reason.strip(),},
        None,
    )


def check_sbd_comm_success_fixture(node, watchdog, device_list):
    return dict(
        label=node,
        output=json.dumps(
            {
                "sbd": {"installed": True,},
                "watchdog": {
                    "exist": True,
                    "path": watchdog,
                    "is_supported": True,
                },
                "device_list": [
                    dict(path=dev, exist=True, block_device=True)
                    for dev in device_list
                ],
            }
        ),
        param_list=[
            ("watchdog", watchdog),
            ("device_list", json.dumps(device_list)),
        ],
    )

import json

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes

ALL_RESOURCE_XML_TAGS = ["bundle", "clone", "group", "master", "primitive"]


def debug(code, context=None, **kwargs):
    return severities.DEBUG, code, kwargs, None, context


def warn(code, context=None, **kwargs):
    return severities.WARNING, code, kwargs, None, context


def deprecation(code, context=None, **kwargs):
    return severities.DEPRECATION, code, kwargs, None, context


def error(code, force_code=None, context=None, **kwargs):
    return severities.ERROR, code, kwargs, force_code, context


def info(code, context=None, **kwargs):
    return severities.INFO, code, kwargs, None, context


class ReportStore:
    def __init__(self, names=None, reports=None):
        self.__names = names or []
        self.__reports = reports or []

        if len(self.__names) != len(self.__reports):
            raise AssertionError("Reports count doesn't match names count")

        duplicate_names = {n for n in self.__names if self.__names.count(n) > 1}
        if duplicate_names:
            raise AssertionError(
                "Duplicate names are not allowed in ReportStore. "
                " Found duplications:\n  '{0}'".format(
                    "'\n  '".join(duplicate_names)
                )
            )

    @staticmethod
    def _report_variation(report, payload):
        updated_payload = report[2].copy()
        updated_payload.update(payload)
        return report[0], report[1], updated_payload, report[3]

    @property
    def reports(self):
        return list(self.__reports)

    def adapt(self, name, **payload):
        index = self.__names.index(name)
        return ReportStore(
            self.__names,
            [
                report
                if i != index
                else self._report_variation(report, payload)
                for i, report in enumerate(self.__reports)
            ],
        )

    def adapt_multi(self, name_list, **payload):
        names, reports = zip(
            *[
                (
                    name,
                    self._report_variation(self[name], payload)
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

    def deprecation(self, name, code, **kwargs):
        return self.__append(name, deprecation(code, **kwargs))

    def error(self, name, code, force_code=None, **kwargs):
        return self.__append(name, error(code, force_code=force_code, **kwargs))

    def as_warn(self, name, as_name):
        report = self[name]
        return self.__append(as_name, warn(report[1], **report[2]))

    def copy(self, name, as_name, **payload):
        return self.__append(
            as_name, self._report_variation(self[name], payload)
        )

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

    def only(self, name, **payload):
        return ReportStore(
            [name], [self._report_variation(self[name], payload)]
        )

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


def report_not_found(
    res_id, context_type="", expected_types=None, context_id=""
):
    return (
        severities.ERROR,
        report_codes.ID_NOT_FOUND,
        {
            "context_type": context_type,
            "context_id": context_id,
            "id": res_id,
            "expected_types": (
                ALL_RESOURCE_XML_TAGS
                if expected_types is None
                else expected_types
            ),
        },
        None,
    )


def report_not_resource_or_tag(element_id, context_type="cib", context_id=""):
    return report_not_found(
        element_id,
        context_type=context_type,
        expected_types=sorted(ALL_RESOURCE_XML_TAGS + ["tag"]),
        context_id=context_id,
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


def report_id_already_exist(_id):
    return (
        severities.ERROR,
        report_codes.ID_ALREADY_EXISTS,
        {
            "id": _id,
        },
    )


def report_resource_not_running(resource, severity=severities.INFO):
    return (
        severity,
        report_codes.RESOURCE_DOES_NOT_RUN,
        {
            "resource_id": resource,
        },
        None,
    )


def report_resource_running(resource, roles, severity=severities.INFO):
    return (
        severity,
        report_codes.RESOURCE_RUNNING_ON_NODES,
        {
            "resource_id": resource,
            "roles_with_nodes": roles,
        },
        None,
    )


def report_unexpected_element(element_id, element_type, expected_types):
    return (
        severities.ERROR,
        report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
        {
            "id": element_id,
            "expected_types": expected_types,
            "current_type": element_type,
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
        {
            "reason": reason.strip(),
        },
        None,
    )


def check_sbd_comm_success_fixture(node, watchdog, device_list):
    return dict(
        label=node,
        output=json.dumps(
            {
                "sbd": {
                    "installed": True,
                },
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

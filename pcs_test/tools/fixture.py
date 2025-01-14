import json
from collections import Counter
from typing import (
    Any,
    Generic,
    Mapping,
    NamedTuple,
    Optional,
    TypeVar,
    overload,
)

from pcs.common import reports
from pcs.common.str_tools import format_list

ALL_RESOURCE_XML_TAGS = ["bundle", "clone", "group", "master", "primitive"]


# Previously, a report item fixture was a plain tuple. That was, however, not
# the best to work with when access to specific indexes was needed. To provide
# a 1-to-1 replacement with more friendly interface, a NamedTuple was chosen
# instead of a dataclass. Order of the attributes is the same as in the
# original tuple, so it may be not the best, but it works without any changes
# to related code.
class ReportItemFixture(NamedTuple):
    severity: reports.types.SeverityLevel
    code: reports.types.MessageCode
    payload: Mapping[str, Any]
    force_code: Optional[reports.types.ForceCode]
    context: Optional[Mapping[str, Any]]

    def to_warn(self):
        return warn(self.code, self.context, **self.payload)

    def adapt(self, **payload):
        updated_payload = self.payload.copy()
        updated_payload.update(**payload)
        return type(self)(
            self.severity,
            self.code,
            updated_payload,
            self.force_code,
            self.context,
        )


def debug(
    code: reports.types.MessageCode,
    context: Optional[Mapping[str, Any]] = None,
    **kwargs,
) -> ReportItemFixture:
    return ReportItemFixture(
        reports.ReportItemSeverity.DEBUG, code, kwargs, None, context
    )


def warn(
    code: reports.types.MessageCode,
    context: Optional[Mapping[str, Any]] = None,
    **kwargs,
) -> ReportItemFixture:
    return ReportItemFixture(
        reports.ReportItemSeverity.WARNING, code, kwargs, None, context
    )


def deprecation(
    code: reports.types.MessageCode,
    context: Optional[Mapping[str, Any]] = None,
    **kwargs,
) -> ReportItemFixture:
    return ReportItemFixture(
        reports.ReportItemSeverity.DEPRECATION, code, kwargs, None, context
    )


def error(
    code: reports.types.MessageCode,
    force_code: Optional[reports.types.ForceCode] = None,
    context: Optional[Mapping[str, Any]] = None,
    **kwargs,
) -> ReportItemFixture:
    return ReportItemFixture(
        reports.ReportItemSeverity.ERROR, code, kwargs, force_code, context
    )


def info(
    code: reports.types.MessageCode,
    context: Optional[Mapping[str, Any]] = None,
    **kwargs,
) -> ReportItemFixture:
    return ReportItemFixture(
        reports.ReportItemSeverity.INFO, code, kwargs, None, context
    )


T = TypeVar("T")


class NameValueSequence(Generic[T]):
    def __init__(
        self,
        name_list: Optional[list[Optional[str]]] = None,
        value_list: Optional[list[T]] = None,
    ):
        self.__names: list[Optional[str]] = name_list or []
        self.__values: list[T] = value_list or []

        if len(self.__names) != len(self.__values):
            raise AssertionError("Values count doesn't match names count")

        name_counter = Counter(self.__names)
        duplicate_names = [
            n for n in name_counter if n is not None and name_counter[n] > 1
        ]
        if duplicate_names:
            raise AssertionError(
                f"Duplicate names are not allowed in {type(self).__name__}. "
                f"Found duplications:\n  {format_list(duplicate_names)}"
            )

    @property
    def names(self) -> list[Optional[str]]:
        return list(self.__names)

    @property
    def values(self) -> list[T]:
        return list(self.__values)

    def append(self, value: T, name: Optional[str] = None) -> None:
        """
        Append new value with the specified name at the end of sequence

        value -- new value
        name -- new value name
        """
        self.__check_name(name)
        self.__names.append(name)
        self.__values.append(value)

    def prepend(self, value: T, name: Optional[str] = None) -> None:
        """
        Insert new value with the specified name at the start of sequence

        value -- new value
        name -- new value name
        """
        self.__check_name(name)
        self.__names.insert(0, name)
        self.__values.insert(0, value)

    def insert(self, before: str, value: T, name: Optional[str] = None) -> None:
        """
        Insert new value before a specified value

        before -- name of a value before which the new one will be placed
        value -- the new value
        name -- name of the new value
        """
        self.__check_name(name)
        index = self.__get_index(before)
        self.__names.insert(index, name)
        self.__values.insert(index, value)

    def remove(self, *name_list: str) -> None:
        """
        Remove values with specified names

        name_list -- names of values to be removed
        """
        for name in name_list:
            index = self.__get_index(name)
            del self.__names[index]
            del self.__values[index]

    def replace(
        self, name: str, value: T, new_name: Optional[str] = None
    ) -> None:
        """
        Replace a value specified by its name

        name -- name of a value to be replaced
        value -- new value
        new_name -- new name of the value, use 'name' if not specified
        """
        if new_name is not None and new_name != name and name in self.__names:
            raise AssertionError(f"Name '{new_name}' already present in {self}")
        for i, current_name in enumerate(self.__names):
            if current_name == name:
                self.__values[i] = value
                if new_name:
                    self.__names[i] = new_name
                return
        raise IndexError(self.__index_error(name))

    def trim_before(self, name: str) -> None:
        """
        Remove a value with the specified name and all values after it

        name -- name of a value to trim at
        """
        index = self.__get_index(name)
        self.__names = self.__names[:index]
        self.__values = self.__values[:index]

    def copy(self) -> "NameValueSequence":
        return type(self)(self.names, self.values)

    def __get_index(self, name: str) -> int:
        try:
            return self.__names.index(name)
        except ValueError as e:
            raise IndexError(self.__index_error(name)) from e

    def __index_error(self, index: str) -> str:
        return f"'{index}' not present in {self}"

    def __check_name(self, name: Optional[str]) -> None:
        if name is not None and name in self.__names:
            raise AssertionError(f"Name '{name}' already present in {self}")

    @overload
    def __getitem__(self, spec: str) -> T:
        pass

    @overload
    def __getitem__(self, spec: slice) -> "NameValueSequence":
        pass

    def __getitem__(self, spec):
        if not isinstance(spec, slice):
            try:
                return self.__values[self.__names.index(spec)]
            except ValueError as e:
                raise IndexError(self.__index_error(spec)) from e

        assert spec.step is None, "Step is not supported in slicing"
        start = None if spec.start is None else self.__names.index(spec.start)
        stop = None if spec.stop is None else self.__names.index(spec.stop)
        return type(self)(self.__names[start:stop], self.__values[start:stop])

    def __setitem__(self, name: str, value: T) -> None:
        return (
            self.replace(name, value)
            if name in self.__names
            else self.append(value, name)
        )

    def __delitem__(self, name: str) -> None:
        index = self.__get_index(name)
        del self.__names[index]
        del self.__values[index]

    def __add__(self, other: "NameValueSequence") -> "NameValueSequence":
        my_name = type(self).__name__
        other_name = type(other).__name__
        assert isinstance(other, type(self)), (
            f"Can only concatenate {my_name} with {my_name}, not {other_name}"
        )

        return type(self)(
            self.names + other.names,
            self.values + other.values,
        )

    def __str__(self) -> str:
        return f"{type(self).__name__} {hex(id(self))}:\n" + "\n".join(
            [
                f" {index:3}. {item[0] if item[0] else '<unnamed>'}: {item[1]}"
                for index, item in enumerate(
                    zip(self.__names, self.__values, strict=False), 1
                )
            ]
        )


class ReportSequenceBuilder:
    def __init__(self, store: Optional[NameValueSequence] = None):
        self._store = store or NameValueSequence()

    @property
    def fixtures(self) -> NameValueSequence:
        return self._store

    def info(
        self,
        code: reports.types.MessageCode,
        _name: Optional[str] = None,
        **kwargs,
    ) -> "ReportSequenceBuilder":
        self._store.append(info(code, **kwargs), _name)
        return self

    def warn(
        self,
        code: reports.types.MessageCode,
        _name: Optional[str] = None,
        **kwargs,
    ) -> "ReportSequenceBuilder":
        self._store.append(warn(code, **kwargs), _name)
        return self

    def deprecation(
        self,
        code: reports.types.MessageCode,
        _name: Optional[str] = None,
        **kwargs,
    ) -> "ReportSequenceBuilder":
        self._store.append(deprecation(code, **kwargs), _name)
        return self

    def error(
        self,
        code: reports.types.MessageCode,
        force_code: Optional[reports.types.ForceCode] = None,
        _name: Optional[str] = None,
        **kwargs,
    ) -> "ReportSequenceBuilder":
        self._store.append(error(code, force_code=force_code, **kwargs), _name)
        return self


def report_not_found(
    res_id, context_type="", expected_types=None, context_id=""
):
    return error(
        reports.codes.ID_NOT_FOUND,
        context_type=context_type,
        context_id=context_id,
        id=res_id,
        expected_types=(
            ALL_RESOURCE_XML_TAGS if expected_types is None else expected_types
        ),
    )


def report_not_resource_or_tag(element_id, context_type="cib", context_id=""):
    return report_not_found(
        element_id,
        context_type=context_type,
        expected_types=sorted(ALL_RESOURCE_XML_TAGS + ["tag"]),
        context_id=context_id,
    )


def report_invalid_id(_id, invalid_char, id_description="id"):
    return error(
        reports.codes.INVALID_ID_BAD_CHAR,
        id=_id,
        id_description=id_description,
        is_first_char=(_id.index(invalid_char) == 0),
        invalid_character=invalid_char,
    )


def report_id_already_exist(_id):
    return error(
        reports.codes.ID_ALREADY_EXISTS,
        id=_id,
    )


def report_resource_not_running(
    resource, severity=reports.ReportItemSeverity.INFO
):
    return ReportItemFixture(
        severity,
        reports.codes.RESOURCE_DOES_NOT_RUN,
        dict(resource_id=resource),
        None,
        None,
    )


def report_resource_running(
    resource, roles, severity=reports.ReportItemSeverity.INFO
):
    return ReportItemFixture(
        severity,
        reports.codes.RESOURCE_RUNNING_ON_NODES,
        dict(
            resource_id=resource,
            roles_with_nodes=roles,
        ),
        None,
        None,
    )


def report_unexpected_element(element_id, element_type, expected_types):
    return error(
        reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
        id=element_id,
        expected_types=expected_types,
        current_type=element_type,
    )


def report_not_for_bundles(element_id):
    return report_unexpected_element(
        element_id, "bundle", ["clone", "master", "group", "primitive"]
    )


def report_wait_for_idle_timed_out(reason):
    return error(reports.codes.WAIT_FOR_IDLE_TIMED_OUT, reason=reason.strip())


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

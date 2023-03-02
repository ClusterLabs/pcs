import json
from collections import Counter
from typing import (
    Any,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    overload,
)

from pcs.common import reports
from pcs.common.str_tools import format_list
from pcs.common.types import (
    StringCollection,
    StringSequence,
)

ALL_RESOURCE_XML_TAGS = ["bundle", "clone", "group", "master", "primitive"]


class ReportItemFixture(NamedTuple):
    severity: reports.types.SeverityLevel
    code: reports.types.MessageCode
    payload: Mapping[str, Any]
    force_code: reports.types.ForceCode
    context: Mapping[str, Any]

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
    force_code: Optional[Mapping[str, Any]] = None,
    context=None,
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
C = TypeVar("C", bound="FixtureStore")


class FixtureStore:
    def __init__(
        self,
        name_list: Optional[StringSequence] = None,
        fixture_list: Optional[Sequence[T]] = None,
    ):
        self.__names = name_list or []
        self.__fixtures = fixture_list or []

        if len(self.__names) != len(self.__fixtures):
            raise AssertionError("Fixtures count doesn't match names count")

        name_counter = Counter(self.__names)
        del name_counter[None]
        duplicate_names = {n for n in name_counter if name_counter[n] > 1}
        if duplicate_names:
            raise AssertionError(
                f"Duplicate names are not allowed in {type(self).__name__}. "
                f"Found duplications:\n  {format_list(duplicate_names)}"
            )

    @property
    def fixtures(self) -> list[T]:
        return list(self.__fixtures)

    @property
    def names(self) -> list[str]:
        return list(self.__names)

    def append(self, fixture: T, name: Optional[str] = None) -> None:
        """
        Append new fixture with the specified name at the end of store

        fixture -- new fixture
        name -- new fixture name
        """
        self.__check_name(name)
        self.__names.append(name)
        self.__fixtures.append(fixture)

    def prepend(self, fixture: T, name: Optional[str] = None) -> None:
        """
        Insert new fixture with the specified name at the start of store

        fixture -- new fixture
        name -- new fixture name
        """
        self.__check_name(name)
        self.__names.insert(0, name)
        self.__fixtures.insert(0, fixture)

    def insert(
        self, before: str, fixture: T, name: Optional[str] = None
    ) -> None:
        """
        Insert new fixture before a specified fixture

        before -- name of a fixture before which the new one will be placed
        fixture -- the new fixture
        name -- name of the new fixture
        """
        self.__check_name(name)
        index = self.__get_index(before)
        self.__names.insert(index, name)
        self.__fixtures.insert(index, fixture)

    def remove(self, *name_list: StringCollection) -> None:
        """
        Remove fixtures with specified names

        name_list -- names of fixtures to be removed
        """
        for name in name_list:
            index = self.__get_index(name)
            del self.__names[index]
            del self.__fixtures[index]

    def replace(
        self, name: str, fixture: T, new_name: Optional[str] = None
    ) -> None:
        """
        Replace a fixture specified by its name

        name -- name of a fixture to be replaced
        fixture -- new fixture
        new_name -- new name of the fixture, use 'name' if not specified
        """
        if new_name is not None and new_name != name and name in self.__names:
            raise AssertionError(f"Name '{new_name}' already present in {self}")
        for i, current_name in enumerate(self.__names):
            if current_name == name:
                self.__fixtures[i] = fixture
                if new_name:
                    self.__names[i] = new_name
                return
        raise IndexError(self.__index_error(name))

    def trim_before(self, name: str) -> None:
        """
        Remove a fixture with the specified name and all fixtures after it

        name -- name of a fixture to trim at
        """
        index = self.__get_index(name)
        self.__names = self.__names[:index]
        self.__fixtures = self.__fixtures[:index]

    def place(
        self,
        fixture: T,
        name: Optional[str] = None,
        *,
        before: Optional[str] = None,
        instead: Optional[str] = None,
    ):
        """
        Place a new fixture

        fixture -- the new fixture
        name -- name of the new fixture
        before -- place the new fixture before a fixture with this name
        instead -- place the new fixture instead of a fixture with this name
        """
        if before and instead:
            raise AssertionError(
                f"Cannot use both 'before' ({before}) and 'instead' ({instead})"
            )

        if before:
            return self.insert(before, fixture, name)
        if instead:
            return self.replace(instead, fixture, name)
        return self.append(fixture, name)

    def copy(self) -> C:
        return type(self)(self.names, self.fixtures)

    def __get_index(self, name: str) -> int:
        try:
            return self.__names.index(name)
        except ValueError as e:
            raise IndexError(self.__index_error(name)) from e

    def __index_error(self, index: str) -> str:
        return f"'{index}' not present in {self}"

    def __check_name(self, name) -> None:
        if name is not None and name in self.__names:
            raise AssertionError(f"Name '{name}' already present in {self}")

    @overload
    def __getitem__(self, spec: str) -> T:
        pass

    @overload
    def __getitem__(self, spec: slice) -> C:
        pass

    def __getitem__(self, spec):
        if not isinstance(spec, slice):
            try:
                return self.__fixtures[self.__names.index(spec)]
            except ValueError as e:
                raise IndexError(self.__index_error(spec)) from e

        assert spec.step is None, "Step is not supported in slicing"
        start = None if spec.start is None else self.__names.index(spec.start)
        stop = None if spec.stop is None else self.__names.index(spec.stop)
        return type(self)(self.__names[start:stop], self.__fixtures[start:stop])

    def __setitem__(self, name: str, fixture: T) -> None:
        return (
            self.replace(name, fixture)
            if name in self.__names
            else self.append(fixture, name)
        )

    def __delitem__(self, name: str) -> None:
        index = self.__get_index(name)
        del self.__names[index]
        del self.__fixtures[index]

    def __add__(self, other: "FixtureStore") -> C:
        my_name = type(self).__name__
        other_name = type(other).__name__
        assert isinstance(
            other, type(self)
        ), f"Can only concatenate {my_name} with {my_name}, not {other_name}"

        return type(self)(
            self.names + other.names,
            self.fixtures + other.fixtures,
        )

    def __str__(self) -> str:
        return f"{type(self).__name__} {hex(id(self))}:\n" + "\n".join(
            [
                f" {index:3}. {item[0] if item[0] else '<unnamed>'}: {item[1]}"
                for index, item in enumerate(
                    zip(self.__names, self.__fixtures), 1
                )
            ]
        )


class ReportSequenceBuilder:
    def __init__(self, store: Optional[FixtureStore] = None):
        self._store = store or FixtureStore()

    @property
    def fixtures(self) -> FixtureStore:
        return self._store

    def info(
        self,
        code: reports.types.MessageCode,
        _name: Optional[str] = None,
        **kwargs,
    ) -> "ReportStore":
        self._store.append(info(code, **kwargs), _name)
        return self

    def warn(
        self,
        code: reports.types.MessageCode,
        _name: Optional[str] = None,
        **kwargs,
    ) -> "ReportStore":
        self._store.append(warn(code, **kwargs), _name)
        return self

    def deprecation(
        self,
        code: reports.types.MessageCode,
        _name: Optional[str] = None,
        **kwargs,
    ) -> "ReportStore":
        self._store.append(deprecation(code, **kwargs), _name)
        return self

    def error(
        self,
        code: reports.types.MessageCode,
        force_code: Optional[reports.types.ForceCode] = None,
        _name: Optional[str] = None,
        **kwargs,
    ) -> "ReportStore":
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

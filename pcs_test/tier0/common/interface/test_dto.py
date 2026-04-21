import importlib
import pkgutil
from collections.abc import Sequence
from dataclasses import dataclass, field, is_dataclass
from typing import Any, Optional
from unittest import TestCase

from dacite.exceptions import WrongTypeError

import pcs
from pcs.common.interface.dto import (
    DataTransferObject,
    PayloadConversionError,
    from_dict,
    meta,
    to_dict,
)
from pcs.common.types import CorosyncNodeAddressType


def _import_all(_path):
    # arbitrary prefix so it doesn't interact with real import in real tests
    for module_finder, module_name, is_pkg in pkgutil.walk_packages(
        _path, prefix="pcs."
    ):
        del module_finder, is_pkg
        if module_name.startswith("pcs.snmp."):
            continue
        importlib.import_module(module_name)


def _all_subclasses(cls):
    subclasses = set(cls.__subclasses__())
    return subclasses.union({s for c in subclasses for s in _all_subclasses(c)})


class DatatransferObjectTest(TestCase):
    def test_has_all_subclasses_are_dataclasses(self):
        _import_all(pcs.__path__)
        for cls in _all_subclasses(DataTransferObject):
            self.assertTrue(is_dataclass(cls), f"{cls} is not a dataclass")


@dataclass
class MyDto1(DataTransferObject):
    field_a: int
    field_b: int = field(metadata=meta(name="field-b"))
    field_c: int


@dataclass
class MyDto2(DataTransferObject):
    field_d: int
    field_e: MyDto1 = field(metadata=meta(name="field-e"))
    field_f: CorosyncNodeAddressType  # tests converting an Enum class


@dataclass
class MyDto3(DataTransferObject):
    field_g: MyDto2 = field(metadata=meta(name="field-g"))
    field_h: list[MyDto2]
    field_i: int = field(metadata=meta(name="field-i"))


@dataclass
class TypeHooksDto(DataTransferObject):
    list_of_tuple_str_str_str: list[tuple[str, str, str]]
    sequence_of_tuple_str_str: Sequence[tuple[str, str]]
    optional_tuple_str_str: Optional[tuple[str, str]]


class DictName(TestCase):
    maxDiff = None
    simple_dto = MyDto1(1, 2, 3)
    simple_dict = {"field_a": 1, "field-b": 2, "field_c": 3}
    nested_dto = MyDto3(
        MyDto2(0, MyDto1(1, 2, 3), CorosyncNodeAddressType.IPV4),
        [
            MyDto2(5, MyDto1(6, 7, 8), CorosyncNodeAddressType.FQDN),
            MyDto2(
                10, MyDto1(11, 12, 13), CorosyncNodeAddressType.UNRESOLVABLE
            ),
        ],
        15,
    )
    nested_dict = {
        "field-g": {
            "field_d": 0,
            "field-e": {"field_a": 1, "field-b": 2, "field_c": 3},
            "field_f": "IPv4",
        },
        "field_h": [
            {
                "field_d": 5,
                "field-e": {"field_a": 6, "field-b": 7, "field_c": 8},
                "field_f": "FQDN",
            },
            {
                "field_d": 10,
                "field-e": {
                    "field_a": 11,
                    "field-b": 12,
                    "field_c": 13,
                },
                "field_f": "unresolvable",
            },
        ],
        "field-i": 15,
    }

    def test_simple_to_dict(self):
        self.assertEqual(to_dict(self.simple_dto), self.simple_dict)

    def test_simple_from_dict(self):
        self.assertEqual(self.simple_dto, from_dict(MyDto1, self.simple_dict))

    def test_nested_to_dict(self):
        self.assertEqual(to_dict(self.nested_dto), self.nested_dict)

    def test_nested_from_dict(self):
        self.assertEqual(self.nested_dto, from_dict(MyDto3, self.nested_dict))


class FromDictConversion(TestCase):
    _valid_payload = dict(
        list_of_tuple_str_str_str=[["a", "b", "c"]],
        sequence_of_tuple_str_str=[["a", "b"]],
        optional_tuple_str_str=["a", "b"],
    )
    _valid_dto = TypeHooksDto(
        list_of_tuple_str_str_str=[("a", "b", "c")],
        sequence_of_tuple_str_str=[("a", "b")],
        optional_tuple_str_str=("a", "b"),
    )

    def test_success(self):
        self.assertEqual(
            self._valid_dto,
            from_dict(TypeHooksDto, self._valid_payload),
        )

    def test_success_optional_none(self):
        payload = {**self._valid_payload, "optional_tuple_str_str": None}
        dto = from_dict(TypeHooksDto, payload)
        self.assertIsNone(dto.optional_tuple_str_str)

    def test_fail_on_wrong_length(self):
        cases = {
            "list_of_tuple_str_str_str": [["a", "b", "c", "d"]],
            "sequence_of_tuple_str_str": [["a", "b", "c"]],
            "optional_tuple_str_str": ["a", "b", "c"],
        }
        for field_name, bad_value in cases.items():
            with self.subTest(field=field_name):
                payload = {**self._valid_payload, field_name: bad_value}
                # Not worth testing exception message as dacite produces
                # misleading messages for type hook failures
                with self.assertRaises(WrongTypeError):
                    from_dict(TypeHooksDto, payload)

    def test_fail_on_wrong_item_type(self):
        cases = {
            "list_of_tuple_str_str_str": [["a", "b", 1]],
            "sequence_of_tuple_str_str": [["a", 1]],
            "optional_tuple_str_str": ["a", 1],
        }
        for field_name, bad_value in cases.items():
            with self.subTest(field=field_name):
                payload = {**self._valid_payload, field_name: bad_value}
                # Not worth testing exception message as dacite produces
                # misleading messages for type hook failures
                with self.assertRaises(WrongTypeError):
                    from_dict(TypeHooksDto, payload)

    def test_fail_on_plain_string(self):
        cases = {
            "list_of_tuple_str_str_str": ["a b c"],
            "sequence_of_tuple_str_str": ["a b"],
            "optional_tuple_str_str": "a b",
        }
        for field_name, bad_value in cases.items():
            with self.subTest(field=field_name):
                payload = {**self._valid_payload, field_name: bad_value}
                # Not worth testing exception message as dacite produces
                # misleading messages for type hook failures
                with self.assertRaises(WrongTypeError):
                    from_dict(TypeHooksDto, payload)


@dataclass
class EnumDto(DataTransferObject):
    field_a: CorosyncNodeAddressType
    field_b: list[CorosyncNodeAddressType]
    field_c: dict[str, CorosyncNodeAddressType]
    field_d: Optional[CorosyncNodeAddressType]


class FromDictEnumConversion(TestCase):
    _VALID_PAYLOAD = dict(
        field_a="IPv4",
        field_b=["IPv6", "FQDN"],
        field_c=dict(foo="unresolvable"),
        field_d="IPv4",
    )

    def test_success_from_raw_values(self):
        self.assertEqual(
            EnumDto(
                CorosyncNodeAddressType.IPV4,
                [CorosyncNodeAddressType.IPV6, CorosyncNodeAddressType.FQDN],
                {"foo": CorosyncNodeAddressType.UNRESOLVABLE},
                CorosyncNodeAddressType.IPV4,
            ),
            from_dict(EnumDto, self._VALID_PAYLOAD),
        )

    def test_error_bad_value(self):
        bad_values = dict(
            field_a="bad value",
            field_b=["IPv6", "bad value"],
            field_c=dict(foo="bad value"),
            field_d="bad value",
        )

        for field_name, bad_value in bad_values.items():
            with self.subTest(field=field_name):
                payload = {**self._VALID_PAYLOAD, field_name: bad_value}
                with self.assertRaises(PayloadConversionError):
                    from_dict(EnumDto, payload)


@dataclass
class DtoWithAny(DataTransferObject):
    field_a: str
    field_b: Any


class UnexpectedTypes(TestCase):
    def test_any_is_list(self):
        dto = DtoWithAny("a", [1, 2])
        self.assertEqual(dict(field_a="a", field_b=[1, 2]), to_dict(dto))

    def test_any_is_dict(self):
        dto = DtoWithAny("a", {1: "1", 2: "2"})
        self.assertEqual(
            dict(field_a="a", field_b={1: "1", 2: "2"}), to_dict(dto)
        )

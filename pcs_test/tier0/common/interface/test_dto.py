import pkgutil
from dataclasses import (
    dataclass,
    field,
    is_dataclass,
)
from typing import (
    Any,
    List,
)
from unittest import TestCase

import pcs
from pcs.common.interface.dto import (
    DataTransferObject,
    from_dict,
    meta,
    to_dict,
)
from pcs.common.types import CorosyncNodeAddressType


def _import_all(_path):
    # arbitrary prefix so it doesn't iteract with real import in real tests
    for module_finder, module_name, is_pkg in pkgutil.walk_packages(
        _path, prefix="_pcs."
    ):
        if module_name.startswith("_pcs.snmp."):
            continue
        del is_pkg
        module_finder.find_spec(module_name).loader.load_module(module_name)


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
    field_h: List[MyDto2]
    field_i: int = field(metadata=meta(name="field-i"))


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

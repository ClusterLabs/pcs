import importlib
import inspect
import pkgutil
from collections.abc import Container, Iterable
from dataclasses import fields, is_dataclass
from enum import EnumType
from typing import get_args, get_origin, get_type_hints
from unittest import TestCase

import pcs.lib.commands as lib_command_package
from pcs.common.interface.dto import DTO_TYPE_HOOKS_MAP
from pcs.daemon.async_tasks.worker.command_mapping import COMMAND_MAP


def prohibited_types_used(_type, prohibited_types):
    if _type in prohibited_types:
        return True
    generic = get_origin(_type)
    if generic:
        if generic in prohibited_types:
            return True
        return any(
            prohibited_types_used(arg, prohibited_types)
            for arg in get_args(_type)
        )
    if is_dataclass(_type):
        # resolve forward references in type hints, because type-detecting
        # functions do not work with forward references
        type_hints = get_type_hints(_type)
        return any(
            prohibited_types_used(type_hints[field.name], prohibited_types)
            for field in fields(_type)
        )
    return False


def _find_disallowed_types(_type, allowed_types, _seen=None):
    if _seen is None:
        _seen = set()
    type_id = id(_type)
    if type_id in _seen:
        return set()
    _seen.add(type_id)

    disallowed = set()
    generic = get_origin(_type)

    if generic is None:
        if isinstance(_type, EnumType) and _type not in allowed_types:
            disallowed.add(_type)
    else:
        # tuples apart from tuple with ellipsis must have explicit type hooks
        if (
            generic is tuple
            and Ellipsis not in get_args(_type)
            and _type not in allowed_types
        ):
            disallowed.add(_type)
        for arg in get_args(_type):
            disallowed.update(_find_disallowed_types(arg, allowed_types, _seen))

    if is_dataclass(_type):
        # resolve forward references in type hints, because type-detecting
        # functions do not work with forward references
        type_hints = get_type_hints(_type)
        for field in fields(_type):
            disallowed.update(
                _find_disallowed_types(
                    type_hints[field.name], allowed_types, _seen
                )
            )
    return disallowed


class DaciteTypingCompatibilityTest(TestCase):
    def test_all(self):
        prohibited_types = (Iterable, Container)
        prohibited_types_normalized = []
        for _type in prohibited_types:
            _type_origin = get_origin(_type)
            prohibited_types_normalized.append(
                _type_origin if _type_origin is not None else _type
            )
        for cmd_name, cmd in COMMAND_MAP.items():
            for param in list(inspect.signature(cmd.cmd).parameters.values())[
                1:
            ]:
                if param.annotation != inspect.Parameter.empty:
                    self.assertFalse(
                        prohibited_types_used(
                            param.annotation, prohibited_types_normalized
                        ),
                        f"Prohibited type used in command: {cmd_name}; argument: {param}; prohibited_types: {prohibited_types}",
                    )

    def test_check_type_hooks_map_types_in_commands(self):
        allowed_types = set(DTO_TYPE_HOOKS_MAP.keys())
        for cmd_name, cmd in COMMAND_MAP.items():
            for param in list(inspect.signature(cmd.cmd).parameters.values())[
                1:
            ]:
                if param.annotation == inspect.Parameter.empty:
                    continue
                disallowed = _find_disallowed_types(
                    param.annotation, allowed_types
                )
                self.assertFalse(
                    disallowed,
                    f"Type(s) {disallowed} in "
                    f"command: {cmd_name}; "
                    f"argument: {param}; "
                    f"not covered by DTO_TYPE_HOOKS_MAP.keys(): "
                    f"{allowed_types}. "
                    "Add the missing type(s) to DTO_TYPE_HOOKS_MAP "
                    "and update FromDictConversion tests in "
                    "test_dto.py accordingly.",
                )


def _find_disallowed_return_type_enums(_type, allowed_enum_bases, _seen=None):
    disallowed = set()

    if _seen is None:
        _seen = set()
    type_id = id(_type)
    if type_id in _seen:
        return disallowed
    _seen.add(type_id)

    generic = get_origin(_type)
    if generic is None:
        if isinstance(_type, EnumType) and not any(
            issubclass(_type, base) for base in allowed_enum_bases
        ):
            disallowed.add(_type)
    else:
        for arg in get_args(_type):
            disallowed.update(
                _find_disallowed_return_type_enums(
                    arg, allowed_enum_bases, _seen
                )
            )

    if is_dataclass(_type):
        # resolve forward references in type hints, because type-detecting
        # functions do not work with forward references
        type_hints = get_type_hints(_type)
        for field in fields(_type):
            disallowed.update(
                _find_disallowed_return_type_enums(
                    type_hints[field.name], allowed_enum_bases, _seen
                )
            )

    return disallowed


class ReturnTypeCompatibilityTest(TestCase):
    def test_return_value_enums(self):
        allowed_enum_bases = (int, str, float)

        for _, module_name, _ in pkgutil.walk_packages(
            lib_command_package.__path__, lib_command_package.__name__ + "."
        ):
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue

            for cmd_name, cmd in inspect.getmembers(module, inspect.isfunction):
                if cmd_name.startswith("_"):
                    continue

                return_type = inspect.signature(cmd).return_annotation
                if (
                    return_type == inspect.Parameter.empty
                    or return_type is None
                ):
                    continue

                with self.subTest(value=cmd_name):
                    disallowed = _find_disallowed_return_type_enums(
                        return_type, allowed_enum_bases
                    )
                    if disallowed:
                        raise AssertionError(
                            f"Type(s) {disallowed} in return type of command: {cmd_name}\n"
                            f"All Enums must also be subclasses of {allowed_enum_bases} "
                            "to allow for easy serialization.\n"
                            "Either use 'pcs.common.types.AutoNameEnum' or make sure "
                            "your enum is also a subclass of one of the allowed "
                            "types: use enum.StrEnum for strings, or "
                            "MyEnum(<allowed_type>, Enum) for other types"
                        )

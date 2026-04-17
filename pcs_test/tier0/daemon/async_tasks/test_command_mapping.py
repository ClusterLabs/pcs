import inspect
from dataclasses import (
    fields,
    is_dataclass,
)
from enum import EnumType
from typing import (
    Container,
    Iterable,
    get_args,
    get_origin,
    get_type_hints,
)
from unittest import TestCase

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


def _get_generic(annotation):
    return getattr(annotation, "__origin__", None)


def _find_disallowed_types(
    _type, allowed_types, hooked_generic_origins, _seen=None
):
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
        # flag as disallowed if types' origin needs a hook but this specific
        # instantiation does not have a type hook
        # e.g. we found a tuple, that does not have explicit type hook, so
        # we flag it as disallowed
        if (
            generic in hooked_generic_origins
            and Ellipsis not in get_args(_type)
            and _type not in allowed_types
        ):
            disallowed.add(_type)
        for arg in get_args(_type):
            disallowed.update(
                _find_disallowed_types(
                    arg, allowed_types, hooked_generic_origins, _seen
                )
            )

    if is_dataclass(_type):
        # resolve forward references in type hints, because type-detecting
        # functions do not work with forward references
        type_hints = get_type_hints(_type)
        for field in fields(_type):
            disallowed.update(
                _find_disallowed_types(
                    type_hints[field.name],
                    allowed_types,
                    hooked_generic_origins,
                    _seen,
                )
            )
    return disallowed


class DaciteTypingCompatibilityTest(TestCase):
    def test_all(self):
        prohibited_types = (Iterable, Container)
        prohibited_types_normalized = [
            get_origin(_type) for _type in prohibited_types
        ]
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
        hooked_generic_origins = {
            origin
            for _type in allowed_types
            if (origin := get_origin(_type)) is not None
        }
        for cmd_name, cmd in COMMAND_MAP.items():
            for param in list(inspect.signature(cmd.cmd).parameters.values())[
                1:
            ]:
                if param.annotation == inspect.Parameter.empty:
                    continue
                disallowed = _find_disallowed_types(
                    param.annotation, allowed_types, hooked_generic_origins
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

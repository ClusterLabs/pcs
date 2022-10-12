import inspect
from dataclasses import (
    fields,
    is_dataclass,
)
from typing import (
    Container,
    Iterable,
    get_args,
    get_origin,
)
from unittest import TestCase

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
        return any(
            prohibited_types_used(field.type, prohibited_types)
            for field in fields(_type)
        )
    return False


def _get_generic(annotation):
    return getattr(annotation, "__origin__", None)


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

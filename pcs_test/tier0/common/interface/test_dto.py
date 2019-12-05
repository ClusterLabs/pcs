import pkgutil
from dataclasses import is_dataclass
from unittest import TestCase

import pcs
from pcs.common.interface.dto import DataTransferObject


def _import_all(_path):
    # arbitrary prefix so it doesn't iteract with real import in real tests
    for loader, module_name, is_pkg in pkgutil.walk_packages(
        _path, prefix="_pcs."
    ):
        if module_name.startswith("_pcs.snmp."):
            continue
        del is_pkg
        loader.find_module(module_name).load_module(module_name)


def _all_subclasses(cls):
    subclasses = set(cls.__subclasses__())
    return subclasses.union(
        {s for c in subclasses for s in _all_subclasses(c)}
    )


class DatatransferObjectTest(TestCase):
    def test_has_all_subclasses_are_dataclasses(self):
        _import_all(pcs.__path__)
        for cls in _all_subclasses(DataTransferObject):
            self.assertTrue(is_dataclass(cls), f"{cls} is not a dataclass")

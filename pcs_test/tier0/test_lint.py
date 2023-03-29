import os
import re
from unittest import TestCase

import pcs


class IterableStr(TestCase):
    maxDiff = None

    def test_no_iterable_str_in_code(self):
        paths_to_fix = []
        for pcs_path in pcs.__path__:
            for dirpath, dirnames, filenames in os.walk(pcs_path):
                del dirnames
                for fname in filenames:
                    if not fname.endswith(".py"):
                        continue
                    file_path = os.path.join(dirpath, fname)
                    with open(file_path) as file:
                        filedata = file.read()
                        if re.search(
                            r"\b(collection|iterable|sequence)\[[^\[\]]*\bstr\b",
                            filedata,
                            re.IGNORECASE,
                        ):
                            paths_to_fix.append(file_path)
        self.assertEqual(
            [],
            paths_to_fix,
            (
                "'Collection[str]' or 'Iterable[str]' or 'Sequence[str]' found "
                "in these files. Please replace it with StringCollection, "
                "StringIterable or StringSequence from pcs.common.types. "
                r"Vim regexp: \(collection\|iterable\|sequence\)\[[^\[\]]*\<str\>\c"
            ),
        )

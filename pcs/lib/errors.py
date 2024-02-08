from typing import Optional

from pcs.common.reports import ReportItem


class LibraryError(Exception):
    def __init__(self, *args: ReportItem, output: Optional[str] = None):
        super().__init__(*args)
        self._output = output

    @property
    def output(self):
        return self._output

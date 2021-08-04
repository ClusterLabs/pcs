from typing import Optional


class LibraryError(Exception):
    def __init__(self, *args, output: Optional[str] = None):
        super().__init__(*args)
        self._output = output

    @property
    def output(self):
        return self._output

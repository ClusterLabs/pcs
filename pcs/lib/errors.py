from pcs.common.reports import ReportItem


class LibraryError(Exception):
    def __init__(self, *args: ReportItem):
        super().__init__(*args)

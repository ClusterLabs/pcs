from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common.reports import LibraryReportProcessorToConsole
import pcs.common.pcs_pycurl as pycurl
from pcs.lib.errors import LibraryError, ReportItemSeverity
from pcs.test.tools.assertions import  assert_report_item_list_equal


class MockLibraryReportProcessor(LibraryReportProcessorToConsole):
    def __init__(self, debug=False, raise_on_errors=True):
        super(MockLibraryReportProcessor, self).__init__(debug)
        self.raise_on_errors = raise_on_errors

    @property
    def report_item_list(self):
        return self.items

    def send(self):
        errors = []
        for report_item in self.items:
            if report_item.severity == ReportItemSeverity.ERROR:
                errors.append(report_item)
        if errors and self.raise_on_errors:
            raise LibraryError(*errors)

    def assert_reports(self, report_info_list):
        assert_report_item_list_equal(self.report_item_list, report_info_list)


class MockCurl(object):
    def __init__(self, info, output="", debug_output_list=None, exception=None):
        self._opts = {}
        self._info = info if info else {}
        self._output = output
        self._debug_output_list = debug_output_list
        self._exception = exception

    @property
    def opts(self):
        return self._opts

    def reset(self):
        self._opts = {}

    def setopt(self, opt, val):
        if val is None:
            self.unsetopt(opt)
        else:
            self._opts[opt] = val

    def unsetopt(self, opt):
        try:
            del self._opts[opt]
        except KeyError:
            pass

    def getinfo(self, opt):
        try:
            return self._info[opt]
        except KeyError:
            AssertionError("info '#{0}' not defined".format(opt))

    def perform(self):
        if self._exception:
            #pylint: disable=raising-bad-type
            raise self._exception
        if pycurl.WRITEFUNCTION in self._opts:
            self._opts[pycurl.WRITEFUNCTION](self._output)
        if pycurl.DEBUGFUNCTION in self._opts:
            for msg_type, msg in self._debug_output_list:
                self._opts[pycurl.DEBUGFUNCTION](msg_type, msg)


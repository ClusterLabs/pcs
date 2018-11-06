import io
import socket
from unittest import mock

from pcs.cli.common.reports import LibraryReportProcessorToConsole
import pcs.common.pcs_pycurl as pycurl
from pcs.lib.errors import LibraryError, ReportItemSeverity
from pcs.test.tools.assertions import  assert_report_item_list_equal


def get_getaddrinfo_mock(resolvable_addr_list):
    def socket_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # pylint: disable=redefined-builtin, unused-argument
        if host not in resolvable_addr_list:
            raise socket.gaierror(1, "")
    return socket_getaddrinfo

def patch_getaddrinfo(test_case, addr_list):
    """
    class MyTest(TestCase):
        def setUp(self):
            self.resolvable_hosts = patch_getaddrinfo(self, [])
        def test_something(self):
            self.resolvable_hosts.extend(["node1", "node2"])
    """
    patcher = mock.patch("socket.getaddrinfo", get_getaddrinfo_mock(addr_list))
    patcher.start()
    test_case.addCleanup(patcher.stop)
    return addr_list


class MockLibraryReportProcessor(LibraryReportProcessorToConsole):
    def __init__(self, debug=False, raise_on_errors=True):
        super(MockLibraryReportProcessor, self).__init__(debug)
        self.raise_on_errors = raise_on_errors
        self.direct_sent_items = []

    @property
    def report_item_list(self):
        return self.items

    def report_list(self, report_list):
        self.direct_sent_items.extend(report_list)
        return self._send(report_list)

    def send(self):
        errors = self._send(self.items, print_errors=False)
        if errors and self.raise_on_errors:
            raise LibraryError(*errors)

    def assert_reports(self, expected_report_info_list, hint=""):
        assert_report_item_list_equal(
            self.report_item_list + self.direct_sent_items,
            expected_report_info_list,
            hint=hint
        )

    def _send(self, report_item_list, print_errors=True):
        errors = []
        for report_item in report_item_list:
            if report_item.severity == ReportItemSeverity.ERROR:
                errors.append(report_item)
        return errors



class MockCurl:
    def __init__(
            self, info=None, output=b"", debug_output_list=None, exception=None,
            error=None, request=None
    ):
        # we don't need exception anymore, because we don't use perform on
        # easy hanlers. but for now it has to stay as it is because it is sill
        # used from old communicator tests
        self._opts = {}
        self._info = info if info else {}
        self._output = output
        self._debug_output_list = debug_output_list if debug_output_list else []
        self._error = error
        self._exception = exception
        self.request_obj = request

    @property
    def opts(self):
        return self._opts

    @property
    def error(self):
        return self._error

    def reset(self):
        self._opts = {}

    def setopt(self, opt, val):
        if isinstance(val, list):
            # in tests we use set operations (e.g. assertLessEqual) which
            # require hashable values
            val = tuple(val)
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
        if self._error:
            return
        if self._exception:
            #pylint: disable=raising-bad-type
            raise self._exception
        if pycurl.WRITEFUNCTION in self._opts:
            self._opts[pycurl.WRITEFUNCTION](self._output)
        if pycurl.DEBUGFUNCTION in self._opts:
            for msg_type, msg in self._debug_output_list:
                self._opts[pycurl.DEBUGFUNCTION](msg_type, msg)


class MockCurlSimple:
    def __init__(self, info=None, output=b"", debug_output=b"", request=None):
        self.output_buffer = io.BytesIO()
        self.output_buffer.write(
            output if isinstance(output, bytes) else output.encode("utf-8")
        )
        self.debug_buffer = io.BytesIO()
        self.debug_buffer.write(
            debug_output if isinstance(debug_output, bytes)
            else debug_output.encode("utf-8")
        )
        self.request_obj = request
        self._info = info if info else {}

    def getinfo(self, opt):
        try:
            return self._info[opt]
        except KeyError:
            AssertionError("info '#{0}' not defined".format(opt))


class MockCurlMulti:
    def __init__(self, number_of_performed_list):
        self._number_of_performed_list = number_of_performed_list
        self._opts = {}
        self._handle_list = []
        self._proccessed_list = []

    @property
    def opts(self):
        return self._opts

    def setopt(self, opt, val):
        self._opts[opt] = val

    def add_handle(self, handle):
        if not isinstance(handle, MockCurl):
            raise AssertionError("Only MockCurl objects are allowed")
        if handle in self._handle_list:
            # same error as real CurlMulti object
            raise pycurl.error("curl object already on this multi-stack")
        self._handle_list.append(handle)

    def remove_handle(self, handle):
        if handle not in self._handle_list:
            # same error as real CurlMulti object
            raise pycurl.error("curl object not on this multi-stack")
        self._handle_list.remove(handle)

    def assert_no_handle_left(self):
        if self._handle_list:
            raise AssertionError(
                "{0} handle(s) left to process".format(len(self._handle_list))
            )

    def select(self, timeout=1):
        # pylint: disable=no-self-use, unused-argument
        return 0

    def perform(self):
        # pylint: disable=no-self-use
        return (0, 0)

    def timeout(self):
        # pylint: disable=no-self-use
        return 0

    def info_read(self):
        ok_list = []
        err_list = []
        if not self._number_of_performed_list:
            raise AssertionError("unexpected info_read call")
        number_to_perform = self._number_of_performed_list.pop(0)
        if number_to_perform > len(self._handle_list):
            raise AssertionError("expecting more handles than prepared")
        for handle in self._handle_list[:number_to_perform]:
            try:
                handle.perform()
                if handle.error:
                    err_list.append((handle, handle.error[0], handle.error[1]))
                else:
                    ok_list.append(handle)
            except pycurl.error as e:
                # pylint: disable=unbalanced-tuple-unpacking
                errno, msg = e.args
                err_list.append((handle, errno, msg))
            self._proccessed_list.append(handle)
        return (0, ok_list, err_list)

import contextlib
import io
import socket
from dataclasses import dataclass
from typing import (
    Callable,
    Iterable,
    Mapping,
    Optional,
    Union,
)
from unittest import mock

import pcs.common.pcs_pycurl as pycurl
from pcs.common.reports import (
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.common.types import CibRuleInEffectStatus
from pcs.lib.cib.rule.in_effect import RuleInEffectEval
from pcs.lib.external import CommandRunner

from pcs_test.tools.assertions import assert_report_item_list_equal


def get_getaddrinfo_mock(resolvable_addr_list):
    def socket_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # pylint: disable=redefined-builtin
        # pylint: disable=unused-argument
        if host not in resolvable_addr_list:
            raise socket.gaierror(1, "")

    return socket_getaddrinfo


def get_runner_mock(stdout="", stderr="", returncode=0, env_vars=None):
    runner = mock.MagicMock(spec_set=CommandRunner)
    runner.run.return_value = (stdout, stderr, returncode)
    runner.env_vars = env_vars if env_vars else {}
    return runner


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


FileContentType = Union[str, bytes, None, Exception]


@dataclass(frozen=True)
class TmpFileCall:
    name: str
    is_binary: bool = False
    orig_content: FileContentType = None
    new_content: FileContentType = None


class TmpFileMock:
    def __init__(
        self,
        calls: Iterable[TmpFileCall] = (),
        file_content_checker: Optional[
            Callable[[FileContentType, FileContentType], bool]
        ] = None,
    ):
        self.set_calls(calls)
        self._file_content_checker = file_content_checker

    def _assert_file_content_equal(self, name, expected, real):
        if expected is None and real is None:
            return

        def eq_callback(file1, file2):
            return file1 != file2

        if self._file_content_checker is not None:
            eq_callback = self._file_content_checker
        try:
            is_not_equal = eq_callback(expected, real)
        except AssertionError as e:
            raise AssertionError(
                f"Temporary file '{name}' content mismatch."
            ) from e
        if is_not_equal:
            raise AssertionError(
                f"Temporary file '{name}' content mismatch.\nExpected:\n"
                f"{expected}\n\nReal:\n{real}"
            )

    def set_calls(self, calls):
        self._calls = list(calls)
        self._calls_iter = iter(self._calls)

    def extend_calls(self, calls):
        self._calls.extend(calls)

    def get_mock_side_effect(self):
        return self._mock_side_effect

    def assert_all_done(self):
        try:
            next_unused = next(self._calls_iter)
            raise AssertionError(
                f"Not all temporary files were used; Next unused: {next_unused}"
            )
        except StopIteration:
            pass

    def _mock_side_effect(self, data, binary=False):
        def _seek_callback(offset):
            if offset != 0:
                raise AssertionError(
                    "Calling seek on a temporary file in tests with a parameter "
                    "other than 0 is not supported"
                )

        try:
            call = next(self._calls_iter)
            if isinstance(call.orig_content, Exception):
                raise call.orig_content
            if binary != call.is_binary:
                raise AssertionError(
                    (
                        "File mode mismatch; Expected: binary={expected}; "
                        "Real: binary={real}"
                    ).format(
                        expected=call.is_binary,
                        real=binary,
                    )
                )
            self._assert_file_content_equal(call.name, call.orig_content, data)
            tmp_file_mock = mock.NonCallableMock(
                spec_set=["read", "seek", "name"]
            )
            tmp_file_mock.name = call.name
            tmp_file_mock.seek.side_effect = _seek_callback
            if call.new_content is None:
                tmp_file_mock.seek.side_effect = AssertionError(
                    "Seek call not expected"
                )
                tmp_file_mock.read.side_effect = AssertionError(
                    "Read call not expected"
                )
            elif isinstance(call.new_content, Exception):
                tmp_file_mock.read.side_effect = call.new_content
            else:
                tmp_file_mock.read.return_value = call.new_content
            tmp_file_context_manager_mock = mock.NonCallableMagicMock(
                spec_set=["__enter__", "__exit__"]
            )
            tmp_file_context_manager_mock.__enter__.return_value = tmp_file_mock
            return tmp_file_context_manager_mock
        except StopIteration:
            raise AssertionError(
                f"No more temporary files expected but got:\n{data}"
            ) from None


class MockLibraryReportProcessor(ReportProcessor):
    def __init__(self, debug=True):
        super().__init__()
        self.debug = debug
        self.items = []

    def _do_report(self, report_item):
        if self.debug or report_item.severity != ReportItemSeverity.DEBUG:
            self.items.append(report_item)

    @property
    def report_item_list(self):
        return self.items

    def assert_reports(self, expected_report_info_list, hint=""):
        assert_report_item_list_equal(
            self.report_item_list, expected_report_info_list, hint=hint
        )


class MockCurl:
    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        info=None,
        output=b"",
        debug_output_list=None,
        exception=None,
        error=None,
        request=None,
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
        with contextlib.suppress(KeyError):
            del self._opts[opt]

    def getinfo(self, opt):
        try:
            return self._info[opt]
        except KeyError as e:
            raise AssertionError("info '#{0}' not defined".format(opt)) from e

    def perform(self):
        if self._error:
            return
        if self._exception:
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
            debug_output
            if isinstance(debug_output, bytes)
            else debug_output.encode("utf-8")
        )
        self.request_obj = request
        self._info = info if info else {}

    def getinfo(self, opt):
        try:
            return self._info[opt]
        except KeyError as e:
            raise AssertionError("info '#{0}' not defined".format(opt)) from e


class MockCurlMulti:
    def __init__(self, number_of_performed_list):
        self._number_of_performed_list = number_of_performed_list
        self._opts = {}
        self._handle_list = []
        self._processed_list = []

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
            self._processed_list.append(handle)
        return (0, ok_list, err_list)


class RuleInEffectEvalMock(RuleInEffectEval):
    def __init__(self, results: Mapping[str, CibRuleInEffectStatus]) -> None:
        self._results = dict(results)

    def get_rule_status(self, rule_id: str) -> CibRuleInEffectStatus:
        return self._results.get(rule_id, CibRuleInEffectStatus.UNKNOWN)

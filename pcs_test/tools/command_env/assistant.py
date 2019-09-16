import inspect
import logging
import os
import os.path
import sys
from functools import partial

from unittest import mock

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_raise_library_error, prepare_diff
from pcs_test.tools.case_analysis import test_failed
from pcs_test.tools.command_env import spy
from pcs_test.tools.command_env.calls import Queue as CallQueue
from pcs_test.tools.command_env.config import Config
from pcs_test.tools.command_env.mock_fs import(
    get_fs_mock,
    is_fs_call_in,
)
from pcs_test.tools.command_env.mock_get_local_corosync_conf import(
    get_get_local_corosync_conf
)
from pcs_test.tools.command_env.mock_node_communicator import NodeCommunicator
from pcs_test.tools.command_env.mock_push_cib import(
    get_push_cib,
    is_push_cib_call_in,
)
from pcs_test.tools.command_env.mock_push_corosync_conf import(
    get_push_corosync_conf,
    is_push_corosync_conf_call_in,
)
from pcs_test.tools.command_env.mock_raw_file import get_raw_file_mock
from pcs_test.tools.command_env.mock_runner import Runner
from pcs_test.tools.custom_mock import MockLibraryReportProcessor

from pcs.common.file import RawFile
from pcs.common.node_communicator import NodeCommunicatorFactory
from pcs.lib.env import LibraryEnvironment

patch_lib_env = partial(mock.patch.object, LibraryEnvironment)

def patch_env(call_queue, config, init_env, patch_is_systemd=True):
    #It is mandatory to patch some env objects/methods. It is ok when command
    #does not use this objects/methods and specify no call for it. But it would
    #be a problem when the test succeded because the live call respond correctly
    #by accident. Such test would fails on different machine (with another live
    #environment)

    get_cmd_runner = init_env.cmd_runner
    get_node_communicator = init_env.get_node_communicator
    mock_communicator_factory = mock.Mock(spec_set=NodeCommunicatorFactory)
    mock_communicator_factory.get_communicator = (
        # TODO: use request_timeout
        lambda request_timeout=None:
            NodeCommunicator(call_queue) if not config.spy
            else spy.NodeCommunicator(get_node_communicator())
    )
    patcher_list = [
        patch_lib_env(
            "cmd_runner",
            lambda env:
            spy.Runner(get_cmd_runner()) if config.spy else Runner(
                call_queue,
                env_vars={} if not config.env.cib_tempfile else {
                    "CIB_file": config.env.cib_tempfile,
                }
            )
        ),

        mock.patch(
            "pcs.lib.env.get_local_corosync_conf",
            get_get_local_corosync_conf(call_queue) if not config.spy
                else spy.get_local_corosync_conf
        ),

        patch_lib_env("communicator_factory", mock_communicator_factory),
    ]
    if patch_is_systemd:
        # In all the tests we assume that we are running on top of a systemd
        # running system. If needed, this may be turned off for some particular
        # tests. Note that the patched function is cached therefore is patched
        # here and not in every tests.
        patcher_list.append(
            mock.patch("pcs.lib.external.is_systemctl", lambda: True)
        )

    if is_fs_call_in(call_queue):
        fs_mock = get_fs_mock(call_queue)
        builtin = (
            ("__builtin__" if sys.version_info[0] == 2 else "builtins")+".{0}"
        ).format

        patcher_list.extend([
            mock.patch(
                builtin("open"),
                fs_mock("open", open)
            ),
            mock.patch(
                "os.path.exists",
                fs_mock("os.path.exists", os.path.exists)
            ),
            mock.patch(
                "os.path.isdir",
                fs_mock("os.path.isdir", os.path.isdir)
            ),
            mock.patch(
                "os.path.isfile",
                fs_mock("os.path.isfile", os.path.isfile)
            ),
            mock.patch(
                "os.listdir",
                fs_mock("os.listdir", os.listdir)
            ),
            mock.patch(
                "os.chmod",
                fs_mock("os.chmod", os.chmod)
            ),
            mock.patch(
                "os.chown",
                fs_mock("os.chown", os.chown)
            ),
        ])

    raw_file_mock = get_raw_file_mock(call_queue)
    for method_name, dummy_method in inspect.getmembers(
        RawFile, inspect.isfunction
    ):
        # patch all public methods
        # inspect.isfunction must be used instead of ismethod because we are
        # working with a class and not an instance - no method is bound yet so
        # it would return an empty list
        # "protected" methods start with _
        # "private" methods start with _<class_name>__
        if method_name.startswith("_"):
            continue
        patcher_list.append(
            mock.patch.object(
                RawFile,
                method_name,
                getattr(raw_file_mock, method_name)
            )
        )

    # It is not always desirable to patch these methods. Some tests may patch
    # only the internals (runner etc.). So these methods are only patched when
    # it is explicitly configured.
    if is_push_cib_call_in(call_queue):
        patcher_list.append(
            patch_lib_env("push_cib", get_push_cib(call_queue))
        )
    if is_push_corosync_conf_call_in(call_queue):
        patcher_list.append(
            patch_lib_env(
                "push_corosync_conf",
                get_push_corosync_conf(call_queue)
            )
        )

    for patcher in patcher_list:
        patcher.start()

    def unpatch():
        for patcher in patcher_list:
            patcher.stop()

    return unpatch

class EnvAssistant:
    # pylint: disable=too-many-instance-attributes
    def __init__(
        self, config=None, test_case=None,
        exception_reports_in_processor_by_default=True
    ):
        """
        TestCase test_case -- cleanup callback is registered to test_case if is
            provided
        """
        self.__call_queue = None
        self.__config = config if config else Config()
        self.__reports_asserted = False
        self.__extra_reports = []
        self.exception_reports_in_processor_by_default = (
            exception_reports_in_processor_by_default
        )

        self.__unpatch = None
        self.__original_mocked_corosync_conf = None

        if test_case:
            test_case.addCleanup(lambda: self.cleanup(test_case))

    @property
    def config(self):
        return self.__config

    def cleanup(self, current_test):
        if self.__unpatch:
            self.__unpatch()

        if test_failed(current_test):
            # We have already got the message that main test failed. There is
            # a high probability that something remains in reports or in the
            # queue etc. But it is only consequence of the main test fail. And
            # we do not want to make the report confusing.
            return

        if not self.__reports_asserted:
            self.__assert_environment_created()
            if not self.__config.spy:
                self._env.report_processor.assert_reports(
                    self.__extra_reports,
                    hint="EnvAssistant.cleanup - is param"
                        " 'expected_in_processor' in the method"
                        " 'assert_raise_library_error' set correctly?"
                )

        if not self.__config.spy:
            if self.__call_queue and self.__call_queue.remaining:
                raise AssertionError(
                    "There are remaining expected calls: \n    '{0}'"
                    .format("'\n    '".join([
                        repr(call) for call in self.__call_queue.remaining
                    ]))
                )
            # If pushing corosync.conf has not been patched in the
            # LibraryEnvironment and the LibraryEnvironment was constructed
            # with a mocked corosync.conf, check if it was changed without the
            # change being specified in a test.
            # If no env.push_corosync_conf call has been specified, no mocking
            # occurs, any changes to corosync.conf are done just in memory and
            # nothing gets reported. So an explicit check is necessary.
            corosync_conf_orig = self.__original_mocked_corosync_conf
            # pylint: disable=protected-access
            corosync_conf_env = self._env._corosync_conf_data
            if (
                corosync_conf_orig
                and
                corosync_conf_orig != corosync_conf_env
            ):
                raise AssertionError(
                    (
                        "An unexpected change to corosync.conf in "
                        "LibraryEnvironment has been detected:\n{0}"
                    ).format(
                        prepare_diff(corosync_conf_orig, corosync_conf_env)
                    )
                )


    def get_env(self, patch_is_systemd=True):
        self.__call_queue = CallQueue(self.__config.calls)
        #pylint: disable=attribute-defined-outside-init
        self._env = LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor(),
            cib_data=self.__config.env.cib_data,
            corosync_conf_data=self.__config.env.corosync_conf_data,
            known_hosts_getter=(
                (lambda: self.__config.spy.known_hosts) if self.__config.spy
                else self.__config.env.known_hosts_getter
            ),
            booth_files_data=self.__config.env.booth,
        )
        self.__unpatch = patch_env(
            self.__call_queue, self.__config, self._env,
            patch_is_systemd=patch_is_systemd
        )
        # If pushing corosync.conf has not been patched in the
        # LibraryEnvironment, store any corosync.conf passed to the
        # LibraryEnvironment for check for changes in cleanup.
        if not is_push_corosync_conf_call_in(self.__call_queue):
            self.__original_mocked_corosync_conf = (
                self.__config.env.corosync_conf_data
            )
        return self._env

    def assert_reports(self, expected_reports):
        self.__reports_asserted = True
        self.__assert_environment_created()
        self._env.report_processor.assert_reports(
            (
                expected_reports.reports
                    if isinstance(expected_reports, fixture.ReportStore)
                else expected_reports
            )
            +
            self.__extra_reports
        )

    def assert_raise_library_error(
        self, command, reports=None, expected_in_processor=None
    ):
        if reports is None:
            reports = []

        if not isinstance(reports, list):
            raise self.__list_of_reports_expected(reports)

        if expected_in_processor is None:
            expected_in_processor = (
                self.exception_reports_in_processor_by_default
            )

        assert_raise_library_error(command, *reports)
        if expected_in_processor:
            self.__extra_reports = reports

    def __assert_environment_created(self):
        if not hasattr(self, "_env"):
            raise AssertionError(
                "LibraryEnvironment was not created in EnvAssitant."
                " Have you called method get_env?"
            )

    def __list_of_reports_expected(self, reports):
        return AssertionError(
            "{0}.{1} expects 'list' as reports parameter, '{2}' was given"
            .format(
                self.__class__.__name__,
                "assert_raise",
                type(reports).__name__
            )
        )

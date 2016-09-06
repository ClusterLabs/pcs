from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.test.tools.pcs_unittest import TestCase

from pcs.cli.common.lib_wrapper import Library, bind
from pcs.test.tools.pcs_unittest import mock
from pcs.lib.errors import ReportItem
from pcs.lib.errors import LibraryEnvError

class LibraryWrapperTest(TestCase):
    def test_raises_for_bad_path(self):
        mock_middleware_factory = mock.MagicMock()
        lib = Library('env', mock_middleware_factory)
        self.assertRaises(Exception, lambda:lib.no_valid_library_part)

    @mock.patch('pcs.cli.common.lib_wrapper.constraint_order.create_with_set')
    @mock.patch('pcs.cli.common.lib_wrapper.cli_env_to_lib_env')
    def test_bind_to_library(self, mock_cli_env_to_lib_env, mock_order_set):
        lib_env = mock.MagicMock()
        lib_env.is_cib_live = True
        lib_env.is_corosync_conf_live = True
        mock_cli_env_to_lib_env.return_value = lib_env

        def dummy_middleware(next_in_line, env, *args, **kwargs):
            return next_in_line(env, *args, **kwargs)


        mock_middleware_factory = mock.MagicMock()
        mock_middleware_factory.cib = dummy_middleware
        mock_middleware_factory.corosync_conf_existing = dummy_middleware
        mock_env = mock.MagicMock()
        Library(mock_env, mock_middleware_factory).constraint_order.set(
            'first', second="third"
        )

        mock_order_set.assert_called_once_with(lib_env, "first", second="third")

class BindTest(TestCase):
    @mock.patch("pcs.cli.common.lib_wrapper.process_library_reports")
    def test_report_unprocessed_library_env_errors(self, mock_process_report):
        report1 = ReportItem.error("OTHER ERROR", info={})
        report2 = ReportItem.error("OTHER ERROR", info={})
        report3 = ReportItem.error("OTHER ERROR", info={})
        e = LibraryEnvError(report1, report2, report3)
        e.sign_processed(report2)
        mock_middleware = mock.Mock(side_effect=e)

        binded = bind(
            cli_env=None,
            run_with_middleware=mock_middleware,
            run_library_command=None
        )

        self.assertRaises(SystemExit, lambda: binded(cli_env=None))
        mock_process_report.assert_called_once_with([report1, report3])

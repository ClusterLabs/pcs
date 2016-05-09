from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from unittest import TestCase

from pcs.cli.common.lib_wrapper import Library
from pcs.test.tools.pcs_mock import mock

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
        Library('env', mock_middleware_factory).constraint_order.set('first', second="third")

        mock_order_set.assert_called_once_with(lib_env, "first", second="third")

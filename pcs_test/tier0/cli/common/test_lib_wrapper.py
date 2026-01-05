from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.lib_wrapper import Library


class LibraryWrapperTest(TestCase):
    def test_raises_for_bad_path(self):
        mock_middleware_factory = mock.MagicMock()
        lib = Library("env", mock_middleware_factory)
        self.assertRaises(ValueError, lambda: lib.no_valid_library_part)

    @mock.patch("pcs.cli.common.lib_wrapper.constraint_order.create_with_set")
    @mock.patch("pcs.cli.common.lib_wrapper.cli_env_to_lib_env")
    def test_bind_to_library(self, mock_cli_env_to_lib_env, mock_order_set):
        # pylint: disable=no-self-use
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
        Library(
            mock_env, mock_middleware_factory
        ).constraint_order.create_with_set("first", second="third")

        mock_order_set.assert_called_once_with(lib_env, "first", second="third")

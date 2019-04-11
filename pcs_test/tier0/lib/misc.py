import logging
from unittest import mock

from pcs_test.tools.custom_mock import MockLibraryReportProcessor

from pcs.lib.env import LibraryEnvironment as Env


def get_mocked_env(**kwargs):
    return Env(
        logger=mock.MagicMock(logging.Logger),
        report_processor=MockLibraryReportProcessor(),
        **kwargs
    )

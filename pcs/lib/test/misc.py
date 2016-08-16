from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging

from pcs.lib.env import LibraryEnvironment as Env
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock


def get_mocked_env(**kwargs):
    return Env(
        logger=mock.MagicMock(logging.Logger),
        report_processor=MockLibraryReportProcessor(),
        **kwargs
    )

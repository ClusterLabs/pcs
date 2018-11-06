import logging
import unittest

from pcs.cli.common.reports import (
    LibraryReportProcessorToConsole as ReportProcessor
)
from pcs.lib.external import CommandRunner
from pcs.lib.resource_agent import StonithAgent


def __can_load_xvm_fence_agent():
    # pylint: disable=bare-except
    try:
        runner = CommandRunner(logging.getLogger("test"), ReportProcessor())
        StonithAgent(runner, "fence_xvm").validate_metadata()
        return True
    except:
        return False


need_load_xvm_fence_agent = unittest.skipUnless(
    __can_load_xvm_fence_agent(),
    "test requires the successful load of 'fence_xvm' agent"
)

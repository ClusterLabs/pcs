from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import RawFileError
from pcs.common.reports.item import ReportItem
from pcs.lib.errors import LibraryError

CALL_TYPE_GET_LOCAL_COROSYNC_CONF = "CALL_TYPE_GET_LOCAL_COROSYNC_CONF"


class Call:
    type = CALL_TYPE_GET_LOCAL_COROSYNC_CONF

    def __init__(self, content, exception_msg=None):
        self.content = content
        self.exception_msg = exception_msg

    def __repr__(self):
        return str("<GetLocalCorosyncConf>")


def get_get_local_corosync_conf(call_queue):
    def get_local_corosync_conf():
        _, expected_call = call_queue.take(CALL_TYPE_GET_LOCAL_COROSYNC_CONF)
        if expected_call.exception_msg:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.FileIoError(
                        file_type_codes.COROSYNC_CONF,
                        RawFileError.ACTION_READ,
                        expected_call.exception_msg,
                        settings.corosync_conf_file,
                    )
                )
            )
        return expected_call.content

    return get_local_corosync_conf

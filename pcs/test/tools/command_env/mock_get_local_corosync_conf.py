CALL_TYPE_GET_LOCAL_COROSYNC_CONF = "CALL_TYPE_GET_LOCAL_COROSYNC_CONF"

class Call:
    type = CALL_TYPE_GET_LOCAL_COROSYNC_CONF

    def __init__(self, content):
        self.content = content

    def __repr__(self):
        return str("<GetLocalCorosyncConf>")


def get_get_local_corosync_conf(call_queue):
    def get_local_corosync_conf():
        _, expected_call = call_queue.take(CALL_TYPE_GET_LOCAL_COROSYNC_CONF)
        return expected_call.content
    return get_local_corosync_conf

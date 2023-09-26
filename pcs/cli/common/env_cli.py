class Env:
    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self.cib_data = None
        self.user = None
        self.groups = None
        self.corosync_conf_data = None
        self.booth = None
        self.pacemaker = None
        self.known_hosts_getter = None
        self.debug = False
        self.request_timeout = None
        self.report_processor = None

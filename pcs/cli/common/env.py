from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

class Env(object):
    #pylint: disable=too-many-instance-attributes
    def __init__(self):
        self.cib_data = None
        self.cib_upgraded = False
        self.user = None
        self.groups = None
        self.corosync_conf_data = None
        self.booth = None
        self.auth_tokens_getter = None
        self.debug = False
        self.cluster_conf_data = None

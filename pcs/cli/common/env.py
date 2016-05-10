from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

class Env(object):
    def __init__(self):
        self.cib_data = None
        self.user = None
        self.groups = None
        self.corosync_conf_data = None
        self.auth_tokens_getter = None
        self.debug = False

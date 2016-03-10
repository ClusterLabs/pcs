from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path

testdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_test_resource(name):
    if name == 'crm_mon.minimal.xml':
        return os.path.join(testdir, 'resources', 'crm_mon.minimal.xml')
    return os.path.join(testdir, name)

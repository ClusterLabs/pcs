from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


class NodeAddresses(object):
    def __init__(self, ring0, ring1=None, name=None, id=None):
        self.ring0 = ring0
        self.ring1 = ring1
        self.name = name
        self.id = id

    @property
    def label(self):
        return self.name if self.name else self.ring0

class NodeAddressesList(object):
    def __init__(self, node_addrs_list=None):
        self._list = []
        if node_addrs_list:
            for node_addr in node_addrs_list:
                self._list.append(node_addr)

    def append(self, item):
        self._list.append(item)

    def __len__(self):
        return self._list.__len__()

    def __getitem__(self, key):
        return self._list.__getitem__(key)

    def __iter__(self):
        return self._list.__iter__()

    def __reversed__(self):
        return self._list.__reversed__()

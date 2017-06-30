from __future__ import (
    absolute_import,
    division,
    print_function,
)


class NodeNotFound(Exception):
    pass

def node_addresses_contain_host(node_addresses_list, host):
    return (
        host in [node.ring0 for node in node_addresses_list]
        or
        host in [node.ring1 for node in node_addresses_list if node.ring1]
    )

def node_addresses_contain_name(node_addresses_list, name):
    return name in [node.name for node in node_addresses_list]


class NodeAddresses(object):
    def __init__(self, ring0, ring1=None, name=None, id=None):
        self._ring0 = ring0
        self._ring1 = ring1
        self._name = name
        self._id = id

    def __hash__(self):
        return hash(self.label)

    def __eq__(self, other):
        return self.label == other.label

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        return self.label < other.label

    def __repr__(self):
        #the "dict" with name and id is "written" inside string because in
        #python3 the order is not
        return str("<{0}.{1} {2}, {{'name': {3}, 'id': {4}}}>").format(
            self.__module__,
            self.__class__.__name__,
            repr(
                [self.ring0] if self.ring1 is None
                else [self.ring0, self.ring1]
            ),
            repr(self.name),
            repr(self.id),
        )

    @property
    def ring0(self):
        return self._ring0

    @property
    def ring1(self):
        return self._ring1

    @property
    def name(self):
        return self._name

    @property
    def id(self):
        return self._id

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

    def __add__(self, other):
        if isinstance(other, NodeAddressesList):
            return NodeAddressesList(self._list + other._list)
        #Suppose that the other is a list. If it is not a list it correctly
        #raises.
        return NodeAddressesList(self._list + other)

    def find_by_label(self, label):
        for node in self._list:
            if node.label == label:
                return node
        raise NodeNotFound()

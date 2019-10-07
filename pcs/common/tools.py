import threading
from collections import namedtuple
from enum import Enum
from lxml import etree

def run_parallel(worker, data_list):
    thread_list = []
    for args, kwargs in data_list:
        thread = threading.Thread(target=worker, args=args, kwargs=kwargs)
        thread.daemon = True
        thread_list.append(thread)
        thread.start()

    for thread in thread_list:
        thread.join()

def format_environment_error(e):
    return format_os_error(e)

def format_os_error(e):
    if e.filename:
        return "{0}: '{1}'".format(e.strerror, e.filename)
    return e.strerror

def join_multilines(strings):
    return "\n".join([a.strip() for a in strings if a.strip()])

def xml_fromstring(xml):
    # If the xml contains encoding declaration such as:
    # <?xml version="1.0" encoding="UTF-8"?>
    # we get an exception in python3:
    # ValueError: Unicode strings with encoding declaration are not supported.
    # Please use bytes input or XML fragments without declaration.
    # So we encode the string to bytes.
    return etree.fromstring(
        xml.encode("utf-8"),
        #it raises on a huge xml without the flag huge_tree=True
        #see https://bugzilla.redhat.com/show_bug.cgi?id=1506864
        etree.XMLParser(huge_tree=True)
    )

class AutoNameEnum(str, Enum):
    def _generate_next_value_(name, start, count, last_values):
        # pylint: disable=no-self-argument
        del start, count, last_values
        return name

class Version(namedtuple("Version", ["major", "minor", "revision"])):
    def __new__(cls, major, minor=None, revision=None):
        return super(Version, cls).__new__(cls, major, minor, revision)

    @property
    def as_full_tuple(self):
        return (
            self.major,
            self.minor if self.minor is not None else 0,
            self.revision if self.revision is not None else 0,
        )

    def normalize(self):
        return self.__class__(*self.as_full_tuple)

    def __str__(self):
        return ".".join([str(x) for x in self if x is not None])

    def __lt__(self, other):
        return self.as_full_tuple < other.as_full_tuple

    def __le__(self, other):
        return self.as_full_tuple <= other.as_full_tuple

    def __eq__(self, other):
        return self.as_full_tuple == other.as_full_tuple

    def __ne__(self, other):
        return self.as_full_tuple != other.as_full_tuple

    def __gt__(self, other):
        return self.as_full_tuple > other.as_full_tuple

    def __ge__(self, other):
        return self.as_full_tuple >= other.as_full_tuple

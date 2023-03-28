import threading
import uuid
from collections import namedtuple
from typing import (
    MutableSet,
    Optional,
    TypeVar,
    Union,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common.types import StringCollection

T = TypeVar("T", bound=type)


def bin_to_str(binary: bytes) -> str:
    return "".join(map(chr, binary))


def get_all_subclasses(cls: T) -> MutableSet[T]:
    subclasses = set(cls.__subclasses__())
    return subclasses.union(
        {s for c in subclasses for s in get_all_subclasses(c)}
    )


def get_unique_uuid(already_used: StringCollection) -> str:
    is_duplicate = True
    while is_duplicate:
        candidate = str(uuid.uuid4())
        is_duplicate = candidate in already_used
    return candidate


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


def format_os_error(e: OSError):
    if e.filename:
        return "{0}: '{1}'".format(e.strerror, e.filename)
    return e.strerror


def xml_fromstring(xml: str) -> _Element:
    # If the xml contains encoding declaration such as:
    # <?xml version="1.0" encoding="UTF-8"?>
    # we get an exception in python3:
    # ValueError: Unicode strings with encoding declaration are not supported.
    # Please use bytes input or XML fragments without declaration.
    # So we encode the string to bytes.
    return etree.fromstring(
        xml.encode("utf-8"),
        # it raises on a huge xml without the flag huge_tree=True
        # see https://bugzilla.redhat.com/show_bug.cgi?id=1506864
        etree.XMLParser(huge_tree=True),
    )


def timeout_to_seconds(timeout: Union[int, str]) -> Optional[int]:
    """
    Transform pacemaker style timeout to number of seconds. If `timeout` is not
    a valid timeout, `None` is returned.

    timeout -- timeout string
    """
    try:
        candidate = int(timeout)
        if candidate >= 0:
            return candidate
        return None
    except ValueError:
        pass
    # Now we know the timeout is not an integer nor an integer string.
    # Let's make sure mypy knows the timeout is a string as well.
    timeout = str(timeout)
    suffix_multiplier = {
        "s": 1,
        "sec": 1,
        "m": 60,
        "min": 60,
        "h": 3600,
        "hr": 3600,
    }
    for suffix, multiplier in suffix_multiplier.items():
        if timeout.endswith(suffix) and timeout[: -len(suffix)].isdigit():
            return int(timeout[: -len(suffix)]) * multiplier
    return None


class Version(namedtuple("Version", ["major", "minor", "revision"])):
    def __new__(
        cls,
        major: int,
        minor: Optional[int] = None,
        revision: Optional[int] = None,
    ):
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

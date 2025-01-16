import uuid
from dataclasses import (
    astuple,
    dataclass,
)
from typing import (
    Generator,
    MutableSet,
    Optional,
    TypeVar,
    Union,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common.types import StringCollection
from pcs.common.validate import is_integer

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


def format_os_error(e: OSError) -> str:
    return f"{e.strerror}: '{e.filename}'" if e.filename else e.strerror


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
        if timeout.endswith(suffix):
            candidate2 = timeout[: -len(suffix)]
            if is_integer(candidate2, at_least=0):
                return int(candidate2) * multiplier
    return None


@dataclass(frozen=True)
class Version:
    major: int
    minor: Optional[int] = None
    revision: Optional[int] = None

    @property
    def as_full_tuple(self) -> tuple[int, int, int]:
        return (
            self.major,
            self.minor if self.minor is not None else 0,
            self.revision if self.revision is not None else 0,
        )

    def normalize(self) -> "Version":
        return self.__class__(*self.as_full_tuple)

    def __iter__(self) -> Generator[Optional[int], None, None]:
        yield from astuple(self)

    def __getitem__(self, index: int) -> Optional[int]:
        return astuple(self)[index]

    def __str__(self) -> str:
        return ".".join([str(x) for x in self if x is not None])

    def __lt__(self, other: "Version") -> bool:
        return self.as_full_tuple < other.as_full_tuple

    def __le__(self, other: "Version") -> bool:
        return self.as_full_tuple <= other.as_full_tuple

    # See, https://stackoverflow.com/questions/37557411/why-does-defining-the-argument-types-for-eq-throw-a-mypy-type-error
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.as_full_tuple == other.as_full_tuple

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.as_full_tuple != other.as_full_tuple

    def __gt__(self, other: "Version") -> bool:
        return self.as_full_tuple > other.as_full_tuple

    def __ge__(self, other: "Version") -> bool:
        return self.as_full_tuple >= other.as_full_tuple

import os
import tempfile
import uuid
from contextlib import contextmanager
from typing import (
    IO,
    Callable,
    ContextManager,
    Generator,
    Literal,
    Mapping,
    Optional,
    TypeVar,
    Union,
    overload,
)

from pcs.common import reports
from pcs.lib.errors import LibraryError

T = TypeVar("T")


def get_optional_value(
    constructor: Callable[[str], T], value: Optional[str]
) -> Optional[T]:
    if value is None:
        return None
    return constructor(value)


def generate_binary_key(random_bytes_count: int) -> bytes:
    return os.urandom(random_bytes_count)


def generate_uuid() -> str:
    return uuid.uuid4().hex


def environment_file_to_dict(config: str) -> dict[str, str]:
    """
    Parse systemd Environment file. This parser is simplified version of
    parser in systemd, because of their poor implementation.
    Returns configuration in dictionary in format:
    {
        <option>: <value>,
        ...
    }

    config -- Environment file as string
    """
    # escape new lines
    config = config.replace("\\\n", "")

    data = {}
    for line in [line.strip() for line in config.split("\n")]:
        if line == "" or line.startswith("#") or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        value = val.strip()
        data[key.strip()] = value
    return data


def dict_to_environment_file(config_dict: Mapping[str, str]) -> str:
    """
    Convert data in dictionary to Environment file format.
    Returns Environment file as string in format:
    # comment
    <option>=<value>
    ...

    config_dict -- dictionary in format: { <option>: <value>, ...}
    """
    lines = ["# This file has been generated by pcs.\n"]
    for key, val in sorted(config_dict.items()):
        lines.append(f"{key}={val}\n")
    return "".join(lines)


@overload
def get_tmp_file(
    data: Optional[bytes], binary: Literal[True]
) -> ContextManager[IO[bytes]]:
    pass


@overload
def get_tmp_file(
    data: Optional[str],
    binary: Literal[False] = False,
) -> ContextManager[IO[str]]:
    pass


# We ignore return type here as it doesn't work with mypy (@contextmanager and
# @overload) and it is properly typed in @overload functions.
@contextmanager
def get_tmp_file(  # type: ignore
    data: Optional[Union[bytes, str]],
    binary: bool = False,
):
    mode = "w+b" if binary else "w+"
    tmpfile = None
    try:
        with tempfile.NamedTemporaryFile(mode=mode, suffix=".pcs") as tmpfile:
            if data is not None:
                tmpfile.write(data)
                tmpfile.flush()
            yield tmpfile
    finally:
        if tmpfile:
            tmpfile.close()


@contextmanager
def get_tmp_cib(
    report_processor: reports.ReportProcessor, data: Optional[str]
) -> Generator[IO[str], None, None]:
    try:
        with get_tmp_file(data) as tmp_cib_file:
            report_processor.report(
                reports.ReportItem.debug(
                    reports.messages.TmpFileWrite(tmp_cib_file.name, data or "")
                )
            )
            yield tmp_cib_file
    except EnvironmentError as e:
        raise LibraryError(
            reports.ReportItem.error(reports.messages.CibSaveTmpError(str(e)))
        ) from e


def create_tmp_cib(
    report_processor: reports.ReportProcessor, data: Optional[str]
) -> IO[str]:
    try:
        # pylint: disable=consider-using-with
        tmp_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".pcs")
        if data is not None:
            tmp_file.write(data)
            tmp_file.flush()
        report_processor.report(
            reports.ReportItem.debug(
                reports.messages.TmpFileWrite(tmp_file.name, data or "")
            )
        )
        return tmp_file
    except EnvironmentError as e:
        raise LibraryError(
            reports.ReportItem.error(reports.messages.CibSaveTmpError(str(e)))
        ) from e

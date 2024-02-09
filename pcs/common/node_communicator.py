import base64
import io
import re
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Generator,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Union,
)
from urllib.parse import urlencode

# We should ignore SIGPIPE when using pycurl.NOSIGNAL - see the libcurl tutorial
# for more info.
try:
    import signal

    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
except ImportError:
    pass

from pcs import settings
from pcs.common import pcs_pycurl as pycurl
from pcs.common.host import (
    Destination,
    PcsKnownHost,
)
from pcs.common.pcs_pycurl import Curl
from pcs.common.types import StringIterable


class HostNotFound(Exception):
    def __init__(self, name: str):
        super().__init__()
        self.name = name


@dataclass(frozen=True)
class RequestTarget:
    """
    This class represents target (host) for request to be performed on
    """

    label: str
    token: Optional[str] = None
    dest_list: list[Destination] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.dest_list:
            object.__setattr__(
                self,
                "dest_list",
                [Destination(self.label, settings.pcsd_default_port)],
            )

    @classmethod
    def from_known_host(cls, known_host: PcsKnownHost) -> "RequestTarget":
        return cls(
            known_host.name,
            token=known_host.token,
            dest_list=known_host.dest_list,
        )

    @property
    def first_addr(self) -> str:
        # __post_init__ ensures there is always at least one item in
        # self.dest_list
        return self.dest_list[0].addr


class NodeTargetFactory:
    def __init__(self, known_hosts: Mapping[str, PcsKnownHost]):
        self._known_hosts = known_hosts

    def get_target(self, host_name: str) -> RequestTarget:
        known_host = self._known_hosts.get(host_name)
        if known_host is None:
            raise HostNotFound(host_name)
        return RequestTarget.from_known_host(known_host)

    def get_target_from_hostname(self, hostname: str) -> RequestTarget:
        try:
            return self.get_target(hostname)
        except HostNotFound:
            return RequestTarget(hostname)


@dataclass(frozen=True)
class RequestData:
    """
    This class represents action and data associated with action which will be
    send in request

    action -- action to perform
    structured_data -- list of tuples, data to send with specified action
    data -- raw data to send in request's body
    """

    action: str
    structured_data: Union[
        Sequence[tuple[Union[str, bytes], Union[str, bytes]]],
        Sequence[tuple[Union[str, bytes], Sequence[Union[str, bytes]]]],
    ] = ()
    data: str = ""

    def __post_init__(self) -> None:
        if not self.data:
            object.__setattr__(self, "data", urlencode(self.structured_data))
        else:
            object.__setattr__(self, "structured_data", ())


class Request:
    """
    This class represents request. With usage of RequestTarget it provides
    interface for getting next available host to make request on.
    """

    def __init__(
        self, request_target: RequestTarget, request_data: RequestData
    ) -> None:
        """
        RequestTarget request_target
        RequestData request_data
        """
        self._target = request_target
        self._data = request_data
        self._current_dest_iterator = iter(self._target.dest_list)
        self._current_dest: Optional[Destination] = None
        self.next_dest()

    def next_dest(self) -> None:
        """
        Move to the next available host connection. Raises StopIteration when
        there is no connection to use.
        """
        self._current_dest = next(self._current_dest_iterator)

    @property
    def url(self) -> str:
        """
        URL representing request using current host.
        """
        if self.dest is None:
            return ""
        addr = self.dest.addr
        port = self.dest.port
        return "https://{host}:{port}/{request}".format(
            host="[{0}]".format(addr) if ":" in addr else addr,
            port=(port if port else settings.pcsd_default_port),
            request=self._data.action,
        )

    @property
    def dest(self) -> Optional[Destination]:
        return self._current_dest

    @property
    def host_label(self) -> str:
        return self._target.label

    @property
    def target(self) -> RequestTarget:
        return self._target

    @property
    def data(self) -> str:
        return self._data.data

    @property
    def action(self) -> str:
        return self._data.action

    @property
    def cookies(self) -> dict[str, str]:
        cookies = {}
        if self._target.token:
            cookies["token"] = self._target.token
        return cookies

    def __repr__(self) -> str:
        return str("Request({0}, {1})").format(self._target, self._data)


class Response:
    """
    This class represents response for request which is available as instance
    property.
    """

    def __init__(
        self,
        handle: Curl,
        was_connected: bool,
        errno: Optional[int] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        self._handle = handle
        self._was_connected = was_connected
        self._errno = errno
        self._error_msg = error_msg
        self._data = None
        self._debug = None

    @classmethod
    def connection_successful(cls, handle: Curl) -> "Response":
        """
        Returns Response instance that is marked as successfully connected.

        handle -- curl easy handle, which connection was successful
        """
        return cls(handle, True)

    @classmethod
    def connection_failure(
        cls, handle: Curl, errno: int, error_msg: str
    ) -> "Response":
        """
        Returns Response instance that is marked as not successfully connected.

        handle -- curl easy handle, which was not connected
        errno -- error number
        error_msg -- text description of error
        """
        return cls(handle, False, errno, error_msg)

    @property
    def request(self) -> Request:
        return self._handle.request_obj  # type: ignore[attr-defined]

    @property
    def handle(self) -> Curl:
        return self._handle

    @property
    def was_connected(self) -> bool:
        return self._was_connected

    @property
    def errno(self) -> Optional[int]:
        return self._errno

    @property
    def error_msg(self) -> Optional[str]:
        return self._error_msg

    @property
    def data(self) -> str:
        if self._data is None:
            self._data = self._handle.output_buffer.getvalue().decode("utf-8")  # type: ignore[attr-defined]
        return str(self._data)

    @property
    def debug(self) -> str:
        if self._debug is None:
            self._debug = self._handle.debug_buffer.getvalue().decode("utf-8")  # type: ignore[attr-defined]
        return str(self._debug)

    @property
    def response_code(self) -> Optional[int]:
        if not self.was_connected:
            return None
        return self._handle.getinfo(pycurl.RESPONSE_CODE)

    def __repr__(self) -> str:
        return str(
            "Response({0} data='{1}' was_connected={2}) errno='{3}'"
            " error_msg='{4}' response_code='{5}')"
        ).format(
            self.request,
            self.data,
            self.was_connected,
            self.errno,
            self.error_msg,
            self.response_code,
        )


class CommunicatorLoggerInterface:
    def log_request_start(self, request: Request) -> None:
        raise NotImplementedError()

    def log_response(self, response: Response) -> None:
        raise NotImplementedError()

    def log_retry(self, response: Response, previous_dest: Destination) -> None:
        raise NotImplementedError()

    def log_no_more_addresses(self, response: Response) -> None:
        raise NotImplementedError()


class Communicator:
    """
    This class provides simple interface for making parallel requests.
    The instances of this class are not thread-safe! It is intended to use it
    only in a single thread. Use an unique instance for each thread.
    """

    curl_multi_select_timeout_default = 0.8  # in seconds

    def __init__(
        self,
        communicator_logger: CommunicatorLoggerInterface,
        user: Optional[str],
        groups: Optional[StringIterable],
        request_timeout: Optional[int] = None,
    ) -> None:
        self._logger = communicator_logger
        self._auth_cookies = _get_auth_cookies(user, groups)
        self._request_timeout = (
            request_timeout
            if request_timeout is not None
            else settings.default_request_timeout
        )
        self._multi_handle = pycurl.CurlMulti()
        self._is_running = False
        # This is used just for storing references of curl easy handles.
        # We need to have references for all the handles, so they don't be
        # cleaned up by the garbage collector.
        self._easy_handle_list: list[Curl] = []

    def add_requests(self, request_list: Iterable[Request]) -> None:
        """
        Add requests to queue to be processed. It is possible to call this
        method before getting generator using start_loop method and also during
        getting responses from generator.  Requests are not performed after
        calling this method, but only when generator returned by start_loop
        method is in progress (returned at least one response and not raised
        StopIteration exception).

        request_list -- Request objects to add to the queue
        """
        for request in request_list:
            handle = _create_request_handle(
                request,
                self._auth_cookies,
                self._request_timeout,
            )
            self._easy_handle_list.append(handle)
            self._multi_handle.add_handle(handle)
            if self._is_running:
                self._logger.log_request_start(request)

    def start_loop(self) -> Generator[Response, None, None]:
        """
        Returns generator. When generator is invoked, all requests in queue
        (added by method add_requests) will be invoked in parallel, and
        generator will then return responses for these requests. It is possible
        to add new request to the queue while the generator is in progress.
        Generator will stop (raise StopIteration) after all requests (also those
        added after creation of generator) are processed.

        WARNING: do not use multiple instances of generator (of one
        Communicator instance) when there is one which didn't finish
        (raised StopIteration). It will cause AssertionError.

        USAGE:
        com = Communicator(...)
        com.add_requests([
            Request(...), ...
        ])
        for response in communicator.start_loop():
            # do something with response
            # if needed, add some new requests to the queue
            com.add_requests([Request(...)])
        """
        if self._is_running:
            raise AssertionError("Method start_loop already running")
        self._is_running = True
        for handle in self._easy_handle_list:
            self._logger.log_request_start(handle.request_obj)  # type: ignore[attr-defined]

        finished_count = 0
        while finished_count < len(self._easy_handle_list):
            self.__multi_perform()
            self.__wait_for_multi_handle()
            response_list = self.__get_all_ready_responses()
            for response in response_list:
                # free up memory for next usage of this Communicator instance
                self._multi_handle.remove_handle(response.handle)
                self._logger.log_response(response)
                yield response
                # if something was added to the queue in the meantime, run it
                # immediately, so we don't need to wait until all responses will
                # be processed
                self.__multi_perform()
            finished_count += len(response_list)
        self._easy_handle_list = []
        self._is_running = False

    def __get_all_ready_responses(self) -> list[Response]:
        response_list = []
        repeat = True
        while repeat:
            num_queued, ok_list, err_list = self._multi_handle.info_read()
            response_list.extend(
                [Response.connection_successful(handle) for handle in ok_list]
                + [
                    Response.connection_failure(handle, errno, error_msg)
                    for handle, errno, error_msg in err_list
                ]
            )
            repeat = num_queued > 0
        return response_list

    def __multi_perform(self) -> int:
        # run all internal operation required by libcurl
        status, num_to_process = self._multi_handle.perform()
        # if perform returns E_CALL_MULTI_PERFORM it requires to call perform
        # once again right away
        while status == pycurl.E_CALL_MULTI_PERFORM:
            status, num_to_process = self._multi_handle.perform()
        return num_to_process

    def __wait_for_multi_handle(self) -> None:
        # try to wait until there is something to do for us
        need_to_wait = True
        while need_to_wait:
            timeout = float(self._multi_handle.timeout())
            if timeout == 0:
                # if timeout == 0 then there is something to precess already
                return
            timeout = (
                timeout / 1000.0
                if timeout > 0
                # curl don't have timeout set, so we can use our default
                else self.curl_multi_select_timeout_default
            )
            # when value returned from select is -1, it timed out, so we can
            # wait
            need_to_wait = self._multi_handle.select(timeout) == -1


class MultiaddressCommunicator(Communicator):
    """
    Class with same interface as Communicator. In difference with Communicator,
    it takes advantage of multiple hosts in RequestTarget. So if it is not
    possible to connect to target using first hostname, it will use next one
    until connection will be successful or there is no host left.
    """

    def start_loop(self) -> Generator[Response, None, None]:
        for response in super().start_loop():
            if response.was_connected:
                yield response
                continue
            try:
                previous_dest = response.request.dest
                response.request.next_dest()
                if previous_dest is not None:
                    self._logger.log_retry(response, previous_dest)
                self.add_requests([response.request])
            except StopIteration:
                self._logger.log_no_more_addresses(response)
                yield response


class NodeCommunicatorFactory:
    def __init__(
        self,
        communicator_logger: CommunicatorLoggerInterface,
        user: Optional[str],
        groups: Optional[StringIterable],
        request_timeout: Optional[int],
    ) -> None:
        self._logger = communicator_logger
        self._user = user
        self._groups = groups
        self._request_timeout = request_timeout

    def get_communicator(
        self, request_timeout: Optional[int] = None
    ) -> Communicator:
        return self.get_simple_communicator(request_timeout=request_timeout)

    def get_simple_communicator(
        self, request_timeout: Optional[int] = None
    ) -> Communicator:
        timeout = request_timeout if request_timeout else self._request_timeout
        return Communicator(
            self._logger, self._user, self._groups, request_timeout=timeout
        )

    def get_multiaddress_communicator(
        self, request_timeout: Optional[int] = None
    ) -> MultiaddressCommunicator:
        timeout = request_timeout if request_timeout else self._request_timeout
        return MultiaddressCommunicator(
            self._logger, self._user, self._groups, request_timeout=timeout
        )


def _get_auth_cookies(
    user: Optional[str], group_list: Optional[StringIterable]
) -> dict[str, str]:
    """
    Returns input parameters in a dictionary which is prepared to be converted
    to cookie string.

    user -- CIB user
    group_list -- CIB user groups
    """
    # Let's be safe about characters in variables (they can come from env)
    # and do base64. We cannot do it for CIB_user however to be backward
    # compatible so we at least remove disallowed characters.
    cookies = {}
    if user:
        cookies["CIB_user"] = re.sub(r"[^!-~]", "", user).replace(";", "")
    if group_list:
        # cookies require string but base64encode returns bytes, so decode it...
        cookies["CIB_user_groups"] = base64.b64encode(
            # python3 requires the value to be bytes not str
            " ".join(group_list).encode("utf-8")
        ).decode("utf-8")
    return cookies


def _create_request_handle(
    request: Request, cookies: dict[str, str], timeout: int
) -> Curl:
    """
    Returns Curl object (easy handle) which is set up with specified parameters.

    request -- request specification
    cookies -- cookies to add to request
    timeout -- request timeout
    """

    # it is not possible to take this callback out of this function, because of
    # curl API
    def __debug_callback(data_type: int, debug_data: bytes) -> None:
        # pylint: disable=no-member
        prefixes = {
            # Dynamically added attributes in pcs/common/pcs_pycurl.py
            pycurl.DEBUG_TEXT: b"* ",  # type: ignore[attr-defined]
            pycurl.DEBUG_HEADER_IN: b"< ",  # type: ignore[attr-defined]
            pycurl.DEBUG_HEADER_OUT: b"> ",  # type: ignore[attr-defined]
            pycurl.DEBUG_DATA_IN: b"<< ",  # type: ignore[attr-defined]
            pycurl.DEBUG_DATA_OUT: b">> ",  # type: ignore[attr-defined]
        }
        if data_type in prefixes:
            debug_output.write(prefixes[data_type])
            debug_output.write(debug_data)
            if not debug_data.endswith(b"\n"):
                debug_output.write(b"\n")

    output = io.BytesIO()
    debug_output = io.BytesIO()
    cookies.update(request.cookies)
    handle = pycurl.Curl()
    handle.setopt(pycurl.PROTOCOLS, pycurl.PROTO_HTTPS)
    handle.setopt(pycurl.TIMEOUT, timeout)
    handle.setopt(pycurl.URL, request.url.encode("utf-8"))
    handle.setopt(pycurl.WRITEFUNCTION, output.write)
    handle.setopt(pycurl.VERBOSE, 1)
    handle.setopt(pycurl.DEBUGFUNCTION, __debug_callback)
    handle.setopt(pycurl.SSL_VERIFYHOST, 0)
    handle.setopt(pycurl.SSL_VERIFYPEER, 0)
    handle.setopt(pycurl.NOSIGNAL, 1)  # required for multi-threading
    handle.setopt(pycurl.HTTPHEADER, ["Expect: "])
    if cookies:
        handle.setopt(pycurl.COOKIE, _dict_to_cookies(cookies).encode("utf-8"))
    if request.data:
        handle.setopt(pycurl.COPYPOSTFIELDS, request.data.encode("utf-8"))
    # add reference for request object and output buffers to handle, so later
    # we don't need to match these objects when they are returned from
    # pycurl after they've been processed
    # similar usage is in pycurl example:
    # https://github.com/pycurl/pycurl/blob/REL_7_19_0_3/examples/retriever-multi.py
    handle.request_obj = request  # type: ignore[attr-defined]
    handle.output_buffer = output  # type: ignore[attr-defined]
    handle.debug_buffer = debug_output  # type: ignore[attr-defined]
    return handle


def _dict_to_cookies(cookies_dict: dict[str, str]) -> str:
    return ";".join(
        [f"{key}={value}" for key, value in sorted(cookies_dict.items())]
    )

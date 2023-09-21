import base64
import io
import re
from collections import namedtuple
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
from pcs.common.host import Destination


def _find_value_for_possible_keys(value_dict, possible_key_list):
    for key in possible_key_list:
        if key in value_dict:
            return value_dict[key]
    return None


class HostNotFound(Exception):
    def __init__(self, name):
        super().__init__()
        self.name = name


class NodeTargetFactory:
    def __init__(self, known_hosts):
        self._known_hosts = known_hosts

    def get_target(self, host_name):
        known_host = self._known_hosts.get(host_name)
        if known_host is None:
            raise HostNotFound(host_name)
        return RequestTarget.from_known_host(known_host)

    def get_target_from_hostname(self, hostname):
        try:
            return self.get_target(hostname)
        except HostNotFound:
            return RequestTarget(hostname)


class RequestData(
    namedtuple("RequestData", ["action", "structured_data", "data"])
):
    """
    This class represents action and data associated with action which will be
    send in request
    """

    def __new__(cls, action, structured_data=(), data=None):
        """
        string action -- action to perform
        list structured_data -- list of tuples, data to send with specified
            action
        string data -- raw data to send in request's body
        """
        return super(RequestData, cls).__new__(
            cls,
            action,
            data if data else structured_data,
            data if data else urlencode(structured_data),
        )


class RequestTarget(
    namedtuple("RequestTarget", ["label", "token", "dest_list"])
):
    """
    This class represents target (host) for request to be performed on
    """

    def __new__(cls, label, token=None, dest_list=()):
        if not dest_list:
            dest_list = [Destination(label, settings.pcsd_default_port)]
        return super(RequestTarget, cls).__new__(
            cls,
            label,
            token=token,
            dest_list=list(dest_list),
        )

    @classmethod
    def from_known_host(cls, known_host):
        return cls(
            known_host.name,
            token=known_host.token,
            dest_list=known_host.dest_list,
        )

    @property
    def first_addr(self):
        # __new__ ensures there is always at least one item in self.dest_list
        return self.dest_list[0].addr


class Request:
    """
    This class represents request. With usage of RequestTarget it provides
    interface for getting next available host to make request on.
    """

    def __init__(self, request_target, request_data):
        """
        RequestTarget request_target
        RequestData request_data
        """
        self._target = request_target
        self._data = request_data
        self._current_dest_iterator = iter(self._target.dest_list)
        self._current_dest = None
        self.next_dest()

    def next_dest(self):
        """
        Move to the next available host connection. Raises StopIteration when
        there is no connection to use.
        """
        self._current_dest = next(self._current_dest_iterator)

    @property
    def url(self):
        """
        URL representing request using current host.
        """
        addr = self.dest.addr
        port = self.dest.port
        return "https://{host}:{port}/{request}".format(
            host="[{0}]".format(addr) if ":" in addr else addr,
            port=(port if port else settings.pcsd_default_port),
            request=self._data.action,
        )

    @property
    def dest(self):
        return self._current_dest

    @property
    def host_label(self):
        return self._target.label

    @property
    def target(self):
        return self._target

    @property
    def data(self):
        return self._data.data

    @property
    def action(self):
        return self._data.action

    @property
    def cookies(self):
        cookies = {}
        if self._target.token:
            cookies["token"] = self._target.token
        return cookies

    def __repr__(self):
        return str("Request({0}, {1})").format(self._target, self._data)


class Response:
    """
    This class represents response for request which is available as instance
    property.
    """

    def __init__(self, handle, was_connected, errno=None, error_msg=None):
        self._handle = handle
        self._was_connected = was_connected
        self._errno = errno
        self._error_msg = error_msg
        self._data = None
        self._debug = None

    @classmethod
    def connection_successful(cls, handle):
        """
        Returns Response instance that is marked as successfully connected.

        pycurl.Curl handle -- curl easy handle, which connection was successful
        """
        return cls(handle, True)

    @classmethod
    def connection_failure(cls, handle, errno, error_msg):
        """
        Returns Response instance that is marked as not successfully connected.

        pycurl.Curl handle -- curl easy handle, which was not connected
        int errno -- error number
        string error_msg -- text description of error
        """
        return cls(handle, False, errno, error_msg)

    @property
    def request(self):
        return self._handle.request_obj

    @property
    def handle(self):
        return self._handle

    @property
    def was_connected(self):
        return self._was_connected

    @property
    def errno(self):
        return self._errno

    @property
    def error_msg(self):
        return self._error_msg

    @property
    def data(self):
        if self._data is None:
            self._data = self._handle.output_buffer.getvalue().decode("utf-8")
        return self._data

    @property
    def debug(self):
        if self._debug is None:
            self._debug = self._handle.debug_buffer.getvalue().decode("utf-8")
        return self._debug

    @property
    def response_code(self):
        if not self.was_connected:
            return None
        return self._handle.getinfo(pycurl.RESPONSE_CODE)

    def __repr__(self):
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


class NodeCommunicatorFactory:
    def __init__(self, communicator_logger, user, groups, request_timeout):
        self._logger = communicator_logger
        self._user = user
        self._groups = groups
        self._request_timeout = request_timeout

    def get_communicator(self, request_timeout=None):
        return self.get_simple_communicator(request_timeout=request_timeout)

    def get_simple_communicator(self, request_timeout=None):
        timeout = request_timeout if request_timeout else self._request_timeout
        return Communicator(
            self._logger, self._user, self._groups, request_timeout=timeout
        )

    def get_multiaddress_communicator(self, request_timeout=None):
        timeout = request_timeout if request_timeout else self._request_timeout
        return MultiaddressCommunicator(
            self._logger, self._user, self._groups, request_timeout=timeout
        )


class Communicator:
    """
    This class provides simple interface for making parallel requests.
    The instances of this class are not thread-safe! It is intended to use it
    only in a single thread. Use an unique instance for each thread.
    """

    curl_multi_select_timeout_default = 0.8  # in seconds

    def __init__(self, communicator_logger, user, groups, request_timeout=None):
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
        self._easy_handle_list = []

    def add_requests(self, request_list):
        """
        Add requests to queue to be processed. It is possible to call this
        method before getting generator using start_loop method and also during
        getting responses from generator.  Requests are not performed after
        calling this method, but only when generator returned by start_loop
        method is in progress (returned at least one response and not raised
        StopIteration exception).

        list request_list -- Request objects to add to the queue
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

    def start_loop(self):
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
            self._logger.log_request_start(handle.request_obj)

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

    def __get_all_ready_responses(self):
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

    def __multi_perform(self):
        # run all internal operation required by libcurl
        status, num_to_process = self._multi_handle.perform()
        # if perform returns E_CALL_MULTI_PERFORM it requires to call perform
        # once again right away
        while status == pycurl.E_CALL_MULTI_PERFORM:
            status, num_to_process = self._multi_handle.perform()
        return num_to_process

    def __wait_for_multi_handle(self):
        # try to wait until there is something to do for us
        need_to_wait = True
        while need_to_wait:
            timeout = self._multi_handle.timeout()
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

    def start_loop(self):
        for response in super().start_loop():
            if response.was_connected:
                yield response
                continue
            try:
                previous_dest = response.request.dest
                response.request.next_dest()
                self._logger.log_retry(response, previous_dest)
                self.add_requests([response.request])
            except StopIteration:
                self._logger.log_no_more_addresses(response)
                yield response


class CommunicatorLoggerInterface:
    def log_request_start(self, request):
        raise NotImplementedError()

    def log_response(self, response):
        raise NotImplementedError()

    def log_retry(self, response, previous_dest):
        raise NotImplementedError()

    def log_no_more_addresses(self, response):
        raise NotImplementedError()


def _get_auth_cookies(user, group_list):
    """
    Returns input parameters in a dictionary which is prepared to be converted
    to cookie string.

    string user -- CIB user
    string group_list -- CIB user groups
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


def _create_request_handle(request, cookies, timeout):
    """
    Returns Curl object (easy handle) which is set up witc specified parameters.

    Request request -- request specification
    dict cookies -- cookies to add to request
    int timeout -- request timeout
    """

    # it is not possible to take this callback out of this function, because of
    # curl API
    def __debug_callback(data_type, debug_data):
        # pylint: disable=no-member
        prefixes = {
            pycurl.DEBUG_TEXT: b"* ",
            pycurl.DEBUG_HEADER_IN: b"< ",
            pycurl.DEBUG_HEADER_OUT: b"> ",
            pycurl.DEBUG_DATA_IN: b"<< ",
            pycurl.DEBUG_DATA_OUT: b">> ",
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
    handle.request_obj = request
    handle.output_buffer = output
    handle.debug_buffer = debug_output
    return handle


def _dict_to_cookies(cookies_dict):
    return ";".join(
        [
            "{0}={1}".format(key, value)
            for key, value in sorted(cookies_dict.items())
        ]
    )

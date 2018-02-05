import base64
import io
import re
from collections import namedtuple
from urllib.parse import urlencode

from pcs.common.host import Destination


# We should ignore SIGPIPE when using pycurl.NOSIGNAL - see the libcurl tutorial
# for more info.
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
except ImportError:
    pass

from pcs import settings
from pcs.common import pcs_pycurl as pycurl


def _find_value_for_possible_keys(value_dict, possible_key_list):
    for key in possible_key_list:
        if key in value_dict:
            return value_dict[key]
    return None


class NodeTargetFactory(object):
    def __init__(self, auth_tokens, ports):
        self._auth_tokens = auth_tokens
        self._ports = ports

    def _get_token(self, possible_names):
        return _find_value_for_possible_keys(self._auth_tokens, possible_names)

    def _get_port(self, possible_names):
        return _find_value_for_possible_keys(self._ports, possible_names)

    def get_target(self, node_addresses):
        possible_names = [node_addresses.label, node_addresses.ring0]
        if node_addresses.ring1:
            possible_names.append(node_addresses.ring1)
        return RequestTarget.from_node_addresses(
            node_addresses,
            token=self._get_token(possible_names),
            port=self._get_port(possible_names),
        )

    def get_target_list(self, node_addresses_list):
        return [self.get_target(node) for node in node_addresses_list]

    def get_target_from_hostname(self, hostname):
        return RequestTarget(
            hostname,
            token=self._get_token([hostname]),
            port=self._get_port([hostname]),
        )


class RequestData(
    namedtuple("RequestData", ["action", "structured_data", "data"])
):
    """
    This class represents action and data asociated with action which will be
    send in request
    """

    def __new__(cls, action, structured_data=()):
        """
        string action -- action to perform
        list structured_data -- list of tuples, data to send with specified
            action
        """
        return super(RequestData, cls).__new__(
            cls, action, structured_data, urlencode(structured_data)
        )



class RequestTarget(namedtuple(
    "RequestTarget", ["label", "host_connection_list", "token"]
)):
    """
    This class represents target (host) for request to be performed on
    """

    def __new__(cls, label, address_list=None, port=None, token=None):
        """
        string label -- label for the host, this is used as only hostname
            if address_list is not defined
        list address_list -- list of all possible hostnames on which the host is
            reachable
        int port -- target communnication port
        string token -- authentication token
        """
        if not address_list:
            address_list = [label]
        return super(RequestTarget, cls).__new__(
            cls,
            label,
            [Destination(addr, port) for addr in address_list],
            token,
        )

    @classmethod
    def from_node_addresses(cls, node_addresses, port=None, token=None):
        """
        Create object RequestTarget from NodeAddresses instance. Returns new
        RequestTarget instance.

        NodeAddresses node_addresses -- node which defines target
        string port -- target communnication port
        string token -- authentication token
        """
        address_list = [node_addresses.ring0]
        if node_addresses.ring1:
            address_list.append(node_addresses.ring1)
        return cls(
            node_addresses.label,
            address_list=address_list, port=port, token=token
        )


class Request(object):
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
        self._current_host_connection_iterator = iter(
            request_target.host_connection_list
        )
        self._current_host_connection = None
        self.next_host_connection()

    def next_host(self):
        """
        Deprecated
        TODO: remove
        """
        self.next_host_connection()

    def next_host_connection(self):
        """
        Move to the next available host connection. Raises StopIteration when
        there is no connection to use.
        """
        self._current_host_connection = next(
            self._current_host_connection_iterator
        )

    @property
    def url(self):
        """
        URL representing request using current host.
        """
        addr = self.host_connection.addr
        port = self.host_connection.port
        return "https://{host}:{port}/{request}".format(
            host="[{0}]".format(addr) if ":" in addr else addr,
            port=(port if port else settings.pcsd_default_port),
            request=self._data.action
        )

    # @property
    # def host(self):
    #     """
    #     Deprecated
    #     TODO: remove
    #     """
    #     return self.host_connection.addr
    #
    @property
    def host_connection(self):
        return self._current_host_connection

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


class Response(object):
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
        Returns Response instance that is marked as not successfuly connected.

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

class NodeCommunicatorFactory(object):
    def __init__(self, communicator_logger, user, groups, request_timeout):
        self._logger = communicator_logger
        self._user = user
        self._groups = groups
        self._request_timeout = request_timeout

    def get_communicator(self):
        return self.get_simple_communicator()

    def get_simple_communicator(self):
        return Communicator(
            self._logger, self._user, self._groups, self._request_timeout
        )

    def get_multiaddress_communicator(self):
        return MultiaddressCommunicator(
            self._logger, self._user, self._groups, self._request_timeout

        )


class Communicator(object):
    """
    This class provides simple interface for making parallel requests.
    The instances of this class are not thread-safe! It is intended to use it
    only in a single thread. Use an unique instance for each thread.
    """
    curl_multi_select_timeout_default = 0.8 # in seconds

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
                request, self._auth_cookies, self._request_timeout,
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
        to add new request to the queue while the generator is in progres.
        Generator will stop (raise StopIteration) after all requests (also those
        added after creation of generator) are processed.

        WARNING: do not use multiple instances of generator (of one
        Communicator instance) when there is one which didn't finish
        (raised StopIteration). It wil cause AssertionError.

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
                [Response.connection_successful(handle) for handle in ok_list] +
                [
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
            need_to_wait = (self._multi_handle.select(timeout) == -1)


class MultiaddressCommunicator(Communicator):
    """
    Class with same interface as Communicator. In difference with Communicator,
    it takes advantage of multiple hosts in RequestTarget. So if it is not
    possible to connect to target using first hostname, it will use next one
    until connection will be successful or there is no host left.
    """
    def start_loop(self):
        for response in super(MultiaddressCommunicator, self).start_loop():
            if response.was_connected:
                yield response
                continue
            try:
                previous_host_connection = response.request.host_connection
                response.request.next_host_connection()
                self._logger.log_retry(response, previous_host_connection)
                self.add_requests([response.request])
            except StopIteration:
                self._logger.log_no_more_addresses(response)
                yield response


class CommunicatorLoggerInterface(object):
    def log_request_start(self, request):
        raise NotImplementedError()

    def log_response(self, response):
        raise NotImplementedError()

    def log_retry(self, response, previous_host_connection):
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
        # python3 requires the value to be bytes not str
        cookies["CIB_user_groups"] = base64.b64encode(
            " ".join(group_list).encode("utf-8")
        )
    return cookies


def _create_request_handle(request, cookies, timeout):
    """
    Returns Curl object (easy handle) which is set up witc specified parameters.

    Request request -- request specification
    dict cookies -- cookies to add to request
    int timeot -- request timeout
    """
    # it is not possible to take this callback out of this function, because of
    # curl API
    def __debug_callback(data_type, debug_data):
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
    handle.setopt(pycurl.NOSIGNAL, 1) # required for multi-threading
    if cookies:
        handle.setopt(
            pycurl.COOKIE, _dict_to_cookies(cookies).encode("utf-8")
        )
    if request.data:
        handle.setopt(
            pycurl.COPYPOSTFIELDS, request.data.encode("utf-8")
        )
    # add reference for request object and output bufers to handle, so later
    # we don't need to match these objects when they are returned from
    # pycurl after they've been processed
    # similar usage is in pycurl example:
    # https://github.com/pycurl/pycurl/blob/REL_7_19_0_3/examples/retriever-multi.py
    handle.request_obj = request
    handle.output_buffer = output
    handle.debug_buffer = debug_output
    return handle


def _dict_to_cookies(cookies_dict):
    return ";".join([
        "{0}={1}".format(key, value)
        for key, value in sorted(cookies_dict.items())
    ])

from pcs.common import report_codes
from pcs.common.node_communicator import Request
from pcs.lib import reports
from pcs.lib.node_communication import response_to_report_item
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity,
)


def run(communicator, cmd):
    """
    Run communication command. Returns return value of method on_complete() of
    communcation command after run.

    NodeCommunicator communicator -- object used for communication
    CommunicationCommandInterface cmd
    """
    cmd.before()
    communicator.add_requests(cmd.get_initial_request_list())
    for response in communicator.start_loop():
        extra_requests = cmd.on_response(response)
        if extra_requests:
            communicator.add_requests(extra_requests)
    return cmd.on_complete()


def run_and_raise(communicator, cmd):
    """
    Run communication command. Returns return value of method on_complete() of
    communcation command after run.
    Raises LibraryError (with no report item) when some errors occured while
    running communication command.

    NodeCommunicator communicator -- object used for communication
    CommunicationCommandInterface cmd
    """
    to_return = run(communicator, cmd)
    if cmd.error_list:
        raise LibraryError()
    return to_return


class CommunicationCommandInterface(object):
    """
    Interface for all communication commands.
    """
    def get_initial_request_list(self):
        """
        Returns an initial list of Request object.
        """
        raise NotImplementedError()

    def on_response(self, response):
        """
        Process received response. Returns list of new Request that should be
        added to the executing queue.

        Response response -- a response to be processed
        """
        raise NotImplementedError()

    def on_complete(self):
        """
        Runs after all reqests finished.
        """
        raise NotImplementedError()

    def before(self):
        """
        Runs before executing the requests.
        """
        raise NotImplementedError()

    @property
    def error_list(self):
        """
        List of errors which occured during running the requests.
        """
        raise NotImplementedError()


class RunRemotelyBase(CommunicationCommandInterface):
    """
    Abstract class for communication commands. This class provides methods for
    reporting.
    """
    #pylint: disable=abstract-method
    def __init__(self, report_processor):
        self._report_processor = report_processor
        self._error_list = []

    def _get_response_report(self, response):
        """
        Convert specified response to report item. Returns None if the response
        has no failures.

        Response response -- a response to be converted
        """
        return response_to_report_item(response)

    def _report_list(self, report_list):
        """
        Send reports from report_list to the report processor.

        list report_list -- list of ReportItem objects
        """
        self._error_list.extend(self._report_processor.report_list(report_list))

    def _report(self, report):
        """
        Send specified report to the report processor.

        ReportItem report -- report which will be reported
        """
        self._report_list([report])

    def _process_response(self, response):
        """
        Process received response. Returns list of new Request that should be
        added to the executing queue. If no new Request should be added, there
        is no need to return empty list.

        Response response -- a response to be processed
        """
        raise NotImplementedError()

    def on_response(self, response):
        returned = self._process_response(response)
        return returned if returned else []

    def on_complete(self):
        return None

    def before(self):
        pass

    @property
    def error_list(self):
        return self._error_list


class StrategyBase(object):
    """
    Abstract base class of the communication strategies. Always use at most one
    strategy mixin in the communication commands classes.
    """
    def _prepare_initial_requests(self):
        """
        Returns list of all Request objects which should be run. Full
        implementation of strategy will use this list for creating initial
        request list and others.
        """
        raise NotImplementedError()

    def get_initial_request_list(self):
        """
        This method has to be implemented by the descendants.
        """
        raise NotImplementedError()


class OneByOneStrategyMixin(StrategyBase):
    """
    Communication strategy in which requests are executed one by one. So only one
    request from _prepare_initial_requests is chosen as initial request list.
    Other requests are then available by calling method _get_next_list.
    """
    #pylint: disable=abstract-method
    __iter = None
    __successful = False

    def get_initial_request_list(self):
        """
        Returns only first request from _prepare_initial_requests.
        """
        self.__iter = iter(self._prepare_initial_requests())
        return self._get_next_list()

    def _get_next_list(self):
        """
        Returns a list which contains another Request object from
        _prepare_initial_requests. Raises StopIteration when there is no other
        request left.
        """
        try:
            return [next(self.__iter)]
        except StopIteration:
            return []

    def _on_success(self):
        self.__successful = True

    def on_complete(self):
        if not self.__successful:
            self._report(reports.unable_to_perform_operation_on_any_node())
        return None


class AllAtOnceStrategyMixin(StrategyBase):
    """
    Communication strategy in which all requests are executed at once in
    parallel.
    """
    #pylint: disable=abstract-method
    def get_initial_request_list(self):
        return self._prepare_initial_requests()


class AllSameDataMixin(object):
    """
    Communication command mixin which adds common methods for commands where
    requests to all targets have the same data.
    """
    __targets = None

    def _get_request_data(self):
        """
        Returns RequestData object to use as data for requests to all targets.
        """
        raise NotImplementedError()

    def _prepare_initial_requests(self):
        return [
            Request(target, self._get_request_data())
            for target in self.__target_list
        ]

    def add_request(self, target):
        """
        Add target to which request will be send.

        RequestTarget target -- target that will be added.
        """
        self.set_targets([target])

    def set_targets(self, target_list):
        """
        Add targets to which requests will be send.

        list target_list -- RequestTarget list
        """
        self.__target_list.extend(target_list)

    @property
    def __target_list(self):
        if self.__targets is None:
            self.__targets = []
        return self.__targets

    @property
    def _target_list(self):
        """
        List of RequestTarget to which request will be send.
        """
        return list(self.__target_list)

    @property
    def _target_label_list(self):
        return [target.label for target in self.__target_list]



class SimpleResponseProcessingMixin(object):
    """
    Communication command mixin which adds common response processing. When
    request fails error/warning will be reported. Otherwise _get_success_report
    will be reported.
    """
    def _get_success_report(self, node_label):
        """
        Returns ReportItem which should be reported when request was
        successfull.

        string node_label -- node identifier on which request was successful
        """
        raise NotImplementedError()

    def _process_response(self, response):
        report = self._get_response_report(response)
        if report is None:
            report = self._get_success_report(response.request.target.label)
        self._report(report)


class SimpleResponseProcessingNoResponseOnSuccessMixin(object):
    """
    Communication command mixin which adds common response processing. When
    request fails error/warning will be reported.
    """
    def _process_response(self, response):
        report = self._get_response_report(response)
        if report is not None:
            self._report(report)


class SkipOfflineMixin(object):
    """
    Communication command mixin which simplifies handling of forcing skip
    offline nodes. This mixin provides method _set_skip_offline which should be
    called from __init__ of the descendants. Then report item from response
    returned from _get_response_report is set accordingly to value of
    skip_offline_targets.
    """
    _failure_severity = ReportItemSeverity.ERROR
    _failure_forceable = None

    def _set_skip_offline(
        self, skip_offline_targets, force_code=report_codes.SKIP_OFFLINE_NODES
    ):
        """
        Set value of skip_offline_targets flag.

        boolean skip_offline_targets
        """
        self._failure_forceable = force_code
        if skip_offline_targets:
            self._failure_severity = ReportItemSeverity.WARNING
            self._failure_forceable = None

    def _get_response_report(self, response):
        return response_to_report_item(
            response,
            severity=self._failure_severity,
            forceable=self._failure_forceable,
        )

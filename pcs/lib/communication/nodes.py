import json

from pcs.common import report_codes
from pcs.common.node_communicator import RequestData
from pcs.lib import reports, node_communication_format
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    RunRemotelyBase,
    SkipOfflineMixin,
    SimpleResponseProcessingMixin,
    SimpleResponseProcessingNoResponseOnSuccessMixin,
)
from pcs.lib.errors import ReportItemSeverity
from pcs.lib.node_communication import response_to_report_item


class GetOnlineTargets(
    AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(self, report_processor, ignore_offline_targets=False):
        super(GetOnlineTargets, self).__init__(report_processor)
        self._ignore_offline_targets = ignore_offline_targets
        self._online_target_list = []

    def _get_request_data(self):
        return RequestData("remote/check_auth", [("check_auth_only", 1)])

    def _process_response(self, response):
        report = response_to_report_item(response)
        if report is None:
            self._online_target_list.append(response.request.target)
            return
        if not response.was_connected:
            report = (
                reports.omitting_node(response.request.target.label)
                if self._ignore_offline_targets
                else response_to_report_item(
                    response, forceable=report_codes.SKIP_OFFLINE_NODES
                )
            )
        self._report(report)

    def on_complete(self):
        return self._online_target_list


class CheckAuth(AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super(CheckAuth, self).__init__(report_processor)
        self._not_authorized_host_name_list = []

    def _get_request_data(self):
        # check_auth_only is not used anymore. It was used in older pcsd to
        # prevent a node to check against which nodes it is authorized and
        # reporting that info. We are not interested in that anymore (it made
        # sense to check it when authentication was bidirectional). So we tell
        # the node not to do this extra check.
        return RequestData("remote/check_auth", [("check_auth_only", 1)])

    def _process_response(self, response):
        report = response_to_report_item(
            response, severity=ReportItemSeverity.INFO
        )
        host_name = response.request.target.label
        if report is None:
            report = reports.host_already_authorized(host_name)
        else:
            # If we cannot connect it may be because a node's address and / or
            # port is not correct. Since these are part of authentication info
            # we tell we're not authorized.
            self._not_authorized_host_name_list.append(host_name)
        self._report(report)

    def on_complete(self):
        return self._not_authorized_host_name_list


class GetHostInfo(AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase):
    _responses = None

    def _get_request_data(self):
        return RequestData("remote/check_host")

    def _process_response(self, response):
        report = self._get_response_report(response)
        if report:
            self._report(report)
            return
        host_name = response.request.target.label
        try:
            self._responses[host_name] = json.loads(response.data)
        except json.JSONDecodeError:
            self._report(reports.invalid_response_format(host_name))

    def before(self):
        self._responses = {}

    def on_complete(self):
        return self._responses


class PrecheckNewNode(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(
        self, report_items, check_response, skip_offline_targets=False
    ):
        super(PrecheckNewNode, self).__init__(None)
        self._set_skip_offline(skip_offline_targets)
        self._report_items = report_items
        self._check_response = check_response

    def _get_request_data(self):
        return RequestData("remote/node_available")

    def _process_response(self, response):
        # do not send outside any report, just append them into specified list
        report = self._get_response_report(response)
        if report:
            self._report_items.append(report)
            return
        target = response.request.target
        data = None
        try:
            data = json.loads(response.data)
        except ValueError:
            self._report_items.append(
                reports.invalid_response_format(target.label)
            )
            return
        is_in_expected_format = (
            #node_available is a mandatory field
            isinstance(data, dict) and "node_available" in data
        )
        if not is_in_expected_format:
            self._report_items.append(
                reports.invalid_response_format(target.label)
            )
            return
        self._check_response(data, self._report_items, target.label)


class RunActionBase(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(
        self, report_processor, action_definition,
        skip_offline_targets=False, allow_fails=False, description="",
    ):
        super(RunActionBase, self).__init__(report_processor)
        self._init_properties()
        self._set_skip_offline(skip_offline_targets)
        self._action_error_force = _force(self._force_code, allow_fails)
        self._action_definition = action_definition
        self._description = description

    def _init_properties(self):
        raise NotImplementedError()

    def _is_success(self, action_response):
        raise NotImplementedError()

    def _get_request_data(self):
        return RequestData(
            self._request_url,
            [("data_json", json.dumps(self._action_definition))],
        )

    def _process_response(self, response):
        report = self._get_response_report(response)
        if report:
            self._report(report)
            return
        results = None
        target = response.request.target
        try:
            results = json.loads(response.data)
        except ValueError:
            self._report(reports.invalid_response_format(target.label))
            return
        results = node_communication_format.response_to_result(
            results,
            self._response_key,
            self._action_definition.keys(),
            target.label
        )
        for key, item_response in sorted(results.items()):
            if self._is_success(item_response):
                #only success process individually
                report = self._success_report(target.label, key)
            else:
                report = self._failure_report(
                    target.label,
                    key,
                    node_communication_format.get_format_result(
                        self._code_message_map
                    )(item_response),
                    **self._action_error_force
                )
            self._report(report)

    def before(self):
        self._report(self._start_report(
            self._action_definition.keys(),
            [target.label for target in self._target_list],
            self._description
        ))


class ServiceAction(RunActionBase):
    def _init_properties(self):
        self._request_url = "remote/manage_services"
        self._response_key = "actions"
        self._force_code = report_codes.SKIP_ACTION_ON_NODES_ERRORS
        self._start_report = reports.service_commands_on_nodes_started
        self._success_report = reports.service_command_on_node_success
        self._failure_report = reports.service_command_on_node_error
        self._code_message_map = {"fail": "Operation failed."}

    def _is_success(self, action_response):
        return action_response.code == "success"


class FileActionBase(RunActionBase):
    #pylint: disable=abstract-method
    def _init_properties(self):
        self._response_key = "files"
        self._force_code = report_codes.SKIP_FILE_DISTRIBUTION_ERRORS


class DistributeFiles(FileActionBase):
    def _init_properties(self):
        super(DistributeFiles, self)._init_properties()
        self._request_url = "remote/put_file"
        self._start_report = reports.files_distribution_started
        self._success_report = reports.file_distribution_success
        self._failure_report = reports.file_distribution_error
        self._code_message_map = {"conflict": "File already exists"}

    def _is_success(self, action_response):
        return action_response.code in ["written", "rewritten", "same_content"]


class DistributeFilesWithoutForces(DistributeFiles):
    def _init_properties(self):
        super()._init_properties()
        # We don't want to allow any kind of force or skip, therefore all force
        # codes have to be set to None
        self._force_code = None
        # _failure_forceable is defined in SkipOfflineMixin
        self._failure_forceable = None


class RemoveFiles(FileActionBase):
    def _init_properties(self):
        super(RemoveFiles, self)._init_properties()
        self._request_url = "remote/remove_file"
        self._start_report = reports.files_remove_from_node_started
        self._success_report = reports.file_remove_from_node_success
        self._failure_report = reports.file_remove_from_node_error
        self._code_message_map = {}

    def _is_success(self, action_response):
        return action_response.code in ["deleted", "not_found"]


class RemoveFilesWithoutForces(RemoveFiles):
    def _init_properties(self):
        super()._init_properties()
        # We don't want to allow any kind of force or skip, therefore all force
        # codes have to be set to None
        self._force_code = None
        # _failure_forceable is defined in SkipOfflineMixin
        self._failure_forceable = None


class StartCluster(
    SimpleResponseProcessingNoResponseOnSuccessMixin, AllSameDataMixin,
    AllAtOnceStrategyMixin, RunRemotelyBase,
):
    def _get_request_data(self):
        return RequestData("remote/cluster_start")

    def before(self):
        self._report(reports.cluster_start_started(self._target_label_list))


class EnableCluster(
    SimpleResponseProcessingMixin, AllSameDataMixin, AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def _get_request_data(self):
        return RequestData("remote/cluster_enable")

    def _get_success_report(self, node_label):
        return reports.cluster_enable_success(node_label)

    def before(self):
        self._report(reports.cluster_enable_started(self._target_label_list))


class CheckPacemakerStarted(
    AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    _not_yet_started_target_list = None

    def _get_request_data(self):
        return RequestData("remote/pacemaker_node_status")

    def _process_response(self, response):
        report = response_to_report_item(response)
        target = response.request.target
        if report is None:
            try:
                parsed_response = json.loads(response.data)
                if not parsed_response["online"] or parsed_response["pending"]:
                    self._not_yet_started_target_list.append(target)
                    return
                else:
                    report = reports.cluster_start_success(target.label)
            except (json.JSONDecodeError, KeyError):
                report = reports.invalid_response_format(target.label)
        else:
            if not response.was_connected:
                self._not_yet_started_target_list.append(target)
        self._report(report)

    def before(self):
        self._not_yet_started_target_list = []

    def on_complete(self):
        return self._not_yet_started_target_list


class UpdateKnownHosts(
    SimpleResponseProcessingNoResponseOnSuccessMixin, AllSameDataMixin,
    AllAtOnceStrategyMixin, RunRemotelyBase,
):
    def __init__(
        self, report_processor, known_hosts_to_add, known_hosts_to_remove
    ):
        super().__init__(report_processor)
        self._json_data = dict(
            known_hosts_add=dict(
                [host.to_known_host_dict() for host in known_hosts_to_add]
            ),
            known_hosts_remove=dict(
                [host.to_known_host_dict() for host in known_hosts_to_remove]
            ),
        )

    def _get_request_data(self):
        return RequestData(
            "remote/known_hosts_change",
            [("data_json", json.dumps(self._json_data))],
        )


def _force(force_code, is_forced):
    if is_forced:
        return dict(
            severity=ReportItemSeverity.WARNING,
            forceable=None,
        )
    return dict(
        severity=ReportItemSeverity.ERROR,
        forceable=force_code,
    )


def availability_checker_node(availability_info, report_items, node_label):
    """
    Check if availability_info means that the node is suitable as cluster
    (corosync) node.
    """
    if availability_info["node_available"]:
        return

    if availability_info.get("pacemaker_running", False):
        report_items.append(reports.cannot_add_node_is_running_service(
            node_label,
            "pacemaker"
        ))
        return

    if availability_info.get("pacemaker_remote", False):
        report_items.append(reports.cannot_add_node_is_running_service(
            node_label,
            "pacemaker_remote"
        ))
        return

    report_items.append(reports.cannot_add_node_is_in_cluster(node_label))

def availability_checker_remote_node(
    availability_info, report_items, node_label
):
    """
    Check if availability_info means that the node is suitable as remote node.
    """
    if availability_info["node_available"]:
        return

    if availability_info.get("pacemaker_running", False):
        report_items.append(reports.cannot_add_node_is_running_service(
            node_label,
            "pacemaker"
        ))
        return

    if not availability_info.get("pacemaker_remote", False):
        report_items.append(reports.cannot_add_node_is_in_cluster(node_label))
        return

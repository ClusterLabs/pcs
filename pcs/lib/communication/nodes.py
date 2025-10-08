import json
from typing import Mapping

from pcs.common import reports
from pcs.common.auth import HostAuthData
from pcs.common.node_communicator import (
    Request,
    RequestData,
    RequestTarget,
    Response,
)
from pcs.common.reports import ReportItemSeverity
from pcs.common.reports import codes as report_codes
from pcs.common.reports.item import ReportItem
from pcs.lib import node_communication_format
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    RunRemotelyBase,
    SimpleResponseProcessingMixin,
    SimpleResponseProcessingNoResponseOnSuccessMixin,
    SkipOfflineMixin,
)
from pcs.lib.node_communication import response_to_report_item


class GetOnlineTargets(
    AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(self, report_processor, ignore_offline_targets=False):
        super().__init__(report_processor)
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
                ReportItem.warning(
                    reports.messages.OmittingNode(response.request.target.label)
                )
                if self._ignore_offline_targets
                else response_to_report_item(
                    response, forceable=report_codes.SKIP_OFFLINE_NODES
                )
            )
        self._report(report)

    def on_complete(self):
        return self._online_target_list


class CheckReachability(
    AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    REACHABLE = "REACHABLE"
    UNREACHABLE = "UNREACHABLE"
    UNAUTH = "UNAUTH"

    def __init__(self, report_processor):
        super().__init__(report_processor)
        self._node_reachability = {}

    def _get_request_data(self):
        return RequestData("remote/check_auth", [("check_auth_only", 1)])

    def _process_response(self, response):
        host = response.request.host_label
        if not response.was_connected:
            self._node_reachability[host] = self.UNREACHABLE
            return
        if response.response_code == 401:
            self._node_reachability[host] = self.UNAUTH
            return
        self._node_reachability[host] = self.REACHABLE

    def on_complete(self):
        return self._node_reachability


class CheckAuth(AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super().__init__(report_processor)
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
            report = ReportItem.info(
                reports.messages.HostAlreadyAuthorized(host_name)
            )
        else:
            # If we cannot connect it may be because a node's address and / or
            # port is not correct. Since these are part of authentication info
            # we tell we're not authorized.
            self._not_authorized_host_name_list.append(host_name)
        self._report(report)

    def on_complete(self):
        return self._not_authorized_host_name_list


class Auth(AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(
        self,
        auth_data: Mapping[str, HostAuthData],
        report_processor: reports.ReportProcessor,
    ) -> None:
        super().__init__(report_processor)
        self._auth_data = auth_data
        self._tokens: dict[str, str] = {}

    def _prepare_initial_requests(self):
        return [
            Request(
                RequestTarget(host_name, dest_list=auth_data.dest_list),
                RequestData(
                    action="remote/auth",
                    structured_data=[
                        ("username", auth_data.username),
                        ("password", auth_data.password),
                    ],
                ),
            )
            for host_name, auth_data in self._auth_data.items()
        ]

    def _process_response(self, response: Response):
        report = response_to_report_item(response)
        if report:
            self._report(report)
            return

        node_label = response.request.target.label
        context = reports.ReportItemContext(node_label)
        token = response.data.strip()
        if token:
            self._tokens[node_label] = token
            self._report(
                reports.ReportItem.info(
                    reports.messages.AuthorizationSuccessful(), context=context
                )
            )
        else:
            self._report(
                reports.ReportItem.error(
                    reports.messages.IncorrectCredentials(), context=context
                )
            )

    def on_complete(self) -> dict[str, str]:
        return self._tokens


class GetHostInfo(AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase):
    _responses = None
    _report_pcsd_too_old_on_404 = True

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
            self._report(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(host_name)
                )
            )

    def before(self):
        self._responses = {}

    def on_complete(self):
        return self._responses


class RunActionBase(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    _request_url = None
    _response_key = None
    _force_code = None
    _code_message_map = None

    def __init__(
        self,
        report_processor,
        action_definition,
        skip_offline_targets=False,
        allow_fails=False,
    ):
        super().__init__(report_processor)
        self._set_skip_offline(skip_offline_targets)
        self._init_properties()
        self._action_error_force = _force(self._force_code, allow_fails)
        self._action_definition = action_definition
        # Pacemaker has only one authkey, there is no a remote and an ordinary
        # one. However, we cannot change it now in the network communication
        # due to backward compatibility. So we translate that for reports only.
        self._key_to_report = {
            "pacemaker_remote authkey": "pacemaker authkey",
        }

    def _init_properties(self):
        raise NotImplementedError()

    def _is_success(self, action_response):
        raise NotImplementedError()

    def _failure_report(
        self, target_label, action, reason, severity, forceable
    ):
        raise NotImplementedError()

    def _success_report(self, target_label, action):
        raise NotImplementedError()

    def _start_report(self, action_list, target_label_list):
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
            self._report(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(target.label)
                )
            )
            return
        results = node_communication_format.response_to_result(
            results,
            self._response_key,
            list(self._action_definition.keys()),
            target.label,
        )
        for key, item_response in sorted(results.items()):
            if self._is_success(item_response):
                # only success process individually
                report = self._success_report(
                    target.label,
                    self._action_key_to_report(key),
                )
            else:
                report = self._failure_report(
                    target.label,
                    self._action_key_to_report(key),
                    node_communication_format.get_format_result(
                        self._code_message_map
                    )(item_response),
                    **self._action_error_force,
                )
            self._report(report)

    def before(self):
        self._report(
            self._start_report(
                [
                    self._action_key_to_report(key)
                    for key in self._action_definition
                ],
                [target.label for target in self._target_list],
            )
        )

    def _action_key_to_report(self, key):
        return self._key_to_report.get(key, key)


class ServiceAction(RunActionBase):
    def _init_properties(self):
        self._request_url = "remote/manage_services"
        self._response_key = "actions"
        self._force_code = report_codes.FORCE
        self._code_message_map = {"fail": "Operation failed."}

    def _failure_report(
        self, target_label, action, reason, severity, forceable
    ):
        return ReportItem(
            severity=reports.item.ReportItemSeverity(severity, forceable),
            message=reports.messages.ServiceCommandOnNodeError(
                target_label, action, reason
            ),
        )

    def _success_report(self, target_label, action):
        return ReportItem.info(
            reports.messages.ServiceCommandOnNodeSuccess(target_label, action)
        )

    def _start_report(self, action_list, target_label_list):
        return ReportItem.info(
            reports.messages.ServiceCommandsOnNodesStarted(
                action_list, target_label_list
            )
        )

    def _is_success(self, action_response):
        return action_response.code == "success"


class FileActionBase(RunActionBase):
    # pylint: disable=abstract-method
    def _init_properties(self):
        self._response_key = "files"
        self._force_code = report_codes.FORCE


class DistributeFiles(FileActionBase):
    def _init_properties(self):
        super()._init_properties()
        self._request_url = "remote/put_file"
        self._code_message_map = {"conflict": "File already exists"}

    def _failure_report(
        self, target_label, action, reason, severity, forceable
    ):
        return ReportItem(
            severity=reports.item.ReportItemSeverity(severity, forceable),
            message=reports.messages.FileDistributionError(
                target_label, action, reason
            ),
        )

    def _success_report(self, target_label, action):
        return ReportItem.info(
            reports.messages.FileDistributionSuccess(target_label, action)
        )

    def _start_report(self, action_list, target_label_list):
        return ReportItem.info(
            reports.messages.FilesDistributionStarted(
                action_list, target_label_list
            )
        )

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
        super()._init_properties()
        self._request_url = "remote/remove_file"
        self._code_message_map = {}

    def _failure_report(
        self, target_label, action, reason, severity, forceable
    ):
        return ReportItem(
            severity=reports.item.ReportItemSeverity(severity, forceable),
            message=reports.messages.FileRemoveFromNodeError(
                target_label, action, reason
            ),
        )

    def _success_report(self, target_label, action):
        return ReportItem.info(
            reports.messages.FileRemoveFromNodeSuccess(target_label, action)
        )

    def _start_report(self, action_list, target_label_list):
        return ReportItem.info(
            reports.messages.FilesRemoveFromNodesStarted(
                action_list, target_label_list
            )
        )

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
    SimpleResponseProcessingNoResponseOnSuccessMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def _get_request_data(self):
        return RequestData("remote/cluster_start")

    def before(self):
        self._report(
            ReportItem.info(
                reports.messages.ClusterStartStarted(
                    sorted(self._target_label_list)
                )
            )
        )


class EnableCluster(
    SimpleResponseProcessingMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def _get_request_data(self):
        return RequestData("remote/cluster_enable")

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.ClusterEnableSuccess(node_label)
        )

    def before(self):
        self._report(
            ReportItem.info(
                reports.messages.ClusterEnableStarted(
                    sorted(self._target_label_list)
                )
            )
        )


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
                # If the node is offline, we only get the "offline" key. Asking
                # for any other in that case results in KeyError which is not
                # what we want.
                if parsed_response.get(
                    "pending", True
                ) or not parsed_response.get("online", False):
                    self._not_yet_started_target_list.append(target)
                    return
                report = ReportItem.info(
                    reports.messages.ClusterStartSuccess(target.label)
                )
            except (json.JSONDecodeError, KeyError):
                report = ReportItem.error(
                    reports.messages.InvalidResponseFormat(target.label)
                )

        elif not response.was_connected:
            self._not_yet_started_target_list.append(target)
            report = response_to_report_item(
                response, severity=ReportItemSeverity.WARNING
            )
        self._report(report)

    def before(self):
        self._not_yet_started_target_list = []

    def on_complete(self):
        return self._not_yet_started_target_list


class UpdateKnownHosts(
    SimpleResponseProcessingNoResponseOnSuccessMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
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


class RemoveNodesFromCib(
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def __init__(self, report_processor, nodes_to_remove):
        super().__init__(report_processor)
        self._nodes_to_remove = nodes_to_remove

    def _get_request_data(self):
        return RequestData(
            "remote/remove_nodes_from_cib",
            [("data_json", json.dumps(dict(node_list=self._nodes_to_remove)))],
        )

    def _process_response(self, response):
        report = self._get_response_report(response)
        if report is not None:
            self._report(report)
            return
        node_label = response.request.target.label
        try:
            output = json.loads(response.data)
            if output["code"] != "success":
                self._report(
                    ReportItem.error(
                        reports.messages.NodeRemoveInPacemakerFailed(
                            node_list_to_remove=self._nodes_to_remove,
                            node=node_label,
                            reason=output["message"],
                        )
                    )
                )
        except (KeyError, json.JSONDecodeError):
            self._report(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(node_label)
                )
            )


class SendPcsdSslCertAndKey(
    SimpleResponseProcessingMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def __init__(self, report_processor, ssl_cert, ssl_key):
        super().__init__(report_processor)
        self._ssl_cert = ssl_cert
        self._ssl_key = ssl_key

    def _get_request_data(self):
        return RequestData(
            "remote/set_certs",
            [("ssl_cert", self._ssl_cert), ("ssl_key", self._ssl_key)],
        )

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.PcsdSslCertAndKeySetSuccess(node_label)
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

import json

from pcs.common.node_communicator import (
    Request,
    RequestData,
)
from pcs.lib import reports
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    MarkSuccessfulMixin,
    OneByOneStrategyMixin,
    RunRemotelyBase,
    SimpleResponseProcessingMixin,
)
from pcs.lib.errors import ReportItemSeverity
from pcs.lib.node_communication import response_to_report_item
from pcs.lib.tools import environment_file_to_dict


class ServiceAction(
    SimpleResponseProcessingMixin, AllSameDataMixin, AllAtOnceStrategyMixin,
    RunRemotelyBase
):
    def _get_request_action(self):
        raise NotImplementedError()

    def _get_before_report(self):
        raise NotImplementedError()

    def _get_success_report(self, node_label):
        raise NotImplementedError()

    def _get_request_data(self):
        return RequestData(self._get_request_action())

    def before(self):
        self._report(self._get_before_report())


class EnableSbdService(ServiceAction):
    def _get_request_action(self):
        return "remote/sbd_enable"

    def _get_before_report(self):
        return reports.sbd_enabling_started()

    def _get_success_report(self, node_label):
        return reports.service_enable_success("sbd", node_label)


class DisableSbdService(ServiceAction):
    def _get_request_action(self):
        return "remote/sbd_disable"

    def _get_before_report(self):
        return reports.sbd_disabling_started()

    def _get_success_report(self, node_label):
        return reports.service_disable_success("sbd", node_label)


class StonithWatchdogTimeoutAction(
    AllSameDataMixin, MarkSuccessfulMixin, OneByOneStrategyMixin,
    RunRemotelyBase,
):
    def _get_request_action(self):
        raise NotImplementedError()

    def _get_request_data(self):
        return RequestData(self._get_request_action())

    def _process_response(self, response):
        report = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        if report is None:
            self._on_success()
            return
        self._report(report)
        return self._get_next_list()


class RemoveStonithWatchdogTimeout(StonithWatchdogTimeoutAction):
    def _get_request_action(self):
        return "remote/remove_stonith_watchdog_timeout"


class SetStonithWatchdogTimeoutToZero(StonithWatchdogTimeoutAction):
    def _get_request_action(self):
        return "remote/set_stonith_watchdog_timeout_to_zero"


class SetSbdConfig(
    SimpleResponseProcessingMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(self, report_processor):
        super(SetSbdConfig, self).__init__(report_processor)
        self._request_data_list = []

    def _prepare_initial_requests(self):
        return [
            Request(
                target,
                RequestData("remote/set_sbd_config", [("config", config)])
            ) for target, config in self._request_data_list
        ]

    def _get_success_report(self, node_label):
        return reports.sbd_config_accepted_by_node(node_label)

    def add_request(self, target, config):
        self._request_data_list.append((target, config))

    def before(self):
        self._report(reports.sbd_config_distribution_started())


class GetSbdConfig(AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super(GetSbdConfig, self).__init__(report_processor)
        self._config_list = []
        self._successful_target_list = []

    def _get_request_data(self):
        return RequestData("remote/get_sbd_config")

    def _process_response(self, response):
        report = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        node_label = response.request.target.label
        if report is not None:
            if not response.was_connected:
                self._report(report)
            self._report(
                reports.unable_to_get_sbd_config(
                    node_label, "", ReportItemSeverity.WARNING
                )
            )
            return
        self._config_list.append({
            "node": node_label,
            "config": environment_file_to_dict(response.data)
        })
        self._successful_target_list.append(node_label)

    def on_complete(self):
        for node in self._target_list:
            if node.label not in self._successful_target_list:
                self._config_list.append({
                    "node": node.label,
                    "config": None
                })
        return self._config_list


class GetSbdStatus(AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super(GetSbdStatus, self).__init__(report_processor)
        self._status_list = []
        self._successful_target_list = []

    def _get_request_data(self):
        return RequestData("remote/check_sbd",
            # here we just need info about sbd service, therefore watchdog and
            # device list is empty
            [
                ("watchdog", ""),
                ("device_list", "[]"),
            ]
        )

    def _process_response(self, response):
        report = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        node_label = response.request.target.label
        if report is not None:
            self._report_list([
                report,
                #reason is in previous report item, warning is there implicit
                reports.unable_to_get_sbd_status(node_label, "")
            ])
            return
        try:
            self._status_list.append({
                "node": node_label,
                "status": json.loads(response.data)["sbd"]
            })
            self._successful_target_list.append(node_label)
        except (ValueError, KeyError) as e:
            self._report(reports.unable_to_get_sbd_status(node_label, str(e)))

    def on_complete(self):
        for node in self._target_list:
            if node.label not in self._successful_target_list:
                self._status_list.append({
                    "node": node.label,
                    "status": {
                        "installed": None,
                        "enabled": None,
                        "running": None
                    }
                })
        return self._status_list


class CheckSbd(AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super(CheckSbd, self).__init__(report_processor)
        self._request_data_list = []

    def _prepare_initial_requests(self):
        return [
            Request(
                target,
                RequestData(
                    "remote/check_sbd",
                    [
                        ("watchdog", watchdog),
                        ("device_list", json.dumps(device_list))
                    ]
                )
            ) for target, watchdog, device_list in self._request_data_list
        ]

    def _process_response(self, response):
        report = response_to_report_item(response)
        if report:
            self._report(report)
            return
        report_list = []
        node_label = response.request.target.label
        try:
            data = json.loads(response.data)
            if not data["sbd"]["installed"]:
                report_list.append(reports.sbd_not_installed(node_label))
            if not data["watchdog"]["exist"]:
                report_list.append(reports.watchdog_not_found(
                    node_label, data["watchdog"]["path"]
                ))
            for device in data.get("device_list", []):
                if not device["exist"]:
                    report_list.append(reports.sbd_device_does_not_exist(
                        device["path"], node_label
                    ))
                elif not device["block_device"]:
                    report_list.append(reports.sbd_device_is_not_block_device(
                        device["path"], node_label
                    ))
                # TODO maybe we can check whenever device is initialized by sbd (by
                # running 'sbd -d <dev> dump;')
        except (ValueError, KeyError, TypeError):
            report_list.append(reports.invalid_response_format(node_label))
        if report_list:
            self._report_list(report_list)
        else:
            self._report(
                reports.sbd_check_success(response.request.target.label)
            )

    def add_request(self, target, watchdog, device_list):
        self._request_data_list.append((target, watchdog, device_list))

    def before(self):
        self._report(reports.sbd_check_started())

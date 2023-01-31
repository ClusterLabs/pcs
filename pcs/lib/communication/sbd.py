import json

from pcs.common import reports
from pcs.common.node_communicator import (
    Request,
    RequestData,
)
from pcs.common.reports import ReportItemSeverity
from pcs.common.reports.item import ReportItem
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    MarkSuccessfulMixin,
    OneByOneStrategyMixin,
    RunRemotelyBase,
    SimpleResponseProcessingMixin,
)
from pcs.lib.node_communication import response_to_report_item
from pcs.lib.tools import environment_file_to_dict


class ServiceAction(
    SimpleResponseProcessingMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
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
        return ReportItem.info(
            reports.messages.ServiceActionStarted(
                reports.const.SERVICE_ACTION_ENABLE, "sbd"
            )
        )

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                reports.const.SERVICE_ACTION_ENABLE, "sbd", node_label
            )
        )


class DisableSbdService(ServiceAction):
    def _get_request_action(self):
        return "remote/sbd_disable"

    def _get_before_report(self):
        return ReportItem.info(
            reports.messages.ServiceActionStarted(
                reports.const.SERVICE_ACTION_DISABLE,
                "sbd",
            )
        )

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                reports.const.SERVICE_ACTION_DISABLE, "sbd", node_label
            )
        )


class StonithWatchdogTimeoutAction(
    AllSameDataMixin,
    MarkSuccessfulMixin,
    OneByOneStrategyMixin,
    RunRemotelyBase,
):
    def _get_request_action(self):
        raise NotImplementedError()

    def _get_request_data(self):
        return RequestData(self._get_request_action())

    def _process_response(self, response):
        report_item = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        if report_item is None:
            self._on_success()
        else:
            self._report(report_item)
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
        super().__init__(report_processor)
        self._request_data_list = []

    def _prepare_initial_requests(self):
        return [
            Request(
                target,
                RequestData("remote/set_sbd_config", [("config", config)]),
            )
            for target, config in self._request_data_list
        ]

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.SbdConfigAcceptedByNode(node_label)
        )

    def add_request(self, target, config):
        self._request_data_list.append((target, config))

    def before(self):
        self._report(
            ReportItem.info(reports.messages.SbdConfigDistributionStarted())
        )


class GetSbdConfig(AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super().__init__(report_processor)
        self._config_list = []
        self._successful_target_list = []

    def _get_request_data(self):
        return RequestData("remote/get_sbd_config")

    def _process_response(self, response):
        report_item = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        node_label = response.request.target.label
        if report_item is not None:
            if not response.was_connected:
                self._report(report_item)
            self._report(
                ReportItem.warning(
                    reports.messages.UnableToGetSbdConfig(node_label, "")
                )
            )
            return
        self._config_list.append(
            {
                "node": node_label,
                "config": environment_file_to_dict(response.data),
            }
        )
        self._successful_target_list.append(node_label)

    def on_complete(self):
        for node in self._target_list:
            if node.label not in self._successful_target_list:
                self._config_list.append({"node": node.label, "config": None})
        return self._config_list


class GetSbdStatus(AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super().__init__(report_processor)
        self._status_list = []
        self._successful_target_list = []

    def _get_request_data(self):
        return RequestData(
            "remote/check_sbd",
            # here we just need info about sbd service, therefore watchdog and
            # device list is empty
            [
                ("watchdog", ""),
                ("device_list", "[]"),
            ],
        )

    def _process_response(self, response):
        report_item = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        node_label = response.request.target.label
        if report_item is not None:
            self._report_list(
                [
                    report_item,
                    # reason is in previous report item, warning is there
                    # implicit
                    ReportItem.warning(
                        reports.messages.UnableToGetSbdStatus(node_label, "")
                    ),
                ]
            )
            return
        try:
            self._status_list.append(
                {"node": node_label, "status": json.loads(response.data)["sbd"]}
            )
            self._successful_target_list.append(node_label)
        except (ValueError, KeyError) as e:
            self._report(
                ReportItem.warning(
                    reports.messages.UnableToGetSbdStatus(node_label, str(e))
                )
            )

    def on_complete(self):
        for node in self._target_list:
            if node.label not in self._successful_target_list:
                self._status_list.append(
                    {
                        "node": node.label,
                        "status": {
                            "installed": None,
                            "enabled": None,
                            "running": None,
                        },
                    }
                )
        return self._status_list


class CheckSbd(AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super().__init__(report_processor)
        self._request_data_list = []

    def _prepare_initial_requests(self):
        return [
            Request(
                target,
                RequestData(
                    "remote/check_sbd",
                    [
                        ("watchdog", watchdog),
                        ("device_list", json.dumps(device_list)),
                    ],
                ),
            )
            for target, watchdog, device_list in self._request_data_list
        ]

    def _process_response(self, response):
        report_item = response_to_report_item(response)
        if report_item:
            self._report(report_item)
            return
        report_list = []
        node_label = response.request.target.label
        try:
            data = json.loads(response.data)
            if not data["sbd"]["installed"]:
                report_list.append(
                    ReportItem.error(
                        reports.messages.SbdNotInstalled(node_label)
                    )
                )
            if "watchdog" in data:
                if data["watchdog"]["exist"]:
                    if not data["watchdog"].get("is_supported", True):
                        report_list.append(
                            ReportItem.error(
                                reports.messages.SbdWatchdogNotSupported(
                                    node_label, data["watchdog"]["path"]
                                )
                            )
                        )
                else:
                    report_list.append(
                        ReportItem.error(
                            reports.messages.WatchdogNotFound(
                                node_label, data["watchdog"]["path"]
                            )
                        )
                    )

            for device in data.get("device_list", []):
                if not device["exist"]:
                    report_list.append(
                        ReportItem.error(
                            reports.messages.SbdDeviceDoesNotExist(
                                device["path"], node_label
                            )
                        )
                    )
                elif not device["block_device"]:
                    report_list.append(
                        ReportItem.error(
                            reports.messages.SbdDeviceIsNotBlockDevice(
                                device["path"], node_label
                            )
                        )
                    )
                # TODO maybe we can check whenever device is initialized by sbd
                # (by running 'sbd -d <dev> dump;')
        except (ValueError, KeyError, TypeError):
            report_list.append(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(node_label)
                )
            )
        if report_list:
            self._report_list(report_list)
        else:
            self._report(
                ReportItem.info(
                    reports.messages.SbdCheckSuccess(
                        response.request.target.label
                    )
                )
            )

    def add_request(self, target, watchdog, device_list):
        self._request_data_list.append((target, watchdog, device_list))

    def before(self):
        self._report(ReportItem.info(reports.messages.SbdCheckStarted()))

from logging import Logger
from typing import (
    Any,
    Callable,
    Mapping,
    Optional,
    Union,
    cast,
)

from lxml.etree import _Element

from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.host import PcsKnownHost
from pcs.common.node_communicator import (
    Communicator,
    NodeCommunicatorFactory,
)
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.common.tools import Version
from pcs.common.types import StringIterable
from pcs.lib.booth.env import BoothEnv
from pcs.lib.communication import qdevice
from pcs.lib.communication.corosync import (
    CheckCorosyncOffline,
    DistributeCorosyncConf,
    ReloadCorosyncConf,
)
from pcs.lib.communication.tools import (
    run,
    run_and_raise,
)
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade
from pcs.lib.corosync.config_parser import (
    verify_section as verify_corosync_section,
)
from pcs.lib.corosync.live import get_local_corosync_conf
from pcs.lib.dr.env import DrEnv
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.file.instance import FileInstance
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.node_communication import (
    LibCommunicatorLogger,
    NodeTargetLibFactory,
)
from pcs.lib.pacemaker.live import (
    diff_cibs_xml,
    ensure_cib_version,
    get_cib,
    get_cib_xml,
    get_cluster_status_dom,
    push_cib_diff_xml,
    replace_cib_configuration,
    wait_for_idle,
)
from pcs.lib.pacemaker.values import get_valid_timeout_seconds
from pcs.lib.services import get_service_manager
from pcs.lib.tools import create_tmp_cib
from pcs.lib.xml_tools import etree_to_str

WaitType = Union[None, bool, int, str]


def _wait_type_to_int(wait: WaitType) -> int:
    """
    Convert WaitType to int.

    wait -- wait value. If False, it means wait is disabled, therefore -1
        is returned. If None, wait is enabled without timeout, therefore 0
        is returned. If string representing timeout or positive integer,
        wait is enabled with timeout, therefore number of seconds is
        retuned. Otherwise a LibraryError is raised.
    """
    if wait is False:
        return -1
    wait_timeout = get_valid_timeout_seconds(wait)
    if wait_timeout is None:
        return 0
    return wait_timeout


class LibraryEnvironment:
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    def __init__(
        self,
        logger: Logger,
        report_processor: reports.ReportProcessor,
        user_login: Optional[str] = None,
        user_groups: Optional[StringIterable] = None,
        cib_data: Optional[str] = None,
        corosync_conf_data: Optional[str] = None,
        booth_files_data: Optional[Mapping[str, Any]] = None,
        known_hosts_getter: Optional[
            Callable[[], Mapping[str, PcsKnownHost]]
        ] = None,
        request_timeout: Optional[int] = None,
    ):
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-positional-arguments
        self._logger = logger
        self._report_processor = report_processor
        self._user_login = user_login
        self._user_groups = [] if user_groups is None else list(user_groups)
        self._cib_data = cib_data
        self._corosync_conf_data = corosync_conf_data
        self._booth_files_data = booth_files_data or {}
        self._request_timeout = request_timeout
        # TODO tokens probably should not be inserted from outside, but we're
        # postponing dealing with them, because it's not that easy to move
        # related code currently - it's in pcsd
        self._known_hosts_getter = known_hosts_getter
        self._known_hosts: Optional[Mapping[str, PcsKnownHost]] = None
        self._cib_upgrade_reported: bool = False
        self._cib_data_tmp_file: Optional[Any] = None  # TODO proper type hint
        self.__loaded_cib_diff_source: Optional[str] = None
        self.__loaded_cib_to_modify: Optional[_Element] = None
        self._communicator_factory = NodeCommunicatorFactory(
            LibCommunicatorLogger(self.logger, self.report_processor),
            self.user_login,
            self.user_groups,
            self._request_timeout,
        )
        self.__loaded_booth_env: Optional[BoothEnv] = None
        self.__loaded_dr_env: Optional[DrEnv] = None
        self.__service_manager: Optional[ServiceManagerInterface] = None

    @property
    def logger(self) -> Logger:
        return self._logger

    @property
    def report_processor(self) -> ReportProcessor:
        return self._report_processor

    @property
    def user_login(self) -> Optional[str]:
        return self._user_login

    @property
    def user_groups(self) -> Optional[list[str]]:
        return self._user_groups

    @property
    def ghost_file_codes(self) -> list[file_type_codes.FileTypeCode]:
        codes = set()
        if not self.is_cib_live:
            codes.add(file_type_codes.CIB)
        if not self.is_corosync_conf_live:
            codes.add(file_type_codes.COROSYNC_CONF)
        return sorted(codes)

    def get_cib(
        self,
        minimal_version: Optional[Version] = None,
        nice_to_have_version: Optional[Version] = None,
    ) -> _Element:
        if self.__loaded_cib_diff_source is not None:
            raise AssertionError("CIB has already been loaded")

        self.__loaded_cib_diff_source = get_cib_xml(self.cmd_runner())
        self.__loaded_cib_to_modify = get_cib(self.__loaded_cib_diff_source)

        if (
            nice_to_have_version is not None
            and minimal_version is not None
            and minimal_version >= nice_to_have_version
        ):
            nice_to_have_version = None

        for version, mandatory in (
            (nice_to_have_version, False),
            (minimal_version, True),
        ):
            if version is not None:
                upgraded_cib, was_upgraded = ensure_cib_version(
                    self.cmd_runner(),
                    self.__loaded_cib_to_modify,
                    version,
                    fail_if_version_not_met=mandatory,
                )
                if was_upgraded:
                    self.__loaded_cib_to_modify = upgraded_cib
                    self.__loaded_cib_diff_source = etree_to_str(upgraded_cib)
                    if not self._cib_upgrade_reported:
                        self.report_processor.report(
                            ReportItem.info(
                                reports.messages.CibUpgradeSuccessful()
                            )
                        )
                    self._cib_upgrade_reported = True

        return self.__loaded_cib_to_modify

    @property
    def cib(self) -> _Element:
        if self.__loaded_cib_to_modify is None:
            raise AssertionError("CIB has not been loaded")
        return self.__loaded_cib_to_modify

    def get_cluster_state(self) -> _Element:
        return get_cluster_status_dom(self.cmd_runner())

    def wait_for_idle(self, timeout: int = 0) -> None:
        """
        Wait for the cluster to settle down.

        timeout -- timeout in seconds, if less than 0 wait will be skipped, if 0
            wait indefinitely
        """
        if timeout < 0:
            # timeout is turned off
            return
        self.report_processor.report(
            ReportItem.info(reports.messages.WaitForIdleStarted(timeout))
        )
        wait_for_idle(self.cmd_runner(), timeout)

    def ensure_wait_satisfiable(self, wait: WaitType) -> int:
        """
        Convert WaitType to int. Returns wait timeout in seconds.
        Raise when wait is not supported or when wait is not valid wait value.

        wait -- wait value. If False, it means wait is disabled, therefore -1
            is returned. If None, wait is enabled without timeout, therefore 0
            is returned. If string representing timeout or positive integer,
            wait is enabled with timeout, therefore number of seconds is
            returned. Otherwise a LibraryError is raised.
        """
        timeout = _wait_type_to_int(wait)
        self._ensure_wait_satisfiable(timeout)
        return timeout

    def _ensure_wait_satisfiable(self, wait_timeout: int) -> None:
        if wait_timeout >= 0 and not self.is_cib_live:
            raise LibraryError(
                ReportItem.error(reports.messages.WaitForIdleNotLiveCluster())
            )

    def push_cib(self, custom_cib=None, wait_timeout: int = -1) -> None:
        """
        Push previously loaded instance of CIB or a custom CIB

        etree custom_cib -- push a custom CIB instead of a loaded instance
            (allows to push an externally provided CIB and replace the one in
            the cluster completely)
        wait_timeout -- wait timeout in seconds, if less than 0 wait will be
            skipped, if 0 wait indefinitely
        """
        self._ensure_wait_satisfiable(wait_timeout)
        if custom_cib is not None:
            if self.__loaded_cib_diff_source is not None:
                raise AssertionError(
                    "CIB has been loaded, cannot push custom CIB"
                )
            return self.__push_cib_full(custom_cib, wait_timeout)
        if self.__loaded_cib_diff_source is None:
            raise AssertionError("CIB has not been loaded")
        return self.__push_cib_diff(wait_timeout)

    def __push_cib_full(self, cib_to_push, wait_timeout: int):
        self.__do_push_cib(
            lambda: replace_cib_configuration(self.cmd_runner(), cib_to_push),
            wait_timeout,
        )

    def __push_cib_diff(self, wait_timeout: int):
        self.__do_push_cib(
            lambda: self.__main_push_cib_diff(self.cmd_runner()), wait_timeout
        )

    def __main_push_cib_diff(self, cmd_runner):
        cib_diff_xml = diff_cibs_xml(
            cmd_runner,
            self.report_processor,
            self.__loaded_cib_diff_source,
            etree_to_str(self.__loaded_cib_to_modify),
        )
        if cib_diff_xml:
            push_cib_diff_xml(cmd_runner, cib_diff_xml)

    def __do_push_cib(self, push_strategy, wait_timeout: int) -> None:
        push_strategy()
        self._cib_upgrade_reported = False
        self.__loaded_cib_diff_source = None
        self.__loaded_cib_to_modify = None
        if self.is_cib_live:
            self.wait_for_idle(wait_timeout)

    @property
    def is_cib_live(self) -> bool:
        return self._cib_data is None

    @property
    def final_mocked_cib_content(self) -> str:
        if self._cib_data is None:
            raise AssertionError(
                "Final mocked cib content does not make sense in live env."
            )

        if self._cib_data_tmp_file:
            self._cib_data_tmp_file.seek(0)
            return self._cib_data_tmp_file.read()

        return self._cib_data

    def get_corosync_conf_data(self) -> str:
        if self._corosync_conf_data is None:
            return get_local_corosync_conf()
        return self._corosync_conf_data

    def get_corosync_conf(self) -> CorosyncConfigFacade:
        # TODO The architecture of working with corosync.conf needs to be
        # overhauled to match the new file framework. The code below is
        # complicated, because we read corosync.conf data at one place outside
        # of the file framework or get it from outside (from CLI) and then we
        # put them back into the framework.
        corosync_instance = FileInstance.for_corosync_conf()
        try:
            facade = cast(
                CorosyncConfigFacade,
                corosync_instance.raw_to_facade(
                    self.get_corosync_conf_data().encode("utf-8")
                ),
            )
        except ParserErrorException as e:
            if self.report_processor.report_list(
                corosync_instance.toolbox.parser.exception_to_report_list(
                    e,
                    corosync_instance.toolbox.file_type_code,
                    (
                        corosync_instance.raw_file.metadata.path
                        if self.is_corosync_conf_live
                        else None
                    ),
                    force_code=None,
                    is_forced_or_warning=False,
                )
            ).has_errors:
                raise LibraryError() from e
        return facade

    def push_corosync_conf(
        self,
        corosync_conf_facade: CorosyncConfigFacade,
        skip_offline_nodes: bool = False,
    ) -> None:
        bad_sections, bad_attr_names, bad_attr_values = verify_corosync_section(
            corosync_conf_facade.config
        )
        if bad_sections or bad_attr_names or bad_attr_values:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.CorosyncConfigCannotSaveInvalidNamesValues(
                        bad_sections,
                        bad_attr_names,
                        bad_attr_values,
                    )
                )
            )
        corosync_conf_data = corosync_conf_facade.config.export()
        if self.is_corosync_conf_live:
            node_name_list, report_list = get_existing_nodes_names(
                corosync_conf_facade,
                # Pcs is unable to communicate with nodes missing names. It
                # cannot send new corosync.conf to them. That might break the
                # cluster. Hence we error out.
                error_on_missing_name=True,
            )
            if self.report_processor.report_list(report_list).has_errors:
                raise LibraryError()

            self._push_corosync_conf_live(
                self.get_node_target_factory().get_target_list(
                    node_name_list,
                    skip_non_existing=skip_offline_nodes,
                ),
                corosync_conf_data,
                corosync_conf_facade.need_stopped_cluster,
                corosync_conf_facade.need_qdevice_reload,
                skip_offline_nodes,
            )
        else:
            self._corosync_conf_data = corosync_conf_data

    def _push_corosync_conf_live(
        self,
        target_list,
        corosync_conf_data,
        need_stopped_cluster,
        need_qdevice_reload,
        skip_offline_nodes,
    ):
        # TODO
        # * check for online nodes and run all commands on them only
        # * if those commands fail, exit with an error
        # * add support for allow_skip_offline=False
        # * use simple report processor
        # Correct reloading is done in pcs.lib.cluster.remove_nodes for example.

        # Check if the cluster is stopped when needed
        if need_stopped_cluster:
            com_cmd = CheckCorosyncOffline(
                self.report_processor, skip_offline_nodes
            )
            com_cmd.set_targets(target_list)
            cluster_running_target_list = run(
                self.get_node_communicator(), com_cmd
            )
            if cluster_running_target_list:
                self.report_processor.report(
                    ReportItem.error(
                        reports.messages.CorosyncNotRunningCheckFinishedRunning(
                            [
                                target.label
                                for target in cluster_running_target_list
                            ],
                        ),
                    )
                )
            if self.report_processor.has_errors:
                raise LibraryError()
        # Distribute corosync.conf
        com_cmd = DistributeCorosyncConf(
            self.report_processor, corosync_conf_data, skip_offline_nodes
        )
        com_cmd.set_targets(target_list)
        run_and_raise(self.get_node_communicator(), com_cmd)
        # Reload corosync
        if not need_stopped_cluster:
            # If cluster must be stopped then we cannot reload corosync because
            # the cluster is stopped. If it is not stopped, we do not even get
            # here.
            com_cmd = ReloadCorosyncConf(self.report_processor)
            com_cmd.set_targets(target_list)
            run_and_raise(self.get_node_communicator(), com_cmd)
        # Reload qdevice if needed
        if need_qdevice_reload:
            self.report_processor.report(
                ReportItem.info(reports.messages.QdeviceClientReloadStarted())
            )
            com_cmd = qdevice.Stop(self.report_processor, skip_offline_nodes)
            com_cmd.set_targets(target_list)
            run(self.get_node_communicator(), com_cmd)
            has_errors = com_cmd.has_errors
            com_cmd = qdevice.Start(self.report_processor, skip_offline_nodes)
            com_cmd.set_targets(target_list)
            run(self.get_node_communicator(), com_cmd)
            has_errors = has_errors or com_cmd.has_errors
            if has_errors:
                raise LibraryError()

    @property
    def is_corosync_conf_live(self) -> bool:
        return self._corosync_conf_data is None

    def cmd_runner(
        self, env: Optional[Mapping[str, str]] = None
    ) -> CommandRunner:
        runner_env = {
            # make sure to get output of external processes in English and ASCII
            "LC_ALL": "C",
        }

        if self.user_login:
            runner_env["CIB_user"] = self.user_login

        if self._cib_data is not None:
            # Dump CIB data to a temporary file and set it up in the runner.
            # This way every called pacemaker tool can access the CIB and we
            # don't need to take care of it every time the runner is called.
            if not self._cib_data_tmp_file:
                self._cib_data_tmp_file = create_tmp_cib(
                    self.report_processor, self._cib_data
                )
            runner_env["CIB_file"] = self._cib_data_tmp_file.name

        if env:
            runner_env.update(env)

        return CommandRunner(self.logger, self.report_processor, runner_env)

    @property
    def communicator_factory(self) -> NodeCommunicatorFactory:
        return self._communicator_factory

    def get_node_communicator(
        self,
        request_timeout: Optional[int] = None,
    ) -> Communicator:
        return self.communicator_factory.get_communicator(
            request_timeout=request_timeout
        )

    def get_node_target_factory(self) -> NodeTargetLibFactory:
        return NodeTargetLibFactory(
            self.__get_known_hosts(), self.report_processor
        )

    def get_known_hosts(
        self, host_name_list: StringIterable
    ) -> list[PcsKnownHost]:
        known_hosts = self.__get_known_hosts()
        return [
            known_hosts[host_name]
            for host_name in host_name_list
            if host_name in known_hosts
        ]

    def __get_known_hosts(self) -> Mapping[str, PcsKnownHost]:
        if self._known_hosts is None:
            if self._known_hosts_getter:
                self._known_hosts = self._known_hosts_getter()
            else:
                self._known_hosts = {}
        return self._known_hosts

    def get_booth_env(self, name: Optional[str]) -> BoothEnv:
        if self.__loaded_booth_env is None:
            self.__loaded_booth_env = BoothEnv(name, self._booth_files_data)
        return self.__loaded_booth_env

    def get_dr_env(self) -> DrEnv:
        if self.__loaded_dr_env is None:
            self.__loaded_dr_env = DrEnv()
        return self.__loaded_dr_env

    def _get_service_manager(self) -> ServiceManagerInterface:
        if self.__service_manager is None:
            self.__service_manager = get_service_manager(
                self.cmd_runner(), self.report_processor
            )
        return self.__service_manager

    @property
    def service_manager(self) -> ServiceManagerInterface:
        return self._get_service_manager()

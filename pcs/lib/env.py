from typing import (
    Optional,
    cast,
)

from lxml.etree import _Element

from pcs.common import file_type_codes
from pcs.common import reports
from pcs.common.node_communicator import Communicator, NodeCommunicatorFactory
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.common.tools import Version
from pcs.lib.booth.env import BoothEnv
from pcs.lib.cib.tools import get_cib_crm_feature_set
from pcs.lib.dr.env import DrEnv
from pcs.lib.node import get_existing_nodes_names
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
from pcs.lib.external import CommandRunner
from pcs.lib.errors import LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node_communication import (
    LibCommunicatorLogger,
    NodeTargetLibFactory,
)
from pcs.lib.pacemaker.live import (
    diff_cibs_xml,
    ensure_cib_version,
    get_cib,
    get_cib_xml,
    get_cluster_status_xml,
    push_cib_diff_xml,
    replace_cib_configuration,
    wait_for_idle,
)
from pcs.lib.pacemaker.state import get_cluster_state_dom
from pcs.lib.pacemaker.values import get_valid_timeout_seconds
from pcs.lib.tools import write_tmpfile
from pcs.lib.xml_tools import etree_to_str

MIN_FEATURE_SET_VERSION_FOR_DIFF = Version(3, 0, 9)


class LibraryEnvironment:
    # pylint: disable=too-many-instance-attributes, too-many-public-methods

    def __init__(
        self,
        logger,
        report_processor,
        user_login=None,
        user_groups=None,
        cib_data=None,
        corosync_conf_data=None,
        booth_files_data=None,
        known_hosts_getter=None,
        request_timeout=None,
    ):
        # pylint: disable=too-many-arguments
        self._logger = logger
        self._report_processor = report_processor
        self._user_login = user_login
        self._user_groups = [] if user_groups is None else user_groups
        self._cib_data = cib_data
        self._corosync_conf_data = corosync_conf_data
        self._booth_files_data = booth_files_data or {}
        self._request_timeout = request_timeout
        # TODO tokens probably should not be inserted from outside, but we're
        # postponing dealing with them, because it's not that easy to move
        # related code currently - it's in pcsd
        self._known_hosts_getter = known_hosts_getter
        self._known_hosts = None
        self._cib_upgrade_reported = False
        self._cib_data_tmp_file = None
        self.__loaded_cib_diff_source = None
        self.__loaded_cib_diff_source_feature_set = None
        self.__loaded_cib_to_modify = None
        self._communicator_factory = NodeCommunicatorFactory(
            LibCommunicatorLogger(self.logger, self.report_processor),
            self.user_login,
            self.user_groups,
            self._request_timeout,
        )
        self.__loaded_booth_env = None
        self.__loaded_dr_env = None

        self.__timeout_cache = {}

    @property
    def logger(self):
        return self._logger

    @property
    def report_processor(self) -> ReportProcessor:
        return self._report_processor

    @property
    def user_login(self):
        return self._user_login

    @property
    def user_groups(self):
        return self._user_groups

    @property
    def ghost_file_codes(self):
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

        self.__loaded_cib_diff_source_feature_set = get_cib_crm_feature_set(
            self.__loaded_cib_to_modify, none_if_missing=True
        ) or Version(0, 0, 0)
        return self.__loaded_cib_to_modify

    @property
    def cib(self):
        if self.__loaded_cib_diff_source is None:
            raise AssertionError("CIB has not been loaded")
        return self.__loaded_cib_to_modify

    def get_cluster_state(self):
        return get_cluster_state_dom(get_cluster_status_xml(self.cmd_runner()))

    def get_wait_timeout(self, wait):
        if wait is False:
            return False

        if wait not in self.__timeout_cache:
            if not self.is_cib_live:
                raise LibraryError(
                    ReportItem.error(
                        reports.messages.WaitForIdleNotLiveCluster()
                    )
                )
            self.__timeout_cache[wait] = get_valid_timeout_seconds(wait)
        return self.__timeout_cache[wait]

    def ensure_wait_satisfiable(self, wait):
        """
        Raise when wait is not supported or when wait is not valid wait value.

        mixed wait can be False when waiting is not required or valid timeout
        """
        self.get_wait_timeout(wait)

    def push_cib(self, custom_cib=None, wait=False):
        """
        Push previously loaded instance of CIB or a custom CIB

        etree custom_cib -- push a custom CIB instead of a loaded instance
            (allows to push an externally provided CIB and replace the one in
            the cluster completely)
        mixed wait -- how many seconds to wait for pacemaker to process new CIB
            or False for not waiting at all
        """
        if custom_cib is not None:
            if self.__loaded_cib_diff_source is not None:
                raise AssertionError(
                    "CIB has been loaded, cannot push custom CIB"
                )
            return self.__push_cib_full(custom_cib, wait)
        if self.__loaded_cib_diff_source is None:
            raise AssertionError("CIB has not been loaded")
        # Push by diff works with crm_feature_set > 3.0.8, see
        # https://bugzilla.redhat.com/show_bug.cgi?id=1488044 for details. We
        # only check the version if a CIB has been loaded, otherwise the push
        # fails anyway. By my testing it seems that only the source CIB's
        # version matters.
        if (
            self.__loaded_cib_diff_source_feature_set
            < MIN_FEATURE_SET_VERSION_FOR_DIFF
        ):
            current_set = str(
                self.__loaded_cib_diff_source_feature_set.normalize()
            )
            self.report_processor.report(
                ReportItem.warning(
                    reports.messages.CibPushForcedFullDueToCrmFeatureSet(
                        str(MIN_FEATURE_SET_VERSION_FOR_DIFF.normalize()),
                        current_set,
                    )
                )
            )
            return self.__push_cib_full(self.__loaded_cib_to_modify, wait=wait)
        return self.__push_cib_diff(wait=wait)

    def __push_cib_full(self, cib_to_push, wait=False):
        cmd_runner = self.cmd_runner()
        self.__do_push_cib(
            cmd_runner,
            lambda: replace_cib_configuration(cmd_runner, cib_to_push),
            wait,
        )

    def __push_cib_diff(self, wait=False):
        cmd_runner = self.cmd_runner()
        self.__do_push_cib(
            cmd_runner, lambda: self.__main_push_cib_diff(cmd_runner), wait
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

    def __do_push_cib(self, cmd_runner, push_strategy, wait):
        timeout = self.get_wait_timeout(wait)
        push_strategy()
        self._cib_upgrade_reported = False
        self.__loaded_cib_diff_source = None
        self.__loaded_cib_diff_source_feature_set = None
        self.__loaded_cib_to_modify = None
        if self.is_cib_live and timeout is not False:
            wait_for_idle(cmd_runner, timeout)

    @property
    def is_cib_live(self):
        return self._cib_data is None

    @property
    def final_mocked_cib_content(self):
        if self.is_cib_live:
            raise AssertionError(
                "Final mocked cib content does not make sense in live env."
            )

        if self._cib_data_tmp_file:
            self._cib_data_tmp_file.seek(0)
            return self._cib_data_tmp_file.read()

        return self._cib_data

    def get_corosync_conf_data(self):
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
        self, corosync_conf_facade, skip_offline_nodes=False
    ):
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
        # * use simple report procesor
        # Correct reloading is done in pcs.lib.cluster.remove_nodes for example.

        # Check if the cluster is stopped when needed
        if need_stopped_cluster:
            com_cmd = CheckCorosyncOffline(
                self.report_processor, skip_offline_nodes
            )
            com_cmd.set_targets(target_list)
            run_and_raise(self.get_node_communicator(), com_cmd)
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
    def is_corosync_conf_live(self):
        return self._corosync_conf_data is None

    def cmd_runner(self) -> CommandRunner:
        runner_env = {
            # make sure to get output of external processes in English and ASCII
            "LC_ALL": "C",
        }

        if self.user_login:
            runner_env["CIB_user"] = self.user_login

        if not self.is_cib_live:
            # Dump CIB data to a temporary file and set it up in the runner.
            # This way every called pacemaker tool can access the CIB and we
            # don't need to take care of it every time the runner is called.
            if not self._cib_data_tmp_file:
                try:
                    cib_data = self._cib_data
                    self._cib_data_tmp_file = write_tmpfile(cib_data)
                    self.report_processor.report(
                        ReportItem.debug(
                            reports.messages.TmpFileWrite(
                                self._cib_data_tmp_file.name, cib_data
                            )
                        )
                    )
                except EnvironmentError as e:
                    raise LibraryError(
                        ReportItem.error(
                            reports.messages.CibSaveTmpError(str(e))
                        )
                    ) from e
            runner_env["CIB_file"] = self._cib_data_tmp_file.name

        return CommandRunner(self.logger, self.report_processor, runner_env)

    @property
    def communicator_factory(self):
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

    def get_known_hosts(self, host_name_list):
        known_hosts = self.__get_known_hosts()
        return [
            known_hosts[host_name]
            for host_name in host_name_list
            if host_name in known_hosts
        ]

    def __get_known_hosts(self):
        if self._known_hosts is None:
            if self._known_hosts_getter:
                self._known_hosts = self._known_hosts_getter()
            else:
                self._known_hosts = {}
        return self._known_hosts

    def get_booth_env(self, name):
        if self.__loaded_booth_env is None:
            self.__loaded_booth_env = BoothEnv(name, self._booth_files_data)
        return self.__loaded_booth_env

    def get_dr_env(self) -> DrEnv:
        if self.__loaded_dr_env is None:
            self.__loaded_dr_env = DrEnv()
        return self.__loaded_dr_env

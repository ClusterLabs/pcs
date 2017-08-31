from __future__ import (
    absolute_import,
    division,
    print_function,
)

import os.path

from pcs import settings
from pcs.common.node_communicator import (
    NodeCommunicatorFactory,
    NodeTargetFactory
)
from pcs.lib import reports
from pcs.lib.booth.env import BoothEnv
from pcs.lib.pacemaker.env import PacemakerEnv
from pcs.lib.cluster_conf_facade import ClusterConfFacade
from pcs.lib.communication import qdevice
from pcs.lib.communication.corosync import (
    CheckCorosyncOffline,
    DistributeCorosyncConf,
)
from pcs.lib.communication.tools import (
    run,
    run_and_raise,
)
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade
from pcs.lib.corosync.live import (
    exists_local_corosync_conf,
    get_local_corosync_conf,
    get_local_cluster_conf,
    reload_config as reload_corosync_config,
)
from pcs.lib.external import (
    is_cman_cluster,
    is_service_running,
    CommandRunner,
    NodeCommunicator,
)
from pcs.lib.errors import LibraryError
from pcs.lib.node_communication import LibCommunicatorLogger
from pcs.lib.pacemaker.live import (
    diff_cibs_xml,
    ensure_cib_version,
    ensure_wait_for_idle_support,
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

class LibraryEnvironment(object):
    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        logger,
        report_processor,
        user_login=None,
        user_groups=None,
        cib_data=None,
        corosync_conf_data=None,
        booth=None,
        pacemaker=None,
        token_file_data_getter=None,
        cluster_conf_data=None,
        request_timeout=None,
    ):
        self._logger = logger
        self._report_processor = report_processor
        self._user_login = user_login
        self._user_groups = [] if user_groups is None else user_groups
        self._cib_data = cib_data
        self._corosync_conf_data = corosync_conf_data
        self._cluster_conf_data = cluster_conf_data
        self._booth = (
            BoothEnv(report_processor, booth) if booth is not None else None
        )
        #pacemaker is currently not mocked and it provides only an access to
        #the authkey
        self._pacemaker =  PacemakerEnv()
        self._request_timeout = request_timeout
        self._is_cman_cluster = None
        # TODO tokens probably should not be inserted from outside, but we're
        # postponing dealing with them, because it's not that easy to move
        # related code currently - it's in pcsd
        self._token_file_data_getter = token_file_data_getter
        self._token_file = None
        self._cib_upgraded = False
        self._cib_data_tmp_file = None
        self.__loaded_cib_diff_source = None
        self.__loaded_cib_to_modify = None
        self._communicator_factory = NodeCommunicatorFactory(
            LibCommunicatorLogger(self.logger, self.report_processor),
            self.user_login,
            self.user_groups,
            self._request_timeout
        )

        self.__timeout_cache = {}

    @property
    def logger(self):
        return self._logger

    @property
    def report_processor(self):
        return self._report_processor

    @property
    def user_login(self):
        return self._user_login

    @property
    def user_groups(self):
        return self._user_groups

    @property
    def is_cman_cluster(self):
        if self._is_cman_cluster is None:
            self._is_cman_cluster = is_cman_cluster(self.cmd_runner())
        return self._is_cman_cluster

    @property
    def cib_upgraded(self):
        return self._cib_upgraded

    def get_cib(self, minimal_version=None):
        if self.__loaded_cib_diff_source is not None:
            raise AssertionError("CIB has already been loaded")
        self.__loaded_cib_diff_source = get_cib_xml(self.cmd_runner())
        self.__loaded_cib_to_modify = get_cib(self.__loaded_cib_diff_source)
        if minimal_version is not None:
            upgraded_cib = ensure_cib_version(
                self.cmd_runner(),
                self.__loaded_cib_to_modify,
                minimal_version
            )
            if upgraded_cib is not None:
                self.__loaded_cib_to_modify = upgraded_cib
                self.__loaded_cib_diff_source = etree_to_str(upgraded_cib)
                if self.is_cib_live and not self._cib_upgraded:
                    self.report_processor.process(
                        reports.cib_upgrade_successful()
                    )
                self._cib_upgraded = True
        return self.__loaded_cib_to_modify

    @property
    def cib(self):
        if self.__loaded_cib_diff_source is None:
            raise AssertionError("CIB has not been loaded")
        return self.__loaded_cib_to_modify

    def get_cluster_state(self):
        return get_cluster_state_dom(get_cluster_status_xml(self.cmd_runner()))

    def _get_wait_timeout(self, wait):
        if wait is False:
            return False

        if wait not in self.__timeout_cache:
            if not self.is_cib_live:
                raise LibraryError(reports.wait_for_idle_not_live_cluster())
            ensure_wait_for_idle_support(self.cmd_runner())
            self.__timeout_cache[wait] = get_valid_timeout_seconds(wait)
        return self.__timeout_cache[wait]


    def ensure_wait_satisfiable(self, wait):
        """
        Raise when wait is not supported or when wait is not valid wait value.

        mixed wait can be False when waiting is not required or valid timeout
        """
        self._get_wait_timeout(wait)

    def push_cib(self, custom_cib=None, wait=False):
        if custom_cib is not None:
            return self.push_cib_full(custom_cib, wait)
        return self.push_cib_diff(wait)

    def push_cib_full(self, custom_cib=None, wait=False):
        if custom_cib is None and self.__loaded_cib_diff_source is None:
            raise AssertionError("CIB has not been loaded")
        if custom_cib is not None and self.__loaded_cib_diff_source is not None:
            raise AssertionError("CIB has been loaded, cannot push custom CIB")

        cmd_runner = self.cmd_runner()
        cib_to_push = (
            self.__loaded_cib_to_modify if custom_cib is None else custom_cib
        )
        self.__do_push_cib(
            cmd_runner,
            lambda: replace_cib_configuration(cmd_runner, cib_to_push),
            cib_to_push,
            wait
        )

    def push_cib_diff(self, wait=False):
        if self.__loaded_cib_diff_source is None:
            raise AssertionError("CIB has not been loaded")

        cmd_runner = self.cmd_runner()
        self.__do_push_cib(
            cmd_runner,
            lambda: self.__main_push_cib_diff(cmd_runner),
            self.__loaded_cib_to_modify,
            wait
        )

    def __main_push_cib_diff(self, cmd_runner):
        cib_diff_xml = diff_cibs_xml(
            cmd_runner,
            self.report_processor,
            self.__loaded_cib_diff_source,
            etree_to_str(self.__loaded_cib_to_modify)
        )

        if cib_diff_xml:
            push_cib_diff_xml(cmd_runner, cib_diff_xml)

    def __do_push_cib(self, cmd_runner, live_push_strategy, not_live_cib, wait):
        timeout = self._get_wait_timeout(wait)
        if self.is_cib_live:
            live_push_strategy()
            self._cib_upgraded = False
        else:
            self._cib_data = etree_to_str(not_live_cib)
        self.__loaded_cib_diff_source = None
        self.__loaded_cib_to_modify = None
        if self.is_cib_live and timeout is not False:
            wait_for_idle(cmd_runner, timeout)

    @property
    def is_cib_live(self):
        return self._cib_data is None

    def get_corosync_conf_data(self):
        if self._corosync_conf_data is None:
            return get_local_corosync_conf()
        return self._corosync_conf_data

    def get_corosync_conf(self):
        return CorosyncConfigFacade.from_string(self.get_corosync_conf_data())

    def push_corosync_conf(
        self, corosync_conf_facade, skip_offline_nodes=False
    ):
        corosync_conf_data = corosync_conf_facade.config.export()
        if self.is_corosync_conf_live:
            self._push_corosync_conf_live(
                self.get_node_target_factory().get_target_list(
                    corosync_conf_facade.get_nodes()
                ),
                corosync_conf_data,
                corosync_conf_facade.need_stopped_cluster,
                corosync_conf_facade.need_qdevice_reload,
                skip_offline_nodes,
            )
        else:
            self._corosync_conf_data = corosync_conf_data

    def _push_corosync_conf_live(
        self, target_list, corosync_conf_data, need_stopped_cluster,
        need_qdevice_reload, skip_offline_nodes
    ):
        if need_stopped_cluster:
            com_cmd = CheckCorosyncOffline(
                self.report_processor, skip_offline_nodes
            )
            com_cmd.set_targets(target_list)
            run_and_raise(self.get_node_communicator(), com_cmd)
        com_cmd = DistributeCorosyncConf(
            self.report_processor, corosync_conf_data, skip_offline_nodes
        )
        com_cmd.set_targets(target_list)
        run_and_raise(self.get_node_communicator(), com_cmd)
        if is_service_running(self.cmd_runner(), "corosync"):
            reload_corosync_config(self.cmd_runner())
            self.report_processor.process(
                reports.corosync_config_reloaded()
            )
        if need_qdevice_reload:
            self.report_processor.process(
                reports.qdevice_client_reload_started()
            )
            com_cmd = qdevice.Stop(self.report_processor, skip_offline_nodes)
            com_cmd.set_targets(target_list)
            run(self.get_node_communicator(), com_cmd)
            report_list = com_cmd.error_list
            com_cmd = qdevice.Start(self.report_processor, skip_offline_nodes)
            com_cmd.set_targets(target_list)
            run(self.get_node_communicator(), com_cmd)
            report_list += com_cmd.error_list
            if report_list:
                raise LibraryError()

    def get_cluster_conf_data(self):
        if self.is_cluster_conf_live:
            return get_local_cluster_conf()
        return self._cluster_conf_data


    def get_cluster_conf(self):
        return ClusterConfFacade.from_string(self.get_cluster_conf_data())


    @property
    def is_cluster_conf_live(self):
        return self._cluster_conf_data is None


    def is_node_in_cluster(self):
        if self.is_cman_cluster:
            #TODO --cluster_conf is not propagated here. So no live check not
            #needed here. But this should not be permanently
            return os.path.exists(settings.corosync_conf_file)

        if not self.is_corosync_conf_live:
            raise AssertionError(
                "Cannot check if node is in cluster with mocked corosync_conf."
            )
        return exists_local_corosync_conf()

    def command_expect_live_corosync_env(self):
        if not self.is_corosync_conf_live:
            raise LibraryError(
                reports.live_environment_required(["COROSYNC_CONF"])
            )

    @property
    def is_corosync_conf_live(self):
        return self._corosync_conf_data is None

    def cmd_runner(self):
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
                    self.report_processor.process(
                        reports.tmp_file_write(
                            self._cib_data_tmp_file.name,
                            cib_data
                        )
                    )
                except EnvironmentError as e:
                    raise LibraryError(reports.cib_save_tmp_error(str(e)))
            runner_env["CIB_file"] = self._cib_data_tmp_file.name

        return CommandRunner(self.logger, self.report_processor, runner_env)

    @property
    def communicator_factory(self):
        return self._communicator_factory

    def get_node_communicator(self):
        return self.communicator_factory.get_communicator()

    def get_node_target_factory(self):
        token_file = self.__get_token_file()
        return NodeTargetFactory(token_file["tokens"], token_file["ports"])

    # deprecated, use communicator_factory or get_node_communicator()
    def node_communicator(self):
        return NodeCommunicator(
            self.logger,
            self.report_processor,
            self.__get_auth_tokens(),
            self.user_login,
            self.user_groups,
            self._request_timeout
        )

    def __get_token_file(self):
        if self._token_file is None:
            if self._token_file_data_getter:
                self._token_file = self._token_file_data_getter()
            else:
                self._token_file = {
                    "tokens": {},
                    "ports": {},
                }
        return self._token_file

    @property
    def booth(self):
        return self._booth

    @property
    def pacemaker(self):
        return self._pacemaker

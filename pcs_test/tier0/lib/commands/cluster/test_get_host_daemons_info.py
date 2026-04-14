import os.path
from dataclasses import replace
from unittest import TestCase, mock

from pcs import settings
from pcs.common import file_type_codes
from pcs.common.cluster_dto import (
    ClusterComponentVersionDto,
    ClusterDaemonsInfoDto,
)
from pcs.common.services_dto import ServiceStatusDto
from pcs.common.version_dto import VersionDto
from pcs.lib.commands import cluster

from pcs_test.tools.command_env import get_env_tools

FIXTURE_PCSD_VERSION = "0.12.2"

FIXTURE_CHECK_HOST_RESULT_DTO = ClusterDaemonsInfoDto(
    cluster_configuration_exists=True,
    services=[
        ServiceStatusDto(
            service="booth",
            installed=False,
            enabled=False,
            running=False,
        ),
        ServiceStatusDto(
            service="corosync",
            installed=True,
            enabled=False,
            running=True,
        ),
        ServiceStatusDto(
            service="corosync-qdevice",
            installed=False,
            enabled=False,
            running=False,
        ),
        ServiceStatusDto(
            service="pacemaker",
            installed=True,
            enabled=False,
            running=True,
        ),
        ServiceStatusDto(
            service="pacemaker_remote",
            installed=False,
            enabled=False,
            running=False,
        ),
        ServiceStatusDto(
            service="pcsd",
            installed=True,
            enabled=True,
            running=True,
        ),
        ServiceStatusDto(
            service="sbd",
            installed=False,
            enabled=False,
            running=False,
        ),
    ],
    versions=ClusterComponentVersionDto(
        corosync=VersionDto(2, 4, 0),
        pacemaker=VersionDto(3, 0, 1),
        pcsd=VersionDto(0, 12, 2),
    ),
)


class GetHostDaemonsInfo(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def command(self):
        return cluster.get_host_daemons_info(self.env_assist.get_env())

    def _configure_all_services(self, **service_states):
        all_services = [
            "booth",
            "corosync",
            "corosync-qdevice",
            "pacemaker",
            "pacemaker_remote",
            "pcsd",
            "sbd",
        ]

        for service in all_services:
            installed, enabled, running = service_states.get(
                service, (False, False, False)
            )
            self.config.services.is_installed(
                service,
                return_value=installed,
                name=f"services.is_installed.{service}",
            )
            self.config.services.is_enabled(
                service,
                return_value=enabled,
                name=f"services.is_enabled.{service}",
            )
            self.config.services.is_running(
                service,
                return_value=running,
                name=f"services.is_running.{service}",
            )

    def _configure_services_from_fixture(self):
        self._configure_all_services(
            corosync=(True, False, True),
            pacemaker=(True, False, True),
            pcsd=(True, True, True),
        )

    def _configure_cluster_configs(self, corosync_conf=True, cib=True):
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=corosync_conf,
            name="raw_file.exists.corosync_conf",
        )
        if not corosync_conf:
            self.config.fs.exists(
                os.path.join(settings.cib_dir, "cib.xml"),
                return_value=cib,
                name="fs.exists.cib_xml",
            )

    def _test_cluster_configuration(self, corosync_conf=True, cib=True):
        self._configure_cluster_configs(corosync_conf=corosync_conf, cib=cib)
        self._configure_services_from_fixture()
        self.config.runner.corosync.version()
        self.config.runner.pcmk.version()
        self.assertEqual(
            self.command(),
            replace(
                FIXTURE_CHECK_HOST_RESULT_DTO,
                cluster_configuration_exists=corosync_conf or cib,
            ),
        )

    @mock.patch(
        "pcs.lib.commands.cluster.node.settings.pcs_version",
        FIXTURE_PCSD_VERSION,
    )
    def test_cluster_configured_corosync_conf(self):
        self._test_cluster_configuration()

    @mock.patch(
        "pcs.lib.commands.cluster.node.settings.pcs_version",
        FIXTURE_PCSD_VERSION,
    )
    def test_cluster_configured_cib_only(self):
        self._test_cluster_configuration(corosync_conf=False)

    @mock.patch(
        "pcs.lib.commands.cluster.node.settings.pcs_version",
        FIXTURE_PCSD_VERSION,
    )
    def test_cluster_not_configured(self):
        self._test_cluster_configuration(corosync_conf=False, cib=False)

    @mock.patch(
        "pcs.lib.commands.cluster.node.settings.pcs_version",
        FIXTURE_PCSD_VERSION,
    )
    def test_versions_unavailable(self):
        self._configure_cluster_configs()
        self._configure_services_from_fixture()
        self.config.runner.corosync.version(returncode=1)
        self.config.runner.pcmk.version(returncode=1)

        self.assertEqual(
            self.command(),
            replace(
                FIXTURE_CHECK_HOST_RESULT_DTO,
                versions=ClusterComponentVersionDto(
                    corosync=VersionDto(0, 0, 0),
                    pacemaker=VersionDto(0, 0, 0),
                    pcsd=VersionDto(0, 12, 2),
                ),
            ),
        )

    @mock.patch("pcs.lib.commands.cluster.node.settings.pcs_version", "")
    def test_unable_to_parse_versions(self):
        self._configure_cluster_configs()
        self._configure_services_from_fixture()
        self.config.runner.corosync.version(version="bad_format")
        self.config.runner.pcmk.version(version="bad_format")

        self.assertEqual(
            self.command(),
            replace(
                FIXTURE_CHECK_HOST_RESULT_DTO,
                versions=ClusterComponentVersionDto(
                    corosync=VersionDto(0, 0, 0),
                    pacemaker=VersionDto(0, 0, 0),
                    pcsd=VersionDto(0, 0, 0),
                ),
            ),
        )

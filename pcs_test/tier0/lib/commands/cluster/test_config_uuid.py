from unittest import (
    TestCase,
    mock,
)

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from .common import (
    CLUSTER_UUID,
    fixture_totem,
)


@mock.patch("pcs.lib.commands.cluster.generate_uuid", lambda: CLUSTER_UUID)
class GenerateUuid(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_uuid_not_present(self):
        self.config.corosync_conf.load_content(fixture_totem(cluster_uuid=None))
        self.config.env.push_corosync_conf(corosync_conf_text=fixture_totem())
        cluster.generate_cluster_uuid(self.env_assist.get_env())
        self.env_assist.assert_reports([])

    def test_uuid_present(self):
        self.config.corosync_conf.load_content(fixture_totem())
        self.env_assist.assert_raise_library_error(
            lambda: cluster.generate_cluster_uuid(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CLUSTER_UUID_ALREADY_SET,
                    force_code=report_codes.FORCE,
                )
            ]
        )

    def test_uuid_present_with_force(self):
        self.config.corosync_conf.load_content(
            fixture_totem(cluster_uuid="uuid")
        )
        self.config.env.push_corosync_conf(corosync_conf_text=fixture_totem())
        cluster.generate_cluster_uuid(
            self.env_assist.get_env(), force_flags=report_codes.FORCE
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.CLUSTER_UUID_ALREADY_SET,
                )
            ]
        )


@mock.patch("pcs.lib.commands.cluster.generate_uuid", lambda: CLUSTER_UUID)
class GenerateUuidLocal(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_uuid_not_present(self):
        self.assertEqual(
            cluster.generate_cluster_uuid_local(
                self.env_assist.get_env(),
                fixture_totem(cluster_uuid=None).encode(),
            ),
            fixture_totem().encode(),
        )

    def test_uuid_present(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.generate_cluster_uuid_local(
                self.env_assist.get_env(),
                fixture_totem().encode(),
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CLUSTER_UUID_ALREADY_SET,
                    force_code=report_codes.FORCE,
                )
            ]
        )

    def test_uuid_present_with_force(self):
        self.assertEqual(
            cluster.generate_cluster_uuid_local(
                self.env_assist.get_env(),
                fixture_totem(cluster_uuid="uuid").encode(),
                force_flags=report_codes.FORCE,
            ),
            fixture_totem().encode(),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.CLUSTER_UUID_ALREADY_SET,
                )
            ]
        )

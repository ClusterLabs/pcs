# pylint: disable=too-many-lines
import os
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import RawFileError
from pcs.lib.booth import constants
from pcs.lib.commands import booth as commands

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import XmlManipulation

RANDOM_KEY = "I'm so random!".encode()
REASON = "This is a reason"


def fixture_report_invalid_name(name):
    return fixture.error(
        reports.codes.BOOTH_INVALID_NAME,
        name=name,
        forbidden_characters="/",
    )


class FixtureMixin:
    booth_dir = settings.booth_config_dir
    site_ip = "192.168.122.254"

    def fixture_cfg_path(self, name="booth"):
        return os.path.join(self.booth_dir, f"{name}.conf")

    def fixture_key_path(self, name="booth"):
        return os.path.join(self.booth_dir, f"{name}.key")

    def fixture_cib_resources(self, name="booth"):
        return (
            "<resources>"
            + self.fixture_cib_booth_primitive(name=name)
            + "</resources>"
        )

    def fixture_cib_more_resources(self):
        return (
            "<resources>"
            + self.fixture_cib_booth_primitive("booth", "booth1")
            + self.fixture_cib_booth_primitive("booth", "booth2")
            + "</resources>"
        )

    def fixture_cib_booth_primitive(self, name="booth", rid="booth_resource"):
        return f"""
            <primitive id="{rid}" type="booth-site">
                <instance_attributes>
                    <nvpair
                        name="config"
                        value="{self.fixture_cfg_path(name)}"
                    />
                </instance_attributes>
            </primitive>
        """

    def fixture_cib_booth_group(
        self, name="booth", default_operations=False, wrap_in_resources=True
    ):
        return (
            ("<resources>" if wrap_in_resources else "")
            + f"""<group id="booth-{name}-group">
                <primitive class="ocf" provider="heartbeat" type="IPaddr2"
                    id="booth-{name}-ip"
                >
                    <instance_attributes
                        id="booth-{name}-ip-instance_attributes"
                    >
                        <nvpair id="booth-{name}-ip-instance_attributes-ip"
                            name="ip" value="{self.site_ip}"
                        />
                    </instance_attributes>
                    <operations>
            """
            + (
                f"""
                        <op id="booth-{name}-ip-monitor-interval-60s"
                            interval="60s" name="monitor"
                        />
            """
                if default_operations
                else f"""
                        <op id="booth-{name}-ip-monitor-interval-10s"
                            interval="10s" name="monitor" timeout="20s"
                        />
                        <op id="booth-{name}-ip-start-interval-0s"
                            interval="0s" name="start" timeout="20s"
                        />
                        <op id="booth-{name}-ip-stop-interval-0s"
                            interval="0s" name="stop" timeout="20s"
                        />
            """
            )
            + f"""
                    </operations>
                </primitive>
                <primitive class="ocf" provider="pacemaker" type="booth-site"
                    id="booth-{name}-service"
                >
                    <instance_attributes
                        id="booth-{name}-service-instance_attributes"
                    >
                        <nvpair
                            id="booth-{name}-service-instance_attributes-config"
                            name="config" value="{self.fixture_cfg_path(name)}"
                        />
                    </instance_attributes>
                    <operations>
            """
            + (
                f"""
                        <op id="booth-{name}-service-monitor-interval-60s"
                            interval="60s" name="monitor"
                        />
            """
                if default_operations
                else f"""
                        <op id="booth-{name}-service-monitor-interval-10"
                            interval="10" name="monitor" start-delay="0"
                            timeout="20"
                        />
                        <op id="booth-{name}-service-reload-interval-0s"
                            interval="0s" name="reload" timeout="20"
                        />
                        <op id="booth-{name}-service-restart-interval-0s"
                            interval="0s" name="restart" timeout="20"
                        />
                        <op id="booth-{name}-service-start-interval-0s"
                            interval="0s" name="start" timeout="20"
                        />
                        <op id="booth-{name}-service-stop-interval-0s"
                            interval="0s" name="stop" timeout="20"
                        />
            """
            )
            + """
                    </operations>
                </primitive>
            </group>"""
            + ("</resources>" if wrap_in_resources else "")
        )

    def fixture_cfg_content(self, key_path=None, ticket_list=None):
        key_path = key_path or self.fixture_key_path()
        config = dedent(
            f"""\
            authfile = {key_path}
            site = 1.1.1.1
            site = 2.2.2.2
            arbitrator = 3.3.3.3
        """
        )
        if ticket_list:
            extra_lines = []
            for ticket_name, option_list in ticket_list:
                extra_lines.append(f'ticket = "{ticket_name}"')
                for name, value in option_list:
                    extra_lines.append(f"  {name} = {value}")
            if extra_lines:
                config += "\n".join(extra_lines) + "\n"
        return config.encode("utf-8")


@mock.patch(
    "pcs.lib.tools.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
@mock.patch("pcs.settings.booth_enable_authfile_set_enabled", False)
class ConfigSetup(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.sites = ["1.1.1.1", "2.2.2.2"]
        self.arbitrators = ["3.3.3.3"]

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_setup(
                self.env_assist.get_env(),
                self.sites,
                self.arbitrators,
                instance_name=instance_name,
            )
        )
        self.env_assist.assert_reports(
            [
                fixture_report_invalid_name(instance_name),
            ]
        )

    def test_peers_not_valid(self):
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_setup(
                self.env_assist.get_env(),
                ["1.1.1.1", "2.2.2.2"],
                ["3.3.3.3", "4.4.4.4"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(reports.codes.BOOTH_EVEN_PEERS_NUM, number=4),
            ]
        )

    def fixture_config_success(self, instance_name="booth"):
        self.config.raw_file.write(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(instance_name),
            RANDOM_KEY,
            name="raw_file.write.key",
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            self.fixture_cfg_content(self.fixture_key_path(instance_name)),
            name="raw_file.write.cfg",
        )

    def test_success_default_instance(self):
        self.fixture_config_success()
        commands.config_setup(
            self.env_assist.get_env(),
            self.sites,
            self.arbitrators,
        )

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        self.fixture_config_success(instance_name=instance_name)
        commands.config_setup(
            self.env_assist.get_env(),
            self.sites,
            self.arbitrators,
            instance_name=instance_name,
        )

    def test_files_exist_config(self):
        self.config.raw_file.write(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            RANDOM_KEY,
            name="raw_file.write.key",
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(),
            already_exists=True,
            name="raw_file.write.cfg",
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_setup(
                self.env_assist.get_env(),
                self.sites,
                self.arbitrators,
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_ALREADY_EXISTS,
                    force_code=reports.codes.FORCE,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    node="",
                ),
            ]
        )

    def test_files_exist_key(self):
        self.config.raw_file.write(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            RANDOM_KEY,
            already_exists=True,
            name="raw_file.write.key",
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_setup(
                self.env_assist.get_env(),
                self.sites,
                self.arbitrators,
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_ALREADY_EXISTS,
                    force_code=reports.codes.FORCE,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=self.fixture_key_path(),
                    node="",
                ),
            ]
        )

    def test_files_exist_forced(self):
        self.config.raw_file.write(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            RANDOM_KEY,
            can_overwrite=True,
            name="raw_file.write.key",
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(),
            can_overwrite=True,
            name="raw_file.write.cfg",
        )

        commands.config_setup(
            self.env_assist.get_env(),
            self.sites,
            self.arbitrators,
            overwrite_existing=True,
        )

    def _assert_write_config_error(self, error, booth_dir_exists):
        self.config.raw_file.write(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            RANDOM_KEY,
            name="raw_file.write.key",
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(),
            exception_msg=error,
            name="raw_file.write.cfg",
        )
        self.config.fs.exists(self.booth_dir, booth_dir_exists)

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_setup(
                self.env_assist.get_env(),
                self.sites,
                self.arbitrators,
            )
        )

    def test_write_config_error(self):
        error = "an error occurred"
        self._assert_write_config_error(error, True)
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_WRITE,
                ),
            ]
        )

    def test_write_config_error_booth_dir_missing(self):
        error = "an error occurred"
        self._assert_write_config_error(error, False)
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_PATH_NOT_EXISTS,
                    path=self.booth_dir,
                ),
            ]
        )

    def _assert_write_key_error(self, error, booth_dir_exists):
        self.config.raw_file.write(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            RANDOM_KEY,
            exception_msg=error,
            name="raw_file.write.key",
        )
        self.config.fs.exists(self.booth_dir, booth_dir_exists)

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_setup(
                self.env_assist.get_env(),
                self.sites,
                self.arbitrators,
            )
        )

    def test_write_key_error(self):
        error = "an error occurred"
        self._assert_write_key_error(error, True)
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=self.fixture_key_path(),
                    reason=error,
                    operation=RawFileError.ACTION_WRITE,
                ),
            ]
        )

    def test_write_key_error_booth_dir_missing(self):
        error = "an error occurred"
        self._assert_write_key_error(error, False)
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_PATH_NOT_EXISTS,
                    path=self.booth_dir,
                ),
            ]
        )

    def test_not_live(self):
        key_path = "/tmp/pcs_test/booth.key"
        self.config.env.set_booth(
            {
                "config_data": None,
                "key_data": None,
                "key_path": key_path,
            }
        )
        env = self.env_assist.get_env()

        commands.config_setup(env, self.sites, self.arbitrators)

        self.assertEqual(
            env.get_booth_env(name="").export(),
            {
                "config_file": {
                    "content": self.fixture_cfg_content(key_path),
                },
                "key_file": {
                    "content": RANDOM_KEY,
                },
            },
        )

    def test_partially_not_life(self):
        self.config.env.set_booth(
            {
                "config_data": None,
            }
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_setup(
                self.env_assist.get_env(),
                self.sites,
                self.arbitrators,
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_NOT_CONSISTENT,
                    mocked_files=[file_type_codes.BOOTH_CONFIG],
                    required_files=[file_type_codes.BOOTH_KEY],
                ),
            ],
            expected_in_processor=False,
        )


@mock.patch(
    "pcs.lib.tools.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
@mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
class ConfigSetupAuthfileFix(TestCase, FixtureMixin):
    def setUp(self):
        self.instance = "instance name"
        self.env_assist, self.config = get_env_tools(self)
        self.sites = ["1.1.1.1", "2.2.2.2"]
        self.arbitrators = ["3.3.3.3"]

    def test_success_default_instance(self):
        self.config.raw_file.write(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(self.instance),
            RANDOM_KEY,
            name="raw_file.write.key",
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(self.instance),
            dedent(
                """\
                authfile = {key_path}
                {fix_option} = yes
                site = 1.1.1.1
                site = 2.2.2.2
                arbitrator = 3.3.3.3
                """.format(
                    fix_option=constants.AUTHFILE_FIX_OPTION,
                    key_path=self.fixture_key_path(self.instance),
                )
            ).encode("utf-8"),
            name="raw_file.write.cfg",
        )
        commands.config_setup(
            self.env_assist.get_env(),
            self.sites,
            self.arbitrators,
            instance_name=self.instance,
        )


class ConfigDestroy(TestCase, FixtureMixin):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.cib_path = os.path.join(settings.cib_dir, "cib.xml")

    def fixture_config_booth_not_used(self, instance_name="booth"):
        self.config.fs.exists(self.cib_path, True)
        self.config.runner.cib.load()
        self.config.services.is_running(
            "booth", instance=instance_name, return_value=False
        )
        self.config.services.is_enabled(
            "booth", instance=instance_name, return_value=False
        )

    def fixture_config_booth_used(
        self,
        instance_name,
        cib_exists=False,
        pcmk_running=False,
        pcmk_remote_running=False,
        booth_running=False,
        booth_enabled=False,
    ):
        cib_load_exception = False
        self.config.fs.exists(self.cib_path, cib_exists)
        if not cib_exists:
            self.config.services.is_running(
                "pacemaker",
                return_value=pcmk_running,
                name="services.is_running.pcmk",
            )
            if not pcmk_running:
                self.config.services.is_running(
                    "pacemaker_remoted",
                    return_value=pcmk_remote_running,
                    name="services.is_running.pcmk_remote",
                )
        if cib_exists and not pcmk_running and not pcmk_remote_running:
            self.config.runner.cib.load(
                returncode=1, stderr="unable to get cib, pcmk is not running"
            )
            cib_load_exception = True
        elif pcmk_running or pcmk_remote_running:
            self.config.runner.cib.load(resources=self.fixture_cib_resources())
        if not cib_load_exception:
            self.config.services.is_running(
                "booth", instance=instance_name, return_value=booth_running
            )
            self.config.services.is_enabled(
                "booth", instance=instance_name, return_value=booth_enabled
            )

    def fixture_config_success(self, instance_name="booth"):
        self.fixture_config_booth_not_used(instance_name)
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            content=self.fixture_cfg_content(
                self.fixture_key_path(instance_name)
            ),
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(instance_name),
            fail_if_file_not_found=False,
            name="raw_file.remove.key",
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            fail_if_file_not_found=True,
            name="raw_file.remove.cfg",
        )

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(
                self.env_assist.get_env(), instance_name=instance_name
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def test_success_default_instance(self):
        self.fixture_config_success()
        commands.config_destroy(self.env_assist.get_env())

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        self.fixture_config_success(instance_name)
        commands.config_destroy(
            self.env_assist.get_env(), instance_name=instance_name
        )

    def test_success_no_booth_key(self):
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=bytes(),
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            fail_if_file_not_found=True,
            name="raw_file.remove.cfg",
        )

        commands.config_destroy(self.env_assist.get_env())

    def test_not_live_booth(self):
        self.config.env.set_booth(
            {
                "config_data": "some config data",
                "key_data": "some key data",
                "key_path": "some key path",
            }
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(
                self.env_assist.get_env(),
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def test_not_live_cib(self):
        self.config.env.set_cib_data("<cib/>")
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(
                self.env_assist.get_env(),
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.CIB],
                ),
            ],
            expected_in_processor=False,
        )

    def test_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": "some config data",
                "key_data": "some key data",
                "key_path": "some key path",
            }
        )
        self.config.env.set_cib_data("<cib/>")
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(
                self.env_assist.get_env(),
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                        file_type_codes.CIB,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def test_booth_config_in_use_cib_pcmk(self):
        instance_name = "booth"
        self.fixture_config_booth_used(instance_name, pcmk_running=True)

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(self.env_assist.get_env()),
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_IS_USED,
                    name=instance_name,
                    detail=reports.const.BOOTH_CONFIG_USED_IN_CLUSTER_RESOURCE,
                    resource_name="booth_resource",
                ),
            ]
        )

    def test_booth_config_in_use_cib_pcmk_remote(self):
        instance_name = "booth"
        self.fixture_config_booth_used(instance_name, pcmk_remote_running=True)

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(self.env_assist.get_env()),
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_IS_USED,
                    name=instance_name,
                    detail=reports.const.BOOTH_CONFIG_USED_IN_CLUSTER_RESOURCE,
                    resource_name="booth_resource",
                ),
            ]
        )

    def test_pcmk_not_running(self):
        instance_name = "booth"
        self.fixture_config_booth_used(instance_name, cib_exists=True)

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.CIB_LOAD_ERROR,
                    reason="unable to get cib, pcmk is not running",
                )
            ],
            expected_in_processor=False,
        )

    def test_booth_config_in_use_systemd_running(self):
        instance_name = "booth"
        self.fixture_config_booth_used(instance_name, booth_running=True)

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(self.env_assist.get_env()),
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_IS_USED,
                    name=instance_name,
                    detail=reports.const.BOOTH_CONFIG_USED_RUNNING_IN_SYSTEMD,
                    resource_name=None,
                ),
            ]
        )

    def test_booth_config_in_use_systemd_enabled(self):
        instance_name = "booth"
        self.fixture_config_booth_used(instance_name, booth_enabled=True)

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(self.env_assist.get_env()),
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_IS_USED,
                    name=instance_name,
                    detail=reports.const.BOOTH_CONFIG_USED_ENABLED_IN_SYSTEMD,
                    resource_name=None,
                ),
            ]
        )

    def test_cannot_read_config(self):
        error = "an error"
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            exception_msg=error,
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    force_code=reports.codes.FORCE,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_cannot_read_config_forced(self):
        error = "an error"
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            exception_msg=error,
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            fail_if_file_not_found=True,
            name="raw_file.remove.cfg",
        )

        commands.config_destroy(
            self.env_assist.get_env(),
            ignore_config_load_problems=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_config_parse_error(self):
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content="invalid config".encode("utf-8"),
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    force_code=reports.codes.FORCE,
                    line_list=["invalid config"],
                    file_path=self.fixture_cfg_path(),
                ),
            ]
        )

    def test_config_parse_error_forced(self):
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content="invalid config".encode("utf-8"),
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            fail_if_file_not_found=True,
            name="raw_file.remove.cfg",
        )

        commands.config_destroy(
            self.env_assist.get_env(),
            ignore_config_load_problems=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    line_list=["invalid config"],
                    file_path=self.fixture_cfg_path(),
                ),
            ]
        )

    def test_key_already_deleted(self):
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            fail_if_file_not_found=False,
            file_not_found_exception=True,
            name="raw_file.remove.key",
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            fail_if_file_not_found=True,
            name="raw_file.remove.cfg",
        )

        commands.config_destroy(self.env_assist.get_env())

    def test_cannot_delete_key(self):
        error = "an error"
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            fail_if_file_not_found=False,
            exception_msg=error,
            name="raw_file.remove.key",
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    force_code=reports.codes.FORCE,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=self.fixture_key_path(),
                    reason=error,
                    operation=RawFileError.ACTION_REMOVE,
                ),
            ]
        )

    def test_cannot_delete_key_forced(self):
        error = "an error"
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            fail_if_file_not_found=False,
            exception_msg=error,
            name="raw_file.remove.key",
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            fail_if_file_not_found=True,
            name="raw_file.remove.cfg",
        )

        commands.config_destroy(
            self.env_assist.get_env(),
            ignore_config_load_problems=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=self.fixture_key_path(),
                    reason=error,
                    operation=RawFileError.ACTION_REMOVE,
                ),
            ]
        )

    def test_cannot_delete_config_forced(self):
        error = "an error"
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            fail_if_file_not_found=False,
            name="raw_file.remove.key",
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            fail_if_file_not_found=True,
            exception_msg=error,
            name="raw_file.remove.cfg",
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_destroy(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_REMOVE,
                ),
            ]
        )

    def test_keyfile_outside_of_booth_dir(self):
        key_path = "/tmp/pcs_test/booth.key"
        self.fixture_config_booth_not_used()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=f"authfile = {key_path}".encode("utf-8"),
        )
        self.config.raw_file.remove(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            fail_if_file_not_found=True,
            name="raw_file.remove.cfg",
        )

        commands.config_destroy(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.BOOTH_UNSUPPORTED_FILE_LOCATION,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=key_path,
                    expected_dir=self.booth_dir,
                ),
            ]
        )


class ConfigText(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_text(
                self.env_assist.get_env(), instance_name=instance_name
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def test_success_default_instance(self):
        config_content = "my config content".encode("utf-8")
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=config_content,
        )
        self.assertEqual(
            commands.config_text(self.env_assist.get_env()),
            config_content,
        )

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        config_content = "my config content".encode("utf-8")
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            content=config_content,
        )
        self.assertEqual(
            commands.config_text(
                self.env_assist.get_env(), instance_name=instance_name
            ),
            config_content,
        )

    def test_not_live(self):
        config_content = "my config content".encode("utf-8")
        key_path = "/tmp/pcs_test/booth.key"
        self.config.env.set_booth(
            {
                "config_data": config_content,
                "key_data": "some key data".encode("utf-8"),
                "key_path": key_path,
            }
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_text(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def test_cannot_read_config(self):
        error = "an error"
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            exception_msg=error,
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_text(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_remote_success(self):
        instance_name = "my_booth"
        config_content = "my config content"
        self.config.http.booth.get_config(
            instance_name,
            config_data=config_content,
            node_labels=["node1"],
        )
        self.assertEqual(
            commands.config_text(
                self.env_assist.get_env(),
                instance_name=instance_name,
                node_name="node1",
            ),
            config_content.encode("utf-8"),
        )

    def test_remote_config_server_error(self):
        instance_name = "booth"
        node_name = "node1"
        server_error = (
            "some error like 'config does not exist' or 'instance name invalid'"
        )
        self.config.http.booth.get_config(
            instance_name,
            communication_list=[
                dict(
                    label=node_name,
                    response_code=400,
                    output=server_error,
                )
            ],
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_text(
                self.env_assist.get_env(), node_name=node_name
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node_name,
                    command="remote/booth_get_config",
                    reason=server_error,
                ),
            ]
        )

    def test_remote_bad_response(self):
        instance_name = "booth"
        node_name = "node1"
        self.config.http.booth.get_config(
            instance_name,
            communication_list=[
                dict(
                    label=node_name,
                    output="not a json",
                )
            ],
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_text(
                self.env_assist.get_env(), node_name=node_name
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=node_name,
                ),
            ]
        )

    def test_remote_connection_error(self):
        instance_name = "booth"
        node_name = "node1"
        error = "an error"
        self.config.http.booth.get_config(
            instance_name,
            communication_list=[
                dict(
                    label=node_name,
                    was_connected=False,
                    errno=1,
                    error_msg=error,
                )
            ],
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_text(
                self.env_assist.get_env(), node_name=node_name
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node_name,
                    command="remote/booth_get_config",
                    reason=error,
                ),
            ]
        )


class ConfigTicketAdd(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_add(
                self.env_assist.get_env(),
                "ticketA",
                {},
                instance_name=instance_name,
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def fixture_config_success(self, instance_name="booth"):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            content=self.fixture_cfg_content(
                self.fixture_key_path(instance_name)
            ),
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            self.fixture_cfg_content(
                self.fixture_key_path(instance_name),
                ticket_list=[["ticketA", []]],
            ),
            can_overwrite=True,
        )

    def test_success_default_instance(self):
        self.fixture_config_success()
        commands.config_ticket_add(self.env_assist.get_env(), "ticketA", {})

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        self.fixture_config_success(instance_name=instance_name)
        commands.config_ticket_add(
            self.env_assist.get_env(),
            "ticketA",
            {},
            instance_name=instance_name,
        )

    def test_success_not_live(self):
        key_data = "some key data"
        key_path = "some key path"
        self.config.env.set_booth(
            {
                "config_data": self.fixture_cfg_content(),
                "key_data": key_data,
                "key_path": key_path,
            }
        )
        env = self.env_assist.get_env()

        commands.config_ticket_add(env, "ticketA", {})
        self.assertEqual(
            env.get_booth_env(name="").export(),
            {
                "config_file": {
                    "content": self.fixture_cfg_content(
                        ticket_list=[["ticketA", []]]
                    ),
                },
                "key_file": {
                    "content": key_data,
                },
            },
        )

    def assert_success_ticket_options(self, options_command, options_config):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(ticket_list=[["ticketA", options_config]]),
            can_overwrite=True,
        )
        commands.config_ticket_add(
            self.env_assist.get_env(), "ticketA", options_command
        )

    def test_success_ticket_options(self):
        self.assert_success_ticket_options(
            {"timeout": "20", "retries": "10"},
            [("retries", "10"), ("timeout", "20")],
        )

    def test_success_ticket_options_mode(self):
        self.assert_success_ticket_options(
            {"timeout": "20", "retries": "10", "mode": "manual"},
            [("mode", "manual"), ("retries", "10"), ("timeout", "20")],
        )

    def test_success_ticket_options_mode_case_insensitive(self):
        self.assert_success_ticket_options(
            {"timeout": "20", "retries": "10", "mode": "MaNuAl"},
            [("mode", "manual"), ("retries", "10"), ("timeout", "20")],
        )

    def test_ticket_already_exists(self):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(ticket_list=[["ticketA", []]]),
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_add(
                self.env_assist.get_env(),
                "ticketA",
                {},
                allow_unknown_options=True,
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_TICKET_DUPLICATE,
                    ticket_name="ticketA",
                ),
            ]
        )

    def test_validator_errors(self):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_add(
                self.env_assist.get_env(), "@ticketA", {"a": "A"}
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_TICKET_NAME_INVALID,
                    ticket_name="@ticketA",
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE,
                    option_names=["a"],
                    option_type="booth ticket",
                    allowed=[
                        "acquire-after",
                        "attr-prereq",
                        "before-acquire-handler",
                        "expire",
                        "mode",
                        "renewal-freq",
                        "retries",
                        "timeout",
                        "weights",
                    ],
                    allowed_patterns=[],
                ),
            ]
        )

    def test_invalid_ticket_options_forced(self):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(ticket_list=[["ticketA", [("a", "A")]]]),
            can_overwrite=True,
        )
        commands.config_ticket_add(
            self.env_assist.get_env(),
            "ticketA",
            {"a": "A"},
            allow_unknown_options=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["a"],
                    option_type="booth ticket",
                    allowed=[
                        "acquire-after",
                        "attr-prereq",
                        "before-acquire-handler",
                        "expire",
                        "mode",
                        "renewal-freq",
                        "retries",
                        "timeout",
                        "weights",
                    ],
                    allowed_patterns=[],
                ),
            ]
        )

    def test_config_parse_error(self):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content="invalid config".encode("utf-8"),
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_add(
                self.env_assist.get_env(),
                "ticketA",
                {},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    line_list=["invalid config"],
                    file_path=self.fixture_cfg_path(),
                ),
            ]
        )

    def test_cannot_read_config(self):
        error = "an error"
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            exception_msg=error,
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_add(
                self.env_assist.get_env(),
                "ticketA",
                {},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_cannot_read_config_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": None,
                "key_data": None,
                "key_path": None,
            }
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_add(
                self.env_assist.get_env(),
                "ticketA",
                {},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path="",
                    reason="No such file or directory",
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_cannot_write_config(self):
        error = "an error"
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(ticket_list=[["ticketA", []]]),
            can_overwrite=True,
            exception_msg=error,
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_add(
                self.env_assist.get_env(),
                "ticketA",
                {},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_WRITE,
                ),
            ]
        )


class ConfigTicketRemove(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_remove(
                self.env_assist.get_env(),
                "ticketA",
                instance_name=instance_name,
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def fixture_config_success(self, instance_name="booth"):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            self.fixture_cfg_content(
                self.fixture_key_path(instance_name),
                ticket_list=[
                    ["ticketA", []],
                    ["ticketB", []],
                    ["ticketC", []],
                ],
            ),
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            self.fixture_cfg_content(
                self.fixture_key_path(instance_name),
                ticket_list=[
                    ["ticketA", []],
                    ["ticketC", []],
                ],
            ),
            can_overwrite=True,
        )

    def test_success_default_instance(self):
        self.fixture_config_success()
        commands.config_ticket_remove(self.env_assist.get_env(), "ticketB")

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        self.fixture_config_success(instance_name=instance_name)
        commands.config_ticket_remove(
            self.env_assist.get_env(), "ticketB", instance_name=instance_name
        )

    def test_success_not_live(self):
        key_data = "some key data"
        key_path = "some key path"
        self.config.env.set_booth(
            {
                "config_data": self.fixture_cfg_content(
                    ticket_list=[["ticketB", []]]
                ),
                "key_data": key_data,
                "key_path": key_path,
            }
        )
        env = self.env_assist.get_env()

        commands.config_ticket_remove(env, "ticketB")
        self.assertEqual(
            env.get_booth_env(name="").export(),
            {
                "config_file": {
                    "content": self.fixture_cfg_content(),
                },
                "key_file": {
                    "content": key_data,
                },
            },
        )

    def test_success_ticket_options(self):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(
                ticket_list=[
                    ["ticketA", [("a1", "A1"), ("a2", "A2")]],
                    ["ticketB", [("b1", "B1"), ("b2", "B2")]],
                    ["ticketC", [("c1", "C1"), ("c2", "C2")]],
                ]
            ),
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(
                ticket_list=[
                    ["ticketA", [("a1", "A1"), ("a2", "A2")]],
                    ["ticketC", [("c1", "C1"), ("c2", "C2")]],
                ]
            ),
            can_overwrite=True,
        )
        commands.config_ticket_remove(self.env_assist.get_env(), "ticketB")

    def test_ticket_does_not_exist(self):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(
                ticket_list=[
                    ["ticketA", []],
                    ["ticketC", []],
                ]
            ),
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_remove(
                self.env_assist.get_env(), "ticketB"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_TICKET_DOES_NOT_EXIST,
                    ticket_name="ticketB",
                ),
            ]
        )

    def test_config_parse_error(self):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content="invalid config".encode("utf-8"),
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_remove(
                self.env_assist.get_env(), "ticketB"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    line_list=["invalid config"],
                    file_path=self.fixture_cfg_path(),
                ),
            ]
        )

    def test_cannot_read_config(self):
        error = "an error"
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            exception_msg=error,
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_remove(
                self.env_assist.get_env(), "ticketB"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_cannot_read_config_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": None,
                "key_data": None,
                "key_path": None,
            }
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_remove(
                self.env_assist.get_env(), "ticketB"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path="",
                    reason="No such file or directory",
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_cannot_write_config(self):
        error = "an error"
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(
                ticket_list=[
                    ["ticketB", []],
                ]
            ),
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            self.fixture_cfg_content(),
            can_overwrite=True,
            exception_msg=error,
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_ticket_remove(
                self.env_assist.get_env(), "ticketB"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_WRITE,
                ),
            ]
        )


class CreateInCluster(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: commands.create_in_cluster(
                self.env_assist.get_env(),
                self.site_ip,
                instance_name=instance_name,
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def fixture_config_success(self, instance_name="booth"):
        self.config.runner.cib.load()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            content=self.fixture_cfg_content(
                self.fixture_key_path(instance_name)
            ),
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:heartbeat:IPaddr2",
            name="runner.pcmk.load_agent.ipaddr2",
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:booth-site",
            name="runner.pcmk.load_agent.booth-site",
        )
        self.config.env.push_cib(
            resources=self.fixture_cib_booth_group(instance_name)
        )

    def test_success_default_instance(self):
        self.fixture_config_success()
        commands.create_in_cluster(self.env_assist.get_env(), self.site_ip)

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        self.fixture_config_success(instance_name=instance_name)
        commands.create_in_cluster(
            self.env_assist.get_env(), self.site_ip, instance_name=instance_name
        )

    def test_success_not_live_cib(self):
        tmp_file = "/fake/tmp_file"
        env = dict(CIB_file=tmp_file)
        with open(rc("cib-empty.xml")) as cib_file:
            self.config.env.set_cib_data(cib_file.read(), cib_tempfile=tmp_file)
        self.config.runner.cib.load(env=env)
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:heartbeat:IPaddr2",
            name="runner.pcmk.load_agent.ipaddr2",
            env=env,
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:booth-site",
            name="runner.pcmk.load_agent.booth-site",
            env=env,
        )
        self.config.env.push_cib(resources=self.fixture_cib_booth_group())
        commands.create_in_cluster(self.env_assist.get_env(), self.site_ip)

    def test_not_live_booth(self):
        self.config.env.set_booth(
            {
                "config_data": "some config data",
                "key_data": "some key data",
                "key_path": "some key path",
            }
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.create_in_cluster(
                self.env_assist.get_env(), self.site_ip
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def test_booth_resource_already_created(self):
        self.config.runner.cib.load(resources=self.fixture_cib_booth_group())
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.create_in_cluster(
                self.env_assist.get_env(), self.site_ip
            )
        )
        self.env_assist.assert_reports(
            [fixture.error(reports.codes.BOOTH_ALREADY_IN_CIB, name="booth")]
        )

    def test_booth_config_does_not_exist(self):
        error = "an error"
        self.config.runner.cib.load().raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            exception_msg=error,
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.create_in_cluster(
                self.env_assist.get_env(), self.site_ip
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=error,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_ip_agent_missing(self):
        self.config.runner.cib.load()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:heartbeat:IPaddr2",
            agent_is_missing=True,
            name="runner.pcmk.load_agent.ipaddr2",
            stderr=REASON,
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.create_in_cluster(
                self.env_assist.get_env(), self.site_ip
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    force_code=reports.codes.FORCE,
                    agent="ocf:heartbeat:IPaddr2",
                    reason=REASON,
                ),
            ]
        )

    def test_booth_agent_missing(self):
        self.config.runner.cib.load()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:heartbeat:IPaddr2",
            name="runner.pcmk.load_agent.ipaddr2",
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:booth-site",
            agent_is_missing=True,
            name="runner.pcmk.load_agent.booth-site",
            stderr=REASON,
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.create_in_cluster(
                self.env_assist.get_env(), self.site_ip
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    force_code=reports.codes.FORCE,
                    agent="ocf:pacemaker:booth-site",
                    reason=REASON,
                ),
            ]
        )

    def test_agents_missing_forced(self):
        self.config.runner.cib.load()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:heartbeat:IPaddr2",
            agent_is_missing=True,
            name="runner.pcmk.load_agent.ipaddr2",
            stderr=REASON,
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:booth-site",
            agent_is_missing=True,
            name="runner.pcmk.load_agent.booth-site",
            stderr=REASON,
        )
        self.config.env.push_cib(
            resources=self.fixture_cib_booth_group(default_operations=True)
        )
        commands.create_in_cluster(
            self.env_assist.get_env(),
            self.site_ip,
            allow_absent_resource_agent=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="ocf:heartbeat:IPaddr2",
                    reason=REASON,
                ),
                fixture.warn(
                    reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="ocf:pacemaker:booth-site",
                    reason=REASON,
                ),
            ]
        )


@mock.patch(
    "pcs.lib.commands.booth._stop_resources_wait",
    lambda env, cib, elements: cib,
)
class RemoveFromCluster(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: commands.remove_from_cluster(
                self.env_assist.get_env(), instance_name=instance_name
            ),
            [fixture_report_invalid_name(instance_name)],
            expected_in_processor=False,
        )

    def test_success_default_instance(self):
        self.config.runner.cib.load(resources=self.fixture_cib_booth_group())
        self.config.env.push_cib(resources="<resources/>")

        commands.remove_from_cluster(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_REMOVE_RESOURCES,
                    id_list=["booth-booth-ip", "booth-booth-service"],
                ),
                fixture.info(
                    reports.codes.CIB_REMOVE_DEPENDANT_ELEMENTS,
                    id_tag_map={"booth-booth-group": "group"},
                ),
            ]
        )

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        self.config.runner.cib.load(
            resources=self.fixture_cib_booth_group(instance_name)
        )
        self.config.env.push_cib(resources="<resources/>")
        commands.remove_from_cluster(
            self.env_assist.get_env(),
            instance_name=instance_name,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_REMOVE_RESOURCES,
                    id_list=["booth-my_booth-ip", "booth-my_booth-service"],
                ),
                fixture.info(
                    reports.codes.CIB_REMOVE_DEPENDANT_ELEMENTS,
                    id_tag_map={"booth-my_booth-group": "group"},
                ),
            ]
        )

    def test_success_not_live_cib(self):
        tmp_file = "/fake/tmp_file"
        env = dict(CIB_file=tmp_file)
        cib_xml_man = XmlManipulation.from_file(rc("cib-empty.xml"))
        cib_xml_man.append_to_first_tag_name(
            "resources", self.fixture_cib_booth_group(wrap_in_resources=False)
        )
        # This makes env.is_cib_live return False
        self.config.env.set_cib_data(str(cib_xml_man), cib_tempfile=tmp_file)
        # This instructs the runner to actually return our mocked cib
        self.config.runner.cib.load_content(str(cib_xml_man), env=env)
        self.config.env.push_cib(
            resources="<resources/>", load_key="runner.cib.load_content"
        )
        commands.remove_from_cluster(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_REMOVE_RESOURCES,
                    id_list=["booth-booth-ip", "booth-booth-service"],
                ),
                fixture.info(
                    reports.codes.CIB_REMOVE_DEPENDANT_ELEMENTS,
                    id_tag_map={"booth-booth-group": "group"},
                ),
            ]
        )

    def test_not_live_booth(self):
        self.config.env.set_booth(
            {
                "config_data": "some config data",
                "key_data": "some key data",
                "key_path": "some key path",
            }
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.remove_from_cluster(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def test_booth_resource_does_not_exist(self):
        (self.config.runner.cib.load())
        self.env_assist.assert_raise_library_error(
            lambda: commands.remove_from_cluster(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_NOT_EXISTS_IN_CIB,
                    name="booth",
                ),
            ]
        )

    def test_more_booth_resources(self):
        self.config.runner.cib.load(resources=self.fixture_cib_more_resources())
        self.env_assist.assert_raise_library_error(
            lambda: commands.remove_from_cluster(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_MULTIPLE_TIMES_IN_CIB,
                    force_code=reports.codes.FORCE,
                    name="booth",
                ),
            ]
        )

    def test_more_booth_resources_forced(self):
        self.config.runner.cib.load(resources=self.fixture_cib_more_resources())
        self.config.env.push_cib(resources="<resources/>")
        commands.remove_from_cluster(
            self.env_assist.get_env(), force_flags=[reports.codes.FORCE]
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_REMOVE_RESOURCES,
                    id_list=["booth1", "booth2"],
                ),
                fixture.warn(
                    reports.codes.BOOTH_MULTIPLE_TIMES_IN_CIB,
                    name="booth",
                ),
            ]
        )


class Restart(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: commands.restart(
                self.env_assist.get_env(),
                instance_name=instance_name,
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def test_success_default_instance(self):
        self.config.runner.cib.load(resources=self.fixture_cib_booth_group())
        self.config.runner.pcmk.resource_restart("booth-booth-service")
        commands.restart(self.env_assist.get_env())

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        self.config.runner.cib.load(
            resources=self.fixture_cib_booth_group(instance_name)
        )
        self.config.runner.pcmk.resource_restart(
            f"booth-{instance_name}-service"
        )
        commands.restart(
            self.env_assist.get_env(),
            instance_name=instance_name,
        )

    def test_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": "some config data",
                "key_data": "some key data",
                "key_path": "some key path",
            }
        )
        self.config.env.set_cib_data("<cib />")
        self.env_assist.assert_raise_library_error(
            lambda: commands.restart(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                        file_type_codes.CIB,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def test_booth_resource_does_not_exist(self):
        self.config.runner.cib.load()
        self.env_assist.assert_raise_library_error(
            lambda: commands.restart(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_NOT_EXISTS_IN_CIB,
                    name="booth",
                ),
            ]
        )

    def test_more_booth_resources(self):
        self.config.runner.cib.load(resources=self.fixture_cib_more_resources())
        self.env_assist.assert_raise_library_error(
            lambda: commands.restart(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_MULTIPLE_TIMES_IN_CIB,
                    force_code=reports.codes.FORCE,
                    name="booth",
                ),
            ]
        )

    def test_more_booth_resources_forced(self):
        self.config.runner.cib.load(resources=self.fixture_cib_more_resources())
        self.config.runner.pcmk.resource_restart(
            "booth1", name="runner.pcmk.restart.1"
        )
        self.config.runner.pcmk.resource_restart(
            "booth2", name="runner.pcmk.restart.2"
        )
        commands.restart(
            self.env_assist.get_env(),
            allow_multiple=True,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.BOOTH_MULTIPLE_TIMES_IN_CIB,
                    name="booth",
                ),
            ]
        )


class TicketGrantRevokeMixin(FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.ticket = "ticketA"

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: self.command(
                self.env_assist.get_env(),
                self.ticket,
                instance_name=instance_name,
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def test_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": "some config data",
                "key_data": "some key data",
                "key_path": "some key path",
            }
        )
        self.config.env.set_cib_data("<cib/>")
        self.env_assist.assert_raise_library_error(
            lambda: self.command(self.env_assist.get_env(), self.ticket),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                        file_type_codes.CIB,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def test_success_site_ip_specified(self):
        self.get_booth_call()(self.ticket, self.site_ip)
        self.command(
            self.env_assist.get_env(), self.ticket, site_ip=self.site_ip
        )

    def test_success_site_ip_not_specified(self):
        self.config.runner.cib.load(resources=self.fixture_cib_booth_group())
        self.get_booth_call()(self.ticket, self.site_ip)
        self.command(self.env_assist.get_env(), self.ticket)

    def test_cannot_find_site_ip(self):
        self.config.runner.cib.load()
        self.env_assist.assert_raise_library_error(
            lambda: self.command(self.env_assist.get_env(), self.ticket),
            [
                fixture.error(
                    reports.codes.BOOTH_CANNOT_DETERMINE_LOCAL_SITE_IP,
                ),
            ],
            expected_in_processor=False,
        )

    def test_cannot_load_cib(self):
        self.config.runner.cib.load(
            stderr="some stderr",
            returncode=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command(self.env_assist.get_env(), self.ticket),
            [
                fixture.error(
                    reports.codes.BOOTH_CANNOT_DETERMINE_LOCAL_SITE_IP,
                ),
            ],
            expected_in_processor=False,
        )

    def test_ticket_action_failed(self):
        self.get_booth_call()(
            self.ticket,
            self.site_ip,
            stdout="some stdout",
            stderr="some stderr",
            returncode=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command(
                self.env_assist.get_env(), self.ticket, site_ip=self.site_ip
            ),
            [
                fixture.error(
                    reports.codes.BOOTH_TICKET_OPERATION_FAILED,
                    operation=self.operation,
                    ticket_name=self.ticket,
                    site_ip=self.site_ip,
                    reason="some stderr\nsome stdout",
                ),
            ],
            expected_in_processor=False,
        )


class TicketGrant(TicketGrantRevokeMixin, TestCase):
    # without 'staticmethod' the command would become a method of this class
    command = staticmethod(commands.ticket_grant)
    operation = "grant"

    def get_booth_call(self):
        return self.config.runner.booth.ticket_grant


class TicketRevoke(TicketGrantRevokeMixin, TestCase):
    # without 'staticmethod' the command would become a method of this class
    command = staticmethod(commands.ticket_revoke)
    operation = "revoke"

    def get_booth_call(self):
        return self.config.runner.booth.ticket_revoke


class ConfigSyncTest(TestCase, FixtureMixin):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.node_list = ["rh7-1", "rh7-2"]
        self.config.env.set_known_nodes(self.node_list)
        self.reason = "fail"

    def fixture_config_success(self, instance_name="booth"):
        config_content = self.fixture_cfg_content(
            self.fixture_key_path(instance_name)
        )
        self.fixture_config_read_success(instance_name=instance_name)
        self.config.http.booth.send_config(
            instance_name,
            config_content.decode("utf-8"),
            authfile=os.path.basename(self.fixture_key_path(instance_name)),
            authfile_data=RANDOM_KEY,
            node_labels=self.node_list,
        )

    def fixture_config_read_success(self, instance_name="booth"):
        config_content = self.fixture_cfg_content(
            self.fixture_key_path(instance_name)
        )
        self.config.corosync_conf.load()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(instance_name),
            content=config_content,
            name="raw_file.read.conf",
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(instance_name),
            content=RANDOM_KEY,
            name="raw_file.read.key",
        )

    def fixture_reports_success(self, instance_name="booth"):
        return [
            fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED)
        ] + [
            fixture.info(
                reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                node=node,
                name_list=[instance_name],
            )
            for node in self.node_list
        ]

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(
                self.env_assist.get_env(), instance_name=instance_name
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def test_success_default_instance(self):
        self.fixture_config_success()
        commands.config_sync(self.env_assist.get_env())
        self.env_assist.assert_reports(self.fixture_reports_success())

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        self.fixture_config_success(instance_name=instance_name)
        commands.config_sync(
            self.env_assist.get_env(), instance_name=instance_name
        )
        self.env_assist.assert_reports(
            self.fixture_reports_success(instance_name=instance_name)
        )

    def test_not_live_cib(self):
        self.config.env.set_cib_data("<cib/>")
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.CIB],
                ),
            ],
            expected_in_processor=False,
        )

    def fixture_config_success_not_live(self, instance_name="booth"):
        key_data = RANDOM_KEY
        key_path = os.path.join(settings.booth_config_dir, "some.key")
        config_data = self.fixture_cfg_content(key_path=key_path)
        self.config.env.set_booth(
            {
                "config_data": config_data,
                "key_data": key_data,
                "key_path": "some key path",
            }
        )
        self.config.corosync_conf.load(node_name_list=self.node_list)
        self.config.http.booth.send_config(
            instance_name,
            config_data.decode("utf-8"),
            authfile=os.path.basename(key_path),
            authfile_data=key_data,
            node_labels=self.node_list,
        )

    def test_not_live_booth_default_instance(self):
        self.fixture_config_success_not_live()
        commands.config_sync(self.env_assist.get_env())
        self.env_assist.assert_reports(self.fixture_reports_success())

    def test_not_live_booth_custom_instance(self):
        instance_name = "my_booth"
        self.fixture_config_success_not_live(instance_name=instance_name)
        commands.config_sync(
            self.env_assist.get_env(), instance_name=instance_name
        )
        self.env_assist.assert_reports(
            self.fixture_reports_success(instance_name=instance_name)
        )

    def test_some_node_names_missing(self):
        nodes = ["rh7-2"]
        self.fixture_config_read_success()
        self.config.corosync_conf.load(
            filename="corosync-some-node-names.conf",
            instead="corosync_conf.load",
        )
        self.config.http.booth.send_config(
            "booth",
            self.fixture_cfg_content().decode("utf-8"),
            authfile=os.path.basename(self.fixture_key_path()),
            authfile_data=RANDOM_KEY,
            node_labels=nodes,
        )
        commands.config_sync(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=False,
                ),
            ]
            + [
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=["booth"],
                )
                for node in nodes
            ]
        )

    def test_all_node_names_missing(self):
        self.fixture_config_read_success()
        self.config.corosync_conf.load(
            filename="corosync-no-node-names.conf",
            instead="corosync_conf.load",
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=False,
                ),
                fixture.error(reports.codes.COROSYNC_CONFIG_NO_NODES_DEFINED),
            ]
        )

    def test_node_failure(self):
        self.fixture_config_read_success()
        self.config.http.booth.send_config(
            "booth",
            self.fixture_cfg_content().decode("utf-8"),
            authfile=os.path.basename(self.fixture_key_path()),
            authfile_data=RANDOM_KEY,
            communication_list=[
                dict(
                    label=self.node_list[0],
                    response_code=400,
                    output=self.reason,
                ),
                dict(
                    label=self.node_list[1],
                ),
            ],
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env()), []
        )
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=self.node_list[1],
                    name_list=["booth"],
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_list[0],
                    reason=self.reason,
                    command="remote/booth_set_config",
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                ),
            ]
        )

    def test_node_failure_skip_offline(self):
        self.fixture_config_read_success()
        self.config.http.booth.send_config(
            "booth",
            self.fixture_cfg_content().decode("utf-8"),
            authfile=os.path.basename(self.fixture_key_path()),
            authfile_data=RANDOM_KEY,
            communication_list=[
                dict(
                    label=self.node_list[0],
                    response_code=400,
                    output=self.reason,
                ),
                dict(
                    label=self.node_list[1],
                ),
            ],
        )

        commands.config_sync(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=self.node_list[1],
                    name_list=["booth"],
                ),
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_list[0],
                    reason=self.reason,
                    command="remote/booth_set_config",
                ),
            ]
        )

    def test_node_offline(self):
        self.fixture_config_read_success()
        self.config.http.booth.send_config(
            "booth",
            self.fixture_cfg_content().decode("utf-8"),
            authfile=os.path.basename(self.fixture_key_path()),
            authfile_data=RANDOM_KEY,
            communication_list=[
                dict(
                    label=self.node_list[0],
                    errno=1,
                    error_msg=self.reason,
                    was_connected=False,
                ),
                dict(
                    label=self.node_list[1],
                ),
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=self.node_list[1],
                    name_list=["booth"],
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.node_list[0],
                    reason=self.reason,
                    command="remote/booth_set_config",
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                ),
            ]
        )

    def test_node_offline_skip_offline(self):
        self.fixture_config_read_success()
        self.config.http.booth.send_config(
            "booth",
            self.fixture_cfg_content().decode("utf-8"),
            authfile=os.path.basename(self.fixture_key_path()),
            authfile_data=RANDOM_KEY,
            communication_list=[
                dict(
                    label=self.node_list[0],
                    errno=1,
                    error_msg=self.reason,
                    was_connected=False,
                ),
                dict(
                    label=self.node_list[1],
                ),
            ],
        )

        commands.config_sync(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=self.node_list[1],
                    name_list=["booth"],
                ),
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.node_list[0],
                    reason=self.reason,
                    command="remote/booth_set_config",
                ),
            ]
        )

    def test_config_not_accessible(self):
        self.config.corosync_conf.load().raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            exception_msg=self.reason,
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.fixture_cfg_path(),
                    reason=self.reason,
                    operation=RawFileError.ACTION_READ,
                )
            ]
        )

    def test_config_not_accessible_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": None,
                "key_data": None,
                "key_path": "some key path",
            }
        )
        (self.config.corosync_conf.load())
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path="",
                    reason="No such file or directory",
                    operation=RawFileError.ACTION_READ,
                )
            ]
        )

    def test_config_parse_error(self):
        self.config.corosync_conf.load().raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content="invalid config".encode("utf-8"),
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    line_list=["invalid config"],
                    file_path=self.fixture_cfg_path(),
                ),
            ]
        )

    def test_config_parse_error_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": "invalid config".encode("utf-8"),
                "key_data": None,
                "key_path": "some key path",
            }
        )
        self.config.corosync_conf.load()
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    line_list=["invalid config"],
                    file_path=None,
                ),
            ]
        )

    def test_authfile_not_accessible(self):
        self.config.corosync_conf.load()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=self.fixture_cfg_content(),
            name="raw_file.read.conf",
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_KEY,
            self.fixture_key_path(),
            exception_msg=self.reason,
            name="raw_file.read.key",
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=self.fixture_key_path(),
                    reason=self.reason,
                    operation=RawFileError.ACTION_READ,
                )
            ]
        )

    def test_authfile_not_accessible_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": self.fixture_cfg_content(),
                "key_data": None,
                "key_path": "some key path",
            }
        )
        self.config.corosync_conf.load()
        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path="",
                    reason="No such file or directory",
                    operation=RawFileError.ACTION_READ,
                )
            ]
        )

    def test_no_authfile(self):
        self.config.corosync_conf.load()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=bytes(),
        )
        self.config.http.booth.send_config(
            "booth",
            bytes().decode("utf-8"),
            node_labels=self.node_list,
        )
        commands.config_sync(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
            ]
            + [
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=["booth"],
                )
                for node in self.node_list
            ]
        )

    def test_authfile_not_in_booth_dir(self):
        config_content = "authfile=/etc/my_booth.key"
        self.config.corosync_conf.load()
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(),
            content=config_content.encode("utf-8"),
        )
        self.config.http.booth.send_config(
            "booth", config_content, node_labels=self.node_list
        )
        commands.config_sync(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.BOOTH_UNSUPPORTED_FILE_LOCATION,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path="/etc/my_booth.key",
                    expected_dir=settings.booth_config_dir,
                ),
                fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
            ]
            + [
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=["booth"],
                )
                for node in self.node_list
            ]
        )


class EnableDisableStartStopMixin(FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: self.command(
                self.env_assist.get_env(), instance_name=instance_name
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def test_not_systemd(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.command(self.env_assist.get_env(is_systemd=False)),
            [
                fixture.error(
                    reports.codes.UNSUPPORTED_OPERATION_ON_NON_SYSTEMD_SYSTEMS,
                ),
            ],
            expected_in_processor=False,
        )

    def test_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": "some config data",
                "key_data": "some key data",
                "key_path": "some key path",
            }
        )
        self.config.env.set_cib_data("<cib/>")
        self.env_assist.assert_raise_library_error(
            lambda: self.command(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                        file_type_codes.CIB,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def test_success_default_instance(self):
        self.get_external_call()("booth", instance="booth")
        self.command(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=self.report_service_action,
                    service="booth",
                    node="",
                    instance="booth",
                ),
            ]
        )

    def test_success_custom_instance(self):
        instance_name = "my_booth"
        self.get_external_call()("booth", instance="my_booth")
        self.command(self.env_assist.get_env(), instance_name=instance_name)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=self.report_service_action,
                    service="booth",
                    node="",
                    instance="my_booth",
                ),
            ]
        )

    def test_fail(self):
        err_msg = "some stderr\nsome stdout"
        self.get_external_call()("booth", instance="booth", failure_msg=err_msg)
        self.env_assist.assert_raise_library_error(
            lambda: self.command(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.SERVICE_ACTION_FAILED,
                    action=self.report_service_action,
                    service="booth",
                    reason=err_msg,
                    node="",
                    instance="booth",
                ),
            ],
            expected_in_processor=False,
        )


class Enable(EnableDisableStartStopMixin, TestCase):
    # without 'staticmethod' the command would bVecome a method of this class
    command = staticmethod(commands.enable_booth)
    report_service_action = reports.const.SERVICE_ACTION_ENABLE

    def get_external_call(self):
        return self.config.services.enable


class Disable(EnableDisableStartStopMixin, TestCase):
    # without 'staticmethod' the command would bVecome a method of this class
    command = staticmethod(commands.disable_booth)
    report_service_action = reports.const.SERVICE_ACTION_DISABLE

    def get_external_call(self):
        return self.config.services.disable


class Start(EnableDisableStartStopMixin, TestCase):
    # without 'staticmethod' the command would bVecome a method of this class
    command = staticmethod(commands.start_booth)
    report_service_action = reports.const.SERVICE_ACTION_START

    def get_external_call(self):
        return self.config.services.start


class Stop(EnableDisableStartStopMixin, TestCase):
    # without 'staticmethod' the command would bVecome a method of this class
    command = staticmethod(commands.stop_booth)
    report_service_action = reports.const.SERVICE_ACTION_STOP

    def get_external_call(self):
        return self.config.services.stop


class PullConfigBase(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.name = "booth"
        self.config_data = "config".encode("utf-8")
        self.config_path = self.fixture_cfg_path(self.name)
        self.node_name = "node"
        self.report_list = [
            fixture.info(
                reports.codes.BOOTH_FETCHING_CONFIG_FROM_NODE,
                node=self.node_name,
                config=self.name,
            ),
            fixture.info(
                reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                node="",
                name_list=[self.name],
            ),
        ]


class PullConfigSuccess(PullConfigBase):
    def setUp(self):
        super().setUp()
        self.config.http.booth.get_config(
            self.name,
            self.config_data.decode("utf-8"),
            node_labels=[self.node_name],
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            self.config_data,
            can_overwrite=True,
        )

    def test_success(self):
        commands.pull_config(self.env_assist.get_env(), self.node_name)
        self.env_assist.assert_reports(self.report_list)


class PullConfigSuccessCustomInstance(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.name = "my_booth"
        self.config_data = "config".encode("utf-8")
        self.config_path = self.fixture_cfg_path(self.name)
        self.node_name = "node"
        self.report_list = [
            fixture.info(
                reports.codes.BOOTH_FETCHING_CONFIG_FROM_NODE,
                node=self.node_name,
                config=self.name,
            ),
            fixture.info(
                reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                node=None,
                name_list=[self.name],
            ),
        ]

    def test_success(self):
        self.config.http.booth.get_config(
            self.name,
            self.config_data.decode("utf-8"),
            node_labels=[self.node_name],
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            self.config_data,
            can_overwrite=True,
        )
        commands.pull_config(
            self.env_assist.get_env(),
            self.node_name,
            instance_name=self.name,
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.BOOTH_FETCHING_CONFIG_FROM_NODE,
                    node=self.node_name,
                    config=self.name,
                ),
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node="",
                    name_list=[self.name],
                ),
            ]
        )


class PullConfigFailure(PullConfigBase):
    reason = "reason"

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(),
                self.node_name,
                instance_name=instance_name,
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def test_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": "some config data",
                "key_data": "some key data",
                "key_path": "some key path",
            }
        )
        self.config.env.set_cib_data("<cib/>")
        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                        file_type_codes.CIB,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def _assert_write_failure(self, booth_dir_exists):
        self.config.http.booth.get_config(
            self.name,
            self.config_data.decode("utf-8"),
            node_labels=[self.node_name],
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            self.config_data,
            can_overwrite=True,
            exception_msg=self.reason,
        )
        self.config.fs.exists(self.booth_dir, booth_dir_exists)

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
        )

    def test_write_failure(self):
        self._assert_write_failure(True)
        self.env_assist.assert_reports(
            self.report_list[:1]
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.config_path,
                    reason=self.reason,
                    operation=RawFileError.ACTION_WRITE,
                )
            ]
        )

    def test_write_failure_booth_dir_missing(self):
        self._assert_write_failure(False)
        self.env_assist.assert_reports(
            self.report_list[:1]
            + [
                fixture.error(
                    reports.codes.BOOTH_PATH_NOT_EXISTS,
                    path=self.booth_dir,
                ),
            ]
        )

    def test_network_failure(self):
        self.config.http.booth.get_config(
            self.name,
            communication_list=[
                dict(
                    label=self.node_name,
                    was_connected=False,
                    errno=1,
                    error_msg=self.reason,
                )
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                self.report_list[0],
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=None,
                    node=self.node_name,
                    command="remote/booth_get_config",
                    reason=self.reason,
                ),
            ]
        )

    def test_network_request_failure(self):
        self.config.http.booth.get_config(
            self.name,
            communication_list=[
                dict(
                    label=self.node_name,
                    response_code=400,
                    output=self.reason,
                )
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                self.report_list[0],
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    force_code=None,
                    node=self.node_name,
                    command="remote/booth_get_config",
                    reason=self.reason,
                ),
            ]
        )

    def test_request_response_not_json(self):
        self.config.http.booth.get_config(
            self.name,
            communication_list=[
                dict(
                    label=self.node_name,
                    output="not json",
                )
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                self.report_list[0],
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=self.node_name,
                ),
            ]
        )

    def test_request_response_missing_keys(self):
        self.config.http.booth.get_config(
            self.name,
            communication_list=[
                dict(
                    label=self.node_name,
                    output="{'config':{}}",
                )
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                self.report_list[0],
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=self.node_name,
                ),
            ]
        )


class PullConfigWithAuthfile(PullConfigBase):
    def setUp(self):
        super().setUp()
        self.authfile_path = self.fixture_key_path()
        self.authfile = os.path.basename(self.authfile_path)
        self.authfile_data = b"auth"

        self.config.http.booth.get_config(
            self.name,
            self.config_data.decode("utf-8"),
            authfile=self.authfile,
            authfile_data=self.authfile_data,
            node_labels=[self.node_name],
        )


class PullConfigWithAuthfileSuccess(PullConfigWithAuthfile):
    def setUp(self):
        super().setUp()
        self.config.raw_file.write(
            file_type_codes.BOOTH_KEY,
            self.authfile_path,
            self.authfile_data,
            can_overwrite=True,
            name="raw_file.write.key",
        )
        self.config.raw_file.write(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            self.config_data,
            can_overwrite=True,
            name="raw_file.write.cfg",
        )

    def test_success(self):
        commands.pull_config(self.env_assist.get_env(), self.node_name)
        self.env_assist.assert_reports(self.report_list)


class PullConfigWithAuthfileFailure(PullConfigWithAuthfile):
    def setUp(self):
        super().setUp()
        self.reason = "reason"

    def _assert_authfile_write_failure(self, booth_dir_exists):
        self.config.raw_file.write(
            file_type_codes.BOOTH_KEY,
            self.authfile_path,
            self.authfile_data,
            can_overwrite=True,
            exception_msg=self.reason,
        )
        self.config.fs.exists(self.booth_dir, booth_dir_exists)

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
        )

    def test_authfile_write_failure(self):
        self._assert_authfile_write_failure(True)
        self.env_assist.assert_reports(
            self.report_list[:1]
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=self.authfile_path,
                    reason=self.reason,
                    operation=RawFileError.ACTION_WRITE,
                )
            ]
        )

    def test_authfile_write_failure_booth_dir_missing(self):
        self._assert_authfile_write_failure(False)
        self.env_assist.assert_reports(
            self.report_list[:1]
            + [
                fixture.error(
                    reports.codes.BOOTH_PATH_NOT_EXISTS,
                    path=self.booth_dir,
                ),
            ]
        )


class GetStatus(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        mock_check_patcher = mock.patch(
            "pcs.lib.booth.status.check_authfile_misconfiguration"
        )
        self.mock_check = mock_check_patcher.start()
        self.mock_check.return_value = None
        self.addCleanup(mock_check_patcher.stop)

    def test_invalid_instance(self):
        instance_name = "/tmp/booth/booth"
        self.env_assist.assert_raise_library_error(
            lambda: commands.get_status(
                self.env_assist.get_env(), instance_name=instance_name
            ),
            [
                fixture_report_invalid_name(instance_name),
            ],
            expected_in_processor=False,
        )

    def test_not_live(self):
        self.config.env.set_booth(
            {
                "config_data": "some config data",
                "key_data": "some key data",
                "key_path": "some key path",
            }
        )
        self.config.env.set_cib_data("<cib/>")
        self.env_assist.assert_raise_library_error(
            lambda: commands.get_status(
                self.env_assist.get_env(),
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.BOOTH_CONFIG,
                        file_type_codes.BOOTH_KEY,
                        file_type_codes.CIB,
                    ],
                ),
            ],
            expected_in_processor=False,
        )

    def assert_success(self, instance_name=None):
        inner_name = instance_name or "booth"
        self.config.runner.booth.status_daemon(
            inner_name, stdout="daemon status"
        )
        self.config.runner.booth.status_tickets(
            inner_name, stdout="tickets status"
        )
        self.config.runner.booth.status_peers(inner_name, stdout="peers status")
        self.assertEqual(
            commands.get_status(
                self.env_assist.get_env(), instance_name=instance_name
            ),
            {
                "status": "daemon status",
                "ticket": "tickets status",
                "peers": "peers status",
            },
        )

    def test_success_default_instance(self):
        self.assert_success()

    def test_success_custom_instance(self):
        self.assert_success("custom instance name")

    def test_daemon_status_failure(self):
        self.config.runner.booth.status_daemon(
            "booth", stdout="some output", stderr="some error", returncode=1
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.get_status(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.BOOTH_DAEMON_STATUS_ERROR,
                    reason="some error\nsome output",
                ),
            ],
            expected_in_processor=False,
        )

    def test_ticket_status_failure(self):
        self.config.runner.booth.status_daemon("booth", stdout="daemon status")
        self.config.runner.booth.status_tickets(
            "booth", stdout="some output", stderr="some error", returncode=1
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.get_status(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.BOOTH_TICKET_STATUS_ERROR,
                    reason="some error\nsome output",
                ),
            ],
            expected_in_processor=False,
        )

    def test_peers_status_failure(self):
        self.config.runner.booth.status_daemon("booth", stdout="daemon status")
        self.config.runner.booth.status_tickets(
            "booth", stdout="tickets status"
        )
        self.config.runner.booth.status_peers(
            "booth", stdout="some output", stderr="some error", returncode=1
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.get_status(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.BOOTH_PEERS_STATUS_ERROR,
                    reason="some error\nsome output",
                ),
            ],
            expected_in_processor=False,
        )


@mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
@mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", True)
class GetStatusWarnings(TestCase, FixtureMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.instance_name = "instance name"

    def assert_success(self):
        self.config.runner.booth.status_daemon(
            self.instance_name, stdout="daemon status"
        )
        self.config.runner.booth.status_tickets(
            self.instance_name, stdout="tickets status"
        )
        self.config.runner.booth.status_peers(
            self.instance_name, stdout="peers status"
        )
        self.assertEqual(
            commands.get_status(
                self.env_assist.get_env(), instance_name=self.instance_name
            ),
            {
                "status": "daemon status",
                "ticket": "tickets status",
                "peers": "peers status",
            },
        )

    def test_warning(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(self.instance_name),
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(self.instance_name),
            content=f"authfile = file\n{constants.AUTHFILE_FIX_OPTION} = no".encode(),
        )
        self.assert_success()
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.BOOTH_AUTHFILE_NOT_USED,
                    instance=self.instance_name,
                )
            ]
        )

    def test_read_file_failure(self):
        config = "invalid file ' format"
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(self.instance_name),
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.fixture_cfg_path(self.instance_name),
            content=config.encode(),
        )
        self.assert_success()
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    line_list=[config],
                    file_path=self.fixture_cfg_path(self.instance_name),
                )
            ]
        )

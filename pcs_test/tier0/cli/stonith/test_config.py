import json
from textwrap import dedent
from unittest import TestCase, mock

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.stonith import command
from pcs.common.interface import dto
from pcs.common.pacemaker.cibsecret import (
    CibResourceSecretDto,
    CibResourceSecretListDto,
)
from pcs.common.pacemaker.fencing_topology import (
    CibFencingTopologyDto,
)
from pcs.common.pacemaker.resource.list import CibResourcesDto

from pcs_test.tools.misc import dict_to_modifiers
from pcs_test.tools.resources_dto import PRIMITIVE_R8, STONITH_S1, STONITH_S3


@mock.patch("pcs.cli.stonith.command.print")
class StonithConfig(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource", "fencing_topology"])
        self.lib.resource = mock.Mock(
            spec_set=["get_configured_resources", "get_cibsecrets"]
        )
        self.lib.resource.get_configured_resources.return_value = (
            CibResourcesDto(
                primitives=[PRIMITIVE_R8, STONITH_S1, STONITH_S3],
                clones=[],
                groups=[],
                bundles=[],
            )
        )
        self.lib.fencing_topology = mock.Mock(spec_set=["get_config_dto"])
        self.lib.fencing_topology.get_config_dto.return_value = (
            CibFencingTopologyDto(
                target_node=[], target_regex=[], target_attribute=[]
            )
        )

    def _call_cmd(self, argv, modifiers=None):
        command.config(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def test_no_args_no_resources(self, mock_print):
        self.lib.resource.get_configured_resources.return_value = (
            CibResourcesDto(primitives=[], clones=[], groups=[], bundles=[])
        )
        self._call_cmd([])
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        self.lib.fencing_topology.get_config_dto.assert_called_once_with()
        mock_print.assert_not_called()

    def _test_show_secrets_with_unsupported_format_error(
        self, mock_print, output_format
    ):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(
                [], {"show-secrets": True, "output-format": output_format}
            )
        self.assertEqual(
            cm.exception.message,
            (
                "using '--show-secrets' is supported only with "
                "--output-format=text"
            ),
        )
        self.lib.resource.get_configured_resources.assert_not_called()
        self.lib.resource.get_cibsecrets.assert_not_called()
        self.lib.fencing_topology.get_config_dto.assert_not_called()
        mock_print.assert_not_called()

    def test_show_secrets_with_cmd_format_error(self, mock_print):
        self._test_show_secrets_with_unsupported_format_error(mock_print, "cmd")

    def test_show_secrets_with_json_format_error(self, mock_print):
        self._test_show_secrets_with_unsupported_format_error(
            mock_print, "json"
        )

    def test_unsupported_option(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"wait": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--wait' is not supported in this command",
        )
        self.lib.resource.get_configured_resources.assert_not_called()
        self.lib.resource.get_cibsecrets.assert_not_called()
        self.lib.fencing_topology.get_config_dto.assert_not_called()
        mock_print.assert_not_called()

    def test_output_format_default_text(self, mock_print):
        self._call_cmd([], {"output-format": "text"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        self.lib.fencing_topology.get_config_dto.assert_called_once_with()
        mock_print.assert_called_once_with(
            dedent(
                """\
                Resource: S1 (class=stonith type=fence_pcsmock_params)
                  Attributes: S1-instance_attributes
                    action=reboot
                    ip=203.0.113.1
                    username=testuser
                  Operations:
                    monitor: S1-monitor-interval-60s
                      interval=60s
                Resource: S3 (class=stonith type=fence_pcsmock_minimal)
                  Attributes: S3-instance_attributes
                    ip=hostname.host
                    Secret Attributes:
                      password
                      username
                  Operations:
                    monitor: S3-monitor-interval-60s
                      interval=60s"""
            )
        )

    def test_output_format_text_with_resource_id(self, mock_print):
        self._call_cmd(["S3"], {"output-format": "text"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        self.lib.fencing_topology.get_config_dto.assert_called_once_with()
        mock_print.assert_called_once_with(
            dedent(
                """\
                Resource: S3 (class=stonith type=fence_pcsmock_minimal)
                  Attributes: S3-instance_attributes
                    ip=hostname.host
                    Secret Attributes:
                      password
                      username
                  Operations:
                    monitor: S3-monitor-interval-60s
                      interval=60s"""
            )
        )

    def test_output_format_cmd(self, mock_print):
        self._call_cmd([], {"output-format": "cmd"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        self.lib.fencing_topology.get_config_dto.assert_called_once_with()
        mock_print.assert_called_once_with(
            dedent(
                """\
                pcs stonith create --no-default-ops --force -- S1 fence_pcsmock_params \\
                  action=reboot ip=203.0.113.1 username=testuser \\
                  op \\
                    monitor interval=60s id=S1-monitor-interval-60s;
                pcs stonith create --no-default-ops --force -- S3 fence_pcsmock_minimal \\
                  ip=hostname.host password=lrm:// username=lrm:// \\
                  op \\
                    monitor interval=60s id=S3-monitor-interval-60s"""
            )
        )

    @mock.patch("pcs.cli.stonith.command.warn")
    def test_output_format_json(self, mock_warn, mock_print):
        self._call_cmd(["S3"], {"output-format": "json"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        self.lib.fencing_topology.get_config_dto.assert_not_called()
        mock_warn.assert_called_once_with(
            "Fencing levels are not included because this command could only "
            "export stonith configuration previously. This cannot be changed "
            "to avoid breaking existing tooling. To export fencing levels, run "
            "'pcs stonith level config --output-format=json'"
        )
        mock_print.assert_called_once_with(
            json.dumps(
                dto.to_dict(
                    CibResourcesDto(
                        primitives=[STONITH_S3],
                        clones=[],
                        groups=[],
                        bundles=[],
                    )
                )
            )
        )

    def test_show_secrets_with_text_format(self, mock_print):
        self.lib.resource.get_cibsecrets.return_value = (
            CibResourceSecretListDto(
                resource_secrets=[
                    CibResourceSecretDto(
                        resource_id="S3",
                        name="password",
                        value="secret_password",
                    ),
                    CibResourceSecretDto(
                        resource_id="S3",
                        name="username",
                        value="secret_user",
                    ),
                ]
            )
        )
        self._call_cmd(["S3"], {"show-secrets": True, "output-format": "text"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_called_once_with(
            [("S3", "password"), ("S3", "username")]
        )
        self.lib.fencing_topology.get_config_dto.assert_called_once_with()
        mock_print.assert_called_once_with(
            dedent(
                """\
                Resource: S3 (class=stonith type=fence_pcsmock_minimal)
                  Attributes: S3-instance_attributes
                    ip=hostname.host
                    Secret Attributes:
                      password=secret_password
                      username=secret_user
                  Operations:
                    monitor: S3-monitor-interval-60s
                      interval=60s"""
            )
        )

    @mock.patch("pcs.cli.resource.output.warn")
    def test_empty_resource_list_filtered(self, mock_warn, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["non_existent_resource"])
        self.assertEqual(cm.exception.message, "No stonith device found")
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        self.lib.fencing_topology.get_config_dto.assert_not_called()
        mock_warn.assert_called_once_with(
            "Unable to find stonith device 'non_existent_resource'"
        )
        mock_print.assert_not_called()

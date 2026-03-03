import json
from textwrap import dedent
from unittest import TestCase, mock

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.resource import command
from pcs.common.interface import dto
from pcs.common.pacemaker.cibsecret import (
    CibResourceSecretDto,
    CibResourceSecretListDto,
)
from pcs.common.pacemaker.resource.list import CibResourcesDto

from pcs_test.tools.misc import dict_to_modifiers
from pcs_test.tools.resources_dto import PRIMITIVE_R1, PRIMITIVE_R8, STONITH_S3


@mock.patch("pcs.cli.resource.command.print")
class ResourceConfig(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.lib.resource = mock.Mock(
            spec_set=["get_configured_resources", "get_cibsecrets"]
        )
        self.lib.resource.get_configured_resources.return_value = (
            CibResourcesDto(
                primitives=[PRIMITIVE_R1, PRIMITIVE_R8, STONITH_S3],
                clones=[],
                groups=[],
                bundles=[],
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
        mock_print.assert_not_called()

    def test_output_format_default_text(self, mock_print):
        self._call_cmd([], {"output-format": "text"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        mock_print.assert_called_once_with(
            dedent(
                """\
                Resource: R1 (class=ocf provider=pcsmock type=minimal)
                  Description: R1 description
                  Operations:
                    monitor: R1-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: R8 (class=ocf provider=pcsmock type=minimal)
                  Attributes: R8-instance_attributes
                    fake=fake_value
                    Secret Attributes:
                      secret1
                  Operations:
                    monitor: R8-monitor-interval-10s
                      interval=10s timeout=20s"""
            )
        )

    def test_output_format_text_with_resource_id(self, mock_print):
        self._call_cmd(["R8"], {"output-format": "text"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        mock_print.assert_called_once_with(
            dedent(
                """\
                Resource: R8 (class=ocf provider=pcsmock type=minimal)
                  Attributes: R8-instance_attributes
                    fake=fake_value
                    Secret Attributes:
                      secret1
                  Operations:
                    monitor: R8-monitor-interval-10s
                      interval=10s timeout=20s"""
            )
        )

    def test_output_format_cmd(self, mock_print):
        self._call_cmd([], {"output-format": "cmd"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        mock_print.assert_called_once_with(
            dedent(
                """\
                pcs resource create --no-default-ops --force -- R1 ocf:pcsmock:minimal \\
                  op \\
                    monitor interval=10s id=R1-monitor-interval-10s timeout=20s;
                pcs cib element description R1 'R1 description';
                pcs resource create --no-default-ops --force -- R8 ocf:pcsmock:minimal \\
                  fake=fake_value secret1=lrm:// \\
                  op \\
                    monitor interval=10s id=R8-monitor-interval-10s timeout=20s"""
            )
        )

    def test_output_format_json(self, mock_print):
        self._call_cmd(["R8"], {"output-format": "json"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        mock_print.assert_called_once_with(
            json.dumps(
                dto.to_dict(
                    CibResourcesDto(
                        primitives=[PRIMITIVE_R8],
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
                        resource_id="R8",
                        name="secret1",
                        value="secret1_value",
                    )
                ]
            )
        )
        self._call_cmd(["R8"], {"show-secrets": True, "output-format": "text"})
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_called_once_with(
            [("R8", "secret1")]
        )
        mock_print.assert_called_once_with(
            dedent(
                """\
                Resource: R8 (class=ocf provider=pcsmock type=minimal)
                  Attributes: R8-instance_attributes
                    fake=fake_value
                    Secret Attributes:
                      secret1=secret1_value
                  Operations:
                    monitor: R8-monitor-interval-10s
                      interval=10s timeout=20s"""
            )
        )

    @mock.patch("pcs.cli.resource.output.warn")
    def test_empty_resource_list_filtered(self, mock_warn, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["non_existent_resource"])
        self.assertEqual(cm.exception.message, "No resource found")
        self.lib.resource.get_configured_resources.assert_called_once_with()
        self.lib.resource.get_cibsecrets.assert_not_called()
        mock_warn.assert_called_once_with(
            "Unable to find resource 'non_existent_resource'"
        )
        mock_print.assert_not_called()

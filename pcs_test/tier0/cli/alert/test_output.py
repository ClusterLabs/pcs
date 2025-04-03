from unittest import TestCase, mock

from pcs.cli.alert.command import alert_config
from pcs.cli.common.errors import CmdLineInputError
from pcs.common.pacemaker.alert import (
    CibAlertDto,
    CibAlertListDto,
    CibAlertRecipientDto,
    CibAlertSelectAttributeDto,
    CibAlertSelectDto,
)
from pcs.common.pacemaker.nvset import CibNvpairDto, CibNvsetDto

from pcs_test.tools.misc import dict_to_modifiers

# The fixtures are almost the same as in tier1.test_alert and they should be
# unified and deduplicated eventually. Currently, it is not possible, because
# the tier0 test tests select, which is not supported by code tested in tier1
# test.
FIXTURE_ALERTS_DTO = CibAlertListDto(
    [
        CibAlertDto(
            id="alert1",
            path="/path/1",
            description=None,
            recipients=[],
            select=None,
            meta_attributes=[],
            instance_attributes=[],
        ),
        CibAlertDto(
            id="alert2",
            path="/path/2",
            description=None,
            recipients=[
                CibAlertRecipientDto(
                    id="alert2-recipient1",
                    value="test_value_1",
                    description=None,
                    meta_attributes=[],
                    instance_attributes=[],
                ),
                CibAlertRecipientDto(
                    id="alert2-recipient2",
                    value="test_value_2",
                    description="alert2 recipient2 description",
                    meta_attributes=[],
                    instance_attributes=[],
                ),
            ],
            select=None,
            meta_attributes=[],
            instance_attributes=[],
        ),
        CibAlertDto(
            id="alert-all",
            path="/path/all",
            description="alert all options",
            recipients=[
                CibAlertRecipientDto(
                    id="alert-all-recipient",
                    value="value-all",
                    description="all options recipient",
                    meta_attributes=[
                        CibNvsetDto(
                            id="aar1m",
                            options={},
                            rule=None,
                            nvpairs=[
                                CibNvpairDto(
                                    id="aar1m1", name="aar1m1n", value="aar1m1v"
                                ),
                                CibNvpairDto(
                                    id="aar1m2", name="aar1m2n", value="aar1m2v"
                                ),
                            ],
                        )
                    ],
                    instance_attributes=[
                        CibNvsetDto(
                            id="aar1i",
                            options={},
                            rule=None,
                            nvpairs=[
                                CibNvpairDto(
                                    id="aar1i1", name="aar1i1n", value="aar1i1v"
                                ),
                                CibNvpairDto(
                                    id="aar1i2", name="aar1i2n", value="aar1i2v"
                                ),
                            ],
                        )
                    ],
                )
            ],
            select=CibAlertSelectDto(
                nodes=True,
                fencing=False,
                resources=False,
                attributes=True,
                attributes_select=[
                    CibAlertSelectAttributeDto(id="attr1", name="standby"),
                    CibAlertSelectAttributeDto(id="attr2", name="shutdown"),
                ],
            ),
            meta_attributes=[
                CibNvsetDto(
                    id="aam1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="aam1", name="aam1n", value="aam1v"),
                        CibNvpairDto(id="aam2", name="aam2n", value="aam2v"),
                    ],
                )
            ],
            instance_attributes=[
                CibNvsetDto(
                    id="aai1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="aai1", name="aai1n", value="aai1v"),
                        CibNvpairDto(id="aai2", name="aai2n", value="aai2v"),
                    ],
                )
            ],
        ),
    ]
)

FIXTURE_ALERTS_TEXT = """\
Alert: alert1
  Path: /path/1
Alert: alert2
  Path: /path/2
  Recipients:
    Recipient: alert2-recipient1
      Value: test_value_1
    Recipient: alert2-recipient2
      Description: alert2 recipient2 description
      Value: test_value_2
Alert: alert-all
  Description: alert all options
  Path: /path/all
  Recipients:
    Recipient: alert-all-recipient
      Description: all options recipient
      Value: value-all
      Attributes: aar1i
        aar1i1n=aar1i1v
        aar1i2n=aar1i2v
      Meta Attributes: aar1m
        aar1m1n=aar1m1v
        aar1m2n=aar1m2v
  Receives:
    nodes
    attributes: 'shutdown', 'standby'
  Attributes: aai1
    aai1n=aai1v
    aai2n=aai2v
  Meta Attributes: aam1
    aam1n=aam1v
    aam2n=aam2v\
"""

FIXTURE_ALERTS_CMD = """\
pcs -- alert create path=/path/1 id=alert1;
pcs -- alert create path=/path/2 id=alert2;
pcs -- alert recipient add alert2 value=test_value_1 id=alert2-recipient1;
pcs -- alert recipient add alert2 value=test_value_2 id=alert2-recipient2 description='alert2 recipient2 description';
pcs -- alert create path=/path/all id=alert-all description='alert all options' options aai1n=aai1v aai2n=aai2v meta aam1n=aam1v aam2n=aam2v;
pcs -- alert recipient add alert-all value=value-all id=alert-all-recipient description='all options recipient' options aar1i1n=aar1i1v aar1i2n=aar1i2v meta aar1m1n=aar1m1v aar1m2n=aar1m2v\
"""


class AlertsConfigBaseMixin:
    def setUp(self):
        self.lib = mock.Mock(spec_set=["alert"])
        self.lib.alert = mock.Mock(spec_set=["get_config_dto"])
        self.lib_cmd = self.lib.alert.get_config_dto

    def _call_cmd(self, argv, modifiers=None):
        modifiers = modifiers or {}
        alert_config(self.lib, argv, dict_to_modifiers(modifiers))

    def test_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["arg"])
        self.assertIsNone(cm.exception.message)
        self.lib_cmd.assert_not_called()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.alert.command.print")
class AlertsConfigText(AlertsConfigBaseMixin, TestCase):
    def test_empty(self, mock_print):
        self.lib_cmd.return_value = CibAlertListDto([])
        self._call_cmd([])
        mock_print.assert_not_called()

    def test_complex(self, mock_print):
        self.lib_cmd.return_value = FIXTURE_ALERTS_DTO
        self._call_cmd([])
        mock_print.assert_called_once_with(FIXTURE_ALERTS_TEXT)


@mock.patch("pcs.cli.alert.command.print")
class AlertsConfigCmd(AlertsConfigBaseMixin, TestCase):
    def _call_cmd(self, argv, modifiers=None):
        modifiers = modifiers or {}
        modifiers["output-format"] = "cmd"
        return super()._call_cmd(argv, modifiers)

    def test_empty(self, mock_print):
        self.lib_cmd.return_value = CibAlertListDto([])
        self._call_cmd([])
        mock_print.assert_not_called()

    def test_complex(self, mock_print):
        self.lib_cmd.return_value = FIXTURE_ALERTS_DTO
        self._call_cmd([])
        mock_print.assert_called_once_with(FIXTURE_ALERTS_CMD)

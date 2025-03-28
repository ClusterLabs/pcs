import json
import shlex
from unittest import TestCase

from pcs.common.interface import dto
from pcs.common.pacemaker.alert import (
    CibAlertDto,
    CibAlertListDto,
    CibAlertRecipientDto,
)
from pcs.common.pacemaker.nvset import CibNvpairDto, CibNvsetDto

from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

# The fixtures are almost the same as in tier0.cli.alert.test_output and they
# should be unified and deduplicated eventually. Currently, it is not possible,
# because the tier0 test tests select, which is not supported by code tested in
# tier1 test.
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
                            id="alert-all-recipient-meta_attributes",
                            options={},
                            rule=None,
                            nvpairs=[
                                CibNvpairDto(
                                    id="alert-all-recipient-meta_attributes-aar1m1n",
                                    name="aar1m1n",
                                    value="aar1m1v",
                                ),
                                CibNvpairDto(
                                    id="alert-all-recipient-meta_attributes-aar1m2n",
                                    name="aar1m2n",
                                    value="aar1m2v",
                                ),
                            ],
                        )
                    ],
                    instance_attributes=[
                        CibNvsetDto(
                            id="alert-all-recipient-instance_attributes",
                            options={},
                            rule=None,
                            nvpairs=[
                                CibNvpairDto(
                                    id="alert-all-recipient-instance_attributes-aar1i1n",
                                    name="aar1i1n",
                                    value="aar1i1v",
                                ),
                                CibNvpairDto(
                                    id="alert-all-recipient-instance_attributes-aar1i2n",
                                    name="aar1i2n",
                                    value="aar1i2v",
                                ),
                            ],
                        )
                    ],
                )
            ],
            # eventually, select should not be None, once pcs starts to
            # actually support it in commands for creating alerts
            select=None,
            meta_attributes=[
                CibNvsetDto(
                    id="alert-all-meta_attributes",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(
                            id="alert-all-meta_attributes-aam1n",
                            name="aam1n",
                            value="aam1v",
                        ),
                        CibNvpairDto(
                            id="alert-all-meta_attributes-aam2n",
                            name="aam2n",
                            value="aam2v",
                        ),
                    ],
                )
            ],
            instance_attributes=[
                CibNvsetDto(
                    id="alert-all-instance_attributes",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(
                            id="alert-all-instance_attributes-aai1n",
                            name="aai1n",
                            value="aai1v",
                        ),
                        CibNvpairDto(
                            id="alert-all-instance_attributes-aai2n",
                            name="aai2n",
                            value="aai2v",
                        ),
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
      Attributes: alert-all-recipient-instance_attributes
        aar1i1n=aar1i1v
        aar1i2n=aar1i2v
      Meta Attributes: alert-all-recipient-meta_attributes
        aar1m1n=aar1m1v
        aar1m2n=aar1m2v
  Attributes: alert-all-instance_attributes
    aai1n=aai1v
    aai2n=aai2v
  Meta Attributes: alert-all-meta_attributes
    aam1n=aam1v
    aam2n=aam2v
"""

FIXTURE_ALERTS_CMD = """\
pcs -- alert create path=/path/1 id=alert1;
pcs -- alert create path=/path/2 id=alert2;
pcs -- alert recipient add alert2 value=test_value_1 id=alert2-recipient1;
pcs -- alert recipient add alert2 value=test_value_2 id=alert2-recipient2 description='alert2 recipient2 description';
pcs -- alert create path=/path/all id=alert-all description='alert all options' options aai1n=aai1v aai2n=aai2v meta aam1n=aam1v aam2n=aam2v;
pcs -- alert recipient add alert-all value=value-all id=alert-all-recipient description='all options recipient' options aar1i1n=aar1i1v aar1i2n=aar1i2v meta aar1m1n=aar1m1v aar1m2n=aar1m2v\
"""


class AlertsConfigJson(TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_empty(self):
        pcs_runner = PcsRunner(cib_file=get_test_resource("cib-empty.xml"))
        stdout, stderr, retval = pcs_runner.run(
            ["alert", "config", "--output-format=json"]
        )
        expected = CibAlertListDto([])
        self.assertEqual(
            json.loads(stdout), json.loads(json.dumps(dto.to_dict(expected)))
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_success(self):
        pcs_runner = PcsRunner(cib_file=get_test_resource("cib-all.xml"))

        stdout, stderr, retval = pcs_runner.run(
            ["alert", "config", "--output-format=json"]
        )
        expected = FIXTURE_ALERTS_DTO
        self.assertEqual(
            json.loads(stdout), json.loads(json.dumps(dto.to_dict(expected)))
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)


class AlertsConfigCmd(TestCase):
    def setUp(self):
        self.old_cib = get_tmp_file("tier1_alert_cmd_old")
        write_file_to_tmpfile(get_test_resource("cib-all.xml"), self.old_cib)
        self.new_cib = get_tmp_file("tier1_alert_cmd_new")
        write_file_to_tmpfile(get_test_resource("cib-empty.xml"), self.new_cib)
        self.old_pcs_runner = PcsRunner(self.old_cib.name)
        self.new_pcs_runner = PcsRunner(self.new_cib.name)
        self.maxDiff = None

    def tearDown(self):
        self.old_cib.close()
        self.new_cib.close()

    def _get_as_json(self, runner):
        stdout, stderr, retval = runner.run(
            ["alert", "config", "--output-format=json"]
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def test_success(self):
        stdout, stderr, retval = self.old_pcs_runner.run(
            ["alert", "config", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        commands = [
            shlex.split(command)[1:]
            for command in stdout.replace("\\n", "").strip().split(";\n")
        ]

        for cmd in commands:
            stdout, stderr, retval = self.new_pcs_runner.run(cmd)
            self.assertEqual(
                retval,
                0,
                (
                    f"Command {cmd} exited with {retval}\nstdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                ),
            )
        self.assertEqual(
            self._get_as_json(self.new_pcs_runner),
            self._get_as_json(self.old_pcs_runner),
        )


class AlertsConfigText(TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_empty(self):
        pcs_runner = PcsRunner(cib_file=get_test_resource("cib-empty.xml"))
        stdout, stderr, retval = pcs_runner.run(
            ["alert", "config", "--output-format=text"]
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_success(self):
        pcs_runner = PcsRunner(cib_file=get_test_resource("cib-all.xml"))
        stdout, stderr, retval = pcs_runner.run(
            ["alert", "config", "--output-format=text"]
        )
        self.assertEqual(stdout, FIXTURE_ALERTS_TEXT)
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_success_no_config(self):
        pcs_runner = PcsRunner(cib_file=get_test_resource("cib-all.xml"))
        stdout, stderr, retval = pcs_runner.run(["alert"])
        self.assertEqual(stdout, FIXTURE_ALERTS_TEXT)
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

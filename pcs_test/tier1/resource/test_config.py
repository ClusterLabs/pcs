import json
from shlex import split
from textwrap import dedent
from unittest import TestCase

from pcs.common.interface.dto import to_dict
from pcs.common.pacemaker.resource.clone import CibResourceCloneDto
from pcs.common.pacemaker.resource.group import CibResourceGroupDto
from pcs.common.pacemaker.resource.list import CibResourcesDto

from pcs_test.tools import resources_dto
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class ResourceConfigJson(TestCase):
    def setUp(self):
        self.pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-all.xml"),
        )
        self.maxDiff = None

    def test_all(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["resource", "config", "--output-format=json"]
        )
        expected = CibResourcesDto(
            primitives=[
                resources_dto.PRIMITIVE_R1,
                resources_dto.PRIMITIVE_R7,
                resources_dto.PRIMITIVE_R5,
                resources_dto.PRIMITIVE_R2,
                resources_dto.PRIMITIVE_R3,
                resources_dto.PRIMITIVE_R4,
                resources_dto.PRIMITIVE_R6,
            ],
            clones=[
                resources_dto.CLONE_G1,
                resources_dto.CLONE_R6,
            ],
            groups=[
                resources_dto.GROUP_G2,
                resources_dto.GROUP_G1,
            ],
            bundles=[
                resources_dto.BUNDLE_B1,
                resources_dto.BUNDLE_B2,
            ],
        )
        self.assertEqual(json.loads(stdout), to_dict(expected))
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_get_multiple(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["resource", "config", "--output-format=json", "G1-clone", "R1"]
        )
        expected = CibResourcesDto(
            primitives=[
                resources_dto.PRIMITIVE_R1,
                resources_dto.PRIMITIVE_R2,
                resources_dto.PRIMITIVE_R3,
                resources_dto.PRIMITIVE_R4,
            ],
            clones=[resources_dto.CLONE_G1],
            groups=[resources_dto.GROUP_G1],
            bundles=[],
        )
        self.assertEqual(json.loads(stdout), to_dict(expected))
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)


class ResourceConfigCmdMixin:
    sub_command = None
    expected_json_config_stderr = ""

    def setUp(self):
        self.new_cib_file = get_tmp_file(self._get_tmp_file_name())
        self.pcs_runner_orig = PcsRunner(
            cib_file=get_test_resource("cib-all.xml")
        )
        self.pcs_runner_orig.mock_settings = get_mock_settings()
        self.pcs_runner_new = PcsRunner(cib_file=self.new_cib_file.name)
        self.pcs_runner_new.mock_settings = get_mock_settings()
        write_file_to_tmpfile(
            get_test_resource("cib-empty.xml"), self.new_cib_file
        )
        self.maxDiff = None

    def tearDown(self):
        self.new_cib_file.close()

    def _run_commands(self, stdout):
        cmds = [
            split(cmd)[1:]
            for cmd in stdout.replace("\\\n", "").strip().split(";\n")
        ]
        for cmd in cmds:
            stdout, stderr, retval = self.pcs_runner_new.run(cmd)
            self.assertEqual(
                retval,
                0,
                (
                    f"Command {cmd} exited with {retval}\nstdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                ),
            )

    def _get_as_json(self, runner):
        stdout, stderr, retval = runner.run(
            [self.sub_command, "config", "--output-format=json"]
        )
        self.assertEqual(stderr, self.expected_json_config_stderr)
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def test_all(self):
        stdout, stderr, retval = self.pcs_runner_orig.run(
            [self.sub_command, "config", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        self._run_commands(stdout)
        self.assertEqual(
            self._get_as_json(self.pcs_runner_new),
            self._get_as_json(self.pcs_runner_orig),
        )


class ResourceConfigCmd(ResourceConfigCmdMixin, TestCase):
    sub_command = "resource"

    @staticmethod
    def _get_tmp_file_name():
        return "tier1_resource_test_config_cib.xml"

    def test_unsupported_stonith(self):
        self.pcs_runner_orig = PcsRunner(
            cib_file=get_test_resource("cib-unsupported-stonith-config.xml")
        )
        stdout, stderr, retval = self.pcs_runner_orig.run(
            ["resource", "config", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        self.assertEqual(
            stderr,
            (
                "Warning: Bundle resource 'B1' contains stonith resource: 'S1',"
                " which is unsupported. The bundle resource will be omitted.\n"
                "Warning: Group 'G1' contains stonith resource: 'S2', which is "
                "unsupported. The group will be omitted.\n"
                "Warning: Group 'G2' contains stonith resources: 'S4', 'S5', "
                "which is unsupported. The group will be omitted.\n"
                "Warning: Group 'G3' contains stonith resources: 'S6', 'S7', "
                "which is unsupported. The stonith resources will be omitted.\n"
                "Warning: Group 'G4' contains stonith resource: 'S8', which is "
                "unsupported. The stonith resource will be omitted.\n"
                "Warning: Clone 'S3-clone' contains stonith resource: 'S3', "
                "which is unsupported. The clone will be omitted.\n"
                "Warning: Clone 'G2-clone' contains stonith resources: 'S4', "
                "'S5', which is unsupported. The clone will be omitted.\n"
            ),
        )
        self._run_commands(stdout)
        expected_dict = to_dict(
            CibResourcesDto(
                primitives=[
                    resources_dto.PRIMITIVE_R1,
                    resources_dto.PRIMITIVE_R2,
                    resources_dto.PRIMITIVE_R3,
                ],
                clones=[
                    CibResourceCloneDto(
                        id="G4-clone",
                        description=None,
                        member_id="G4",
                        meta_attributes=[],
                        instance_attributes=[],
                    )
                ],
                groups=[
                    CibResourceGroupDto(
                        id="G3",
                        description=None,
                        member_ids=["R2"],
                        meta_attributes=[],
                        instance_attributes=[],
                    ),
                    CibResourceGroupDto(
                        id="G4",
                        description=None,
                        member_ids=["R3"],
                        meta_attributes=[],
                        instance_attributes=[],
                    ),
                ],
                bundles=[],
            )
        )
        self.assertEqual(
            self._get_as_json(self.pcs_runner_new),
            expected_dict,
        )

    def test_plaintext(self):
        stdout, stderr, retval = self.pcs_runner_orig.run(
            [self.sub_command, "config"]
        )
        self.assertEqual(
            stdout,
            dedent(
                """\
                Resource: R7 (class=ocf provider=pcsmock type=minimal)
                  Description: R7 description is very long " & and special
                  Attributes: R7-instance_attributes
                    envfile=/dev/null
                    fake=looool
                  Meta Attributes: R7-meta_attributes
                    "another one0"="a + b = c"
                    anotherone=something'"special
                    m1=value1
                    m10=value1
                    meta2=valueofmeta2isthisverylongstring
                    meta20=valueofmeta2isthisverylongstring
                  Operations:
                    custom_action: R7-custom_action-interval-10s
                      interval=10s OCF_CHECK_LEVEL=2
                    migrate_from: R7-migrate_from-interval-0s
                      interval=0s timeout=20s
                    migrate_to: R7-migrate_to-interval-0s
                      interval=0s timeout=20s enabled=0 record-pending=0
                    monitor: R7-monitor-interval-10s
                      interval=10s timeout=20s
                    reload: R7-reload-interval-0s
                      interval=0s timeout=20s
                    reload-agent: R7-reload-agent-interval-0s
                      interval=0s timeout=20s
                    start: R7-start-interval-0s
                      interval=0s timeout=20s
                    stop: R7-stop-interval-0s
                      interval=0s timeout=20s
                Group: G2
                  Meta Attributes: G2-meta_attributes
                    meta1=metaval1
                    meta2=metaval2
                  Resource: R5 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: R5-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: G1-clone
                  Description: G1-clone description
                  Meta Attributes: G1-clone-meta_attributes
                    promotable=true
                  Group: G1
                    Description: G1 description
                    Resource: R2 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: R2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: R3 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: R3-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: R4 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: R4-monitor-interval-10s
                          interval=10s timeout=20s
                Clone: R6-clone
                  Resource: R6 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      migrate_from: R6-migrate_from-interval-0s
                        interval=0s timeout=20s
                      migrate_to: R6-migrate_to-interval-0s
                        interval=0s timeout=20s
                      monitor: R6-monitor-interval-10s
                        interval=10s timeout=20s
                      reload: R6-reload-interval-0s
                        interval=0s timeout=20s
                      reload-agent: R6-reload-agent-interval-0s
                        interval=0s timeout=20s
                      start: R6-start-interval-0s
                        interval=0s timeout=20s
                      stop: R6-stop-interval-0s
                        interval=0s timeout=20s
                Bundle: B1
                  Description: B1 description
                  Docker: image=pcs:test replicas=4 replicas-per-host=2 run-command=/bin/true network=extra_network_settings options=extra_options
                  Network: ip-range-start=192.168.100.200 control-port=12345 host-interface=eth0 host-netmask=24
                  Port Mapping:
                    port=1001 (B1-port-map-1001)
                    port=2000 internal-port=2002 (B1-port-map-2000)
                    range=3000-3300 (B1-port-map-3000-3300)
                  Storage Mapping:
                    source-dir=/tmp/docker1a target-dir=/tmp/docker1b (B1-storage-map)
                    source-dir=/tmp/docker2a target-dir=/tmp/docker2b (B1-storage-map-1)
                    source-dir-root=/tmp/docker3a target-dir=/tmp/docker3b (B1-storage-map-2)
                    source-dir-root=/tmp/docker4a target-dir=/tmp/docker4b (B1-storage-map-3)
                  Meta Attributes: B1-meta_attributes
                    is-managed=false
                    target-role=Stopped
                Bundle: B2
                  Docker: image=pcs:test
                  Network: control-port=9000
                  Resource: R1 (class=ocf provider=pcsmock type=minimal)
                    Description: R1 description
                    Operations:
                      monitor: R1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

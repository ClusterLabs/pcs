from unittest import TestCase

from pcs_test.tier1.cib_resource.common import get_cib_resources
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_data_to_tmpfile,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class OperationAdd(TestCase, get_assert_pcs_effect_mixin(get_cib_resources)):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_cib_resource_operation_add")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings()
        write_data_to_tmpfile(self.fixture_cib_cache(), self.temp_cib)

    def tearDown(self):
        self.temp_cib.close()

    def fixture_cib_cache(self):
        if not hasattr(self.__class__, "cib_cache"):
            self.__class__.cib_cache = self.fixture_cib()
        return self.__class__.cib_cache

    def fixture_cib(self):
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.assert_pcs_success(
            "resource create --no-default-ops R ocf:pcsmock:minimal".split()
        )
        # add to cib:
        # <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
        #   <operations>
        #     <op id="R-monitor-interval-60s" interval="60s"
        #       name="monitor"
        #     />
        #   </operations>
        # </primitive>
        self.temp_cib.seek(0)
        return self.temp_cib.read()

    def test_base_add(self):
        self.assert_effect(
            "resource op add R start interval=20s".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                        <op id="R-start-interval-20s" interval="20s"
                            name="start"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_add_with_OCF_CHECK_LEVEL(self):
        # pylint: disable=invalid-name
        self.assert_effect(
            (
                "resource op add R start interval=20s OCF_CHECK_LEVEL=1 "
                "description=test-description"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                        <op description="test-description" name="start"
                            id="R-start-interval-20s" interval="20s"
                        >
                            <instance_attributes
                                id="params-R-start-interval-20s"
                            >
                                <nvpair
                                    id="R-start-interval-20s-OCF_CHECK_LEVEL-1"
                                    name="OCF_CHECK_LEVEL" value="1"
                                />
                            </instance_attributes>
                        </op>
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_can_multiple_operation_add(self):
        self.assert_effect(
            "resource op add R start interval=20s".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                        <op id="R-start-interval-20s" interval="20s"
                            name="start"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )
        self.assert_effect(
            "resource op add R stop interval=30s".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                        <op id="R-start-interval-20s" interval="20s"
                            name="start"
                        />
                        <op id="R-stop-interval-30s" interval="30s"
                            name="stop"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_id_specified(self):
        self.assert_effect(
            "resource op add R start timeout=30 id=abcd".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                        <op id="abcd" interval="0s" name="start" timeout="30" />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_invalid_id(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource op add R start timeout=30 id=ab#cd".split(),
            "Error: invalid operation id 'ab#cd', '#' is not a valid"
            " character for a operation id\n",
        )

    def test_duplicate_id(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource op add R start timeout=30 id=R".split(),
            "Error: id 'R' is already in use, please specify another one\n",
        )

    def test_unknown_option(self):
        self.assert_pcs_fail(
            "resource op add R start timeout=30 requires=quorum".split(),
            (
                "Error: requires is not a valid op option (use --force to "
                "override)\n"
            ),
        )

import shutil
from unittest import TestCase

from pcs.test.cib_resource.common import get_cib_resources
from pcs.test.tools.cib import get_assert_pcs_effect_mixin
from pcs.test.tools.misc import  get_test_resource as rc
from pcs.test.tools.pcs_runner import PcsRunner


class OperationAdd(
    TestCase,
    get_assert_pcs_effect_mixin(get_cib_resources)
):
    temp_cib = rc("temp-cib.xml")
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.prepare_cib_file()
        self.pcs_runner = PcsRunner(self.temp_cib)

    def prepare_cib_file(self):
        with open(self.temp_cib, "w") as temp_cib_file:
            temp_cib_file.write(self.fixture_cib_cache())

    def fixture_cib_cache(self):
        if not hasattr(self.__class__, "cib_cache"):
            self.__class__.cib_cache = self.fixture_cib()
        return self.__class__.cib_cache

    def fixture_cib(self):
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)
        self.assert_pcs_success(
            "resource create --no-default-ops R ocf:heartbeat:Dummy"
        )
        #add to cib:
        # <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
        #   <operations>
        #     <op id="R-monitor-interval-60s" interval="60s"
        #       name="monitor"
        #     />
        #   </operations>
        # </primitive>
        cib_content = open(self.temp_cib).read()

        #clean
        self.pcs_runner = None
        shutil.copy(self.empty_cib, self.temp_cib)

        return cib_content

    def test_base_add(self):
        self.assert_effect(
            "resource op add R start interval=20s",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="R-start-interval-20s" interval="20s"
                            name="start"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_add_with_OCF_CHECK_LEVEL(self):
        self.assert_effect(
            "resource op add R start interval=20s OCF_CHECK_LEVEL=1"
                " description=test-description"
            ,
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
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
            </resources>"""
        )

    def test_can_multiple_operation_add(self):
        self.assert_effect(
            "resource op add R start interval=20s",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="R-start-interval-20s" interval="20s"
                            name="start"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )
        self.assert_effect(
            "resource op add R stop interval=30s",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="R-start-interval-20s" interval="20s"
                            name="start"
                        />
                        <op id="R-stop-interval-30s" interval="30s"
                            name="stop"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_id_specified(self):
        self.assert_effect(
            "resource op add R start timeout=30 id=abcd",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                        <op id="abcd" interval="0s" name="start" timeout="30" />
                    </operations>
                </primitive>
            </resources>"""
        )

    def test_invalid_id(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource op add R start timeout=30 id=ab#cd",
            "Error: invalid operation id 'ab#cd', '#' is not a valid"
                " character for a operation id\n"
        )

    def test_duplicate_id(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource op add R start timeout=30 id=R",
            "Error: id 'R' is already in use, please specify another one\n"
        )

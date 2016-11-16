from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil

from pcs.test.cib_resource.common import AssertPcsEffectMixin
from pcs.test.tools.misc import  get_test_resource as rc
from pcs.test.tools.pcs_runner import PcsRunner
from pcs.test.tools.pcs_unittest import TestCase


class Success(TestCase, AssertPcsEffectMixin):
    temp_cib = rc("temp-cib.xml")
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
        shutil.copy(rc('cib-empty-1.2.xml'), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)
        self.assert_pcs_success(
            "resource create --no-default-ops R ocf:heartbeat:Dummy"
        )
        #add to cib:
        # <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
        #   <instance_attributes id="R-instance_attributes"/>
        #   <operations>
        #     <op id="R-monitor-interval-60s" interval="60s"
        #       name="monitor"
        #     />
        #   </operations>
        # </primitive>
        cib_content = open(self.temp_cib).read()

        #clean
        self.pcs_runner = None
        shutil.copy(rc('cib-empty-1.2.xml'), self.temp_cib)

        return cib_content

    def test_base_add(self):
        self.assert_effect(
            "resource op add R start interval=20s",
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat" type="Dummy">
                    <instance_attributes id="R-instance_attributes"/>
                    <operations>
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
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
                    <instance_attributes id="R-instance_attributes"/>
                    <operations>
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
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
                    <instance_attributes id="R-instance_attributes"/>
                    <operations>
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
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
                    <instance_attributes id="R-instance_attributes"/>
                    <operations>
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
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

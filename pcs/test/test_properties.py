import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils
from pcs_test_functions import pcs

empty_cib = "empty.xml"
temp_cib = "temp.xml"

class ResourceAdditionTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def testEmpty(self):
        output, returnVal = pcs(temp_cib, "property") 
        assert returnVal == 0, 'Unable to list resources'
        assert output == "Cluster Properties:\n", [output]

    def testDefaults(self):
        output, returnVal = pcs(temp_cib, "property --defaults")
        assert returnVal == 0, 'Unable to list resources'
        assert output == 'Cluster Properties:\n batch-limit: 30\n cluster-delay: 60s\n cluster-infrastructure: heartbeat\n cluster-recheck-interval: 15min\n crmd-finalization-timeout: 30min\n crmd-integration-timeout: 3min\n crmd-transition-delay: 0s\n dc-deadtime: 20s\n dc-version: none\n default-action-timeout: 20s\n default-resource-stickiness: 0\n election-timeout: 2min\n enable-startup-probes: true\n expected-quorum-votes: 2\n is-managed-default: true\n maintenance-mode: false\n migration-limit: -1\n no-quorum-policy: stop\n node-health-green: 0\n node-health-red: -INFINITY\n node-health-strategy: none\n node-health-yellow: 0\n pe-error-series-max: -1\n pe-input-series-max: 4000\n pe-warn-series-max: 5000\n placement-strategy: default\n remove-after-stop: false\n shutdown-escalation: 20min\n start-failure-is-fatal: true\n startup-fencing: true\n stonith-action: reboot\n stonith-enabled: true\n stonith-timeout: 60s\n stop-all-resources: false\n stop-orphan-actions: true\n stop-orphan-resources: true\n symmetric-cluster: true\n', [output]

        output, returnVal = pcs(temp_cib, "property --all")
        assert returnVal == 0, 'Unable to list resources'
        assert output == 'Cluster Properties:\n batch-limit: 30\n cluster-delay: 60s\n cluster-infrastructure: heartbeat\n cluster-recheck-interval: 15min\n crmd-finalization-timeout: 30min\n crmd-integration-timeout: 3min\n crmd-transition-delay: 0s\n dc-deadtime: 20s\n dc-version: none\n default-action-timeout: 20s\n default-resource-stickiness: 0\n election-timeout: 2min\n enable-startup-probes: true\n expected-quorum-votes: 2\n is-managed-default: true\n maintenance-mode: false\n migration-limit: -1\n no-quorum-policy: stop\n node-health-green: 0\n node-health-red: -INFINITY\n node-health-strategy: none\n node-health-yellow: 0\n pe-error-series-max: -1\n pe-input-series-max: 4000\n pe-warn-series-max: 5000\n placement-strategy: default\n remove-after-stop: false\n shutdown-escalation: 20min\n start-failure-is-fatal: true\n startup-fencing: true\n stonith-action: reboot\n stonith-enabled: true\n stonith-timeout: 60s\n stop-all-resources: false\n stop-orphan-actions: true\n stop-orphan-resources: true\n symmetric-cluster: true\n', [output]

        output, returnVal = pcs(temp_cib, "property set blahblah=blah")
        assert returnVal == 1
        assert output == "Error: unknown cluster property: 'blahblah', (use --force to override)\n",[output]

        output, returnVal = pcs(temp_cib, "property set blahblah=blah --force")
        assert returnVal == 0,output
        assert output == "",output

        output, returnVal = pcs(temp_cib, "property set stonith-enabled=false")
        assert returnVal == 0,output
        assert output == "",output

        output, returnVal = pcs(temp_cib, "property")
        assert returnVal == 0
        assert output == "Cluster Properties:\n blahblah: blah\n stonith-enabled: false\n", [output]

        output, returnVal = pcs(temp_cib, "property --defaults")
        assert returnVal == 0, 'Unable to list resources'
        assert output == 'Cluster Properties:\n batch-limit: 30\n cluster-delay: 60s\n cluster-infrastructure: heartbeat\n cluster-recheck-interval: 15min\n crmd-finalization-timeout: 30min\n crmd-integration-timeout: 3min\n crmd-transition-delay: 0s\n dc-deadtime: 20s\n dc-version: none\n default-action-timeout: 20s\n default-resource-stickiness: 0\n election-timeout: 2min\n enable-startup-probes: true\n expected-quorum-votes: 2\n is-managed-default: true\n maintenance-mode: false\n migration-limit: -1\n no-quorum-policy: stop\n node-health-green: 0\n node-health-red: -INFINITY\n node-health-strategy: none\n node-health-yellow: 0\n pe-error-series-max: -1\n pe-input-series-max: 4000\n pe-warn-series-max: 5000\n placement-strategy: default\n remove-after-stop: false\n shutdown-escalation: 20min\n start-failure-is-fatal: true\n startup-fencing: true\n stonith-action: reboot\n stonith-enabled: true\n stonith-timeout: 60s\n stop-all-resources: false\n stop-orphan-actions: true\n stop-orphan-resources: true\n symmetric-cluster: true\n', [output]

        output, returnVal = pcs(temp_cib, "property --all")
        assert returnVal == 0, 'Unable to list resources'
        assert output == 'Cluster Properties:\n batch-limit: 30\n blahblah: blah\n cluster-delay: 60s\n cluster-infrastructure: heartbeat\n cluster-recheck-interval: 15min\n crmd-finalization-timeout: 30min\n crmd-integration-timeout: 3min\n crmd-transition-delay: 0s\n dc-deadtime: 20s\n dc-version: none\n default-action-timeout: 20s\n default-resource-stickiness: 0\n election-timeout: 2min\n enable-startup-probes: true\n expected-quorum-votes: 2\n is-managed-default: true\n maintenance-mode: false\n migration-limit: -1\n no-quorum-policy: stop\n node-health-green: 0\n node-health-red: -INFINITY\n node-health-strategy: none\n node-health-yellow: 0\n pe-error-series-max: -1\n pe-input-series-max: 4000\n pe-warn-series-max: 5000\n placement-strategy: default\n remove-after-stop: false\n shutdown-escalation: 20min\n start-failure-is-fatal: true\n startup-fencing: true\n stonith-action: reboot\n stonith-enabled: false\n stonith-timeout: 60s\n stop-all-resources: false\n stop-orphan-actions: true\n stop-orphan-resources: true\n symmetric-cluster: true\n', [output]

if __name__ == "__main__":
    unittest.main()


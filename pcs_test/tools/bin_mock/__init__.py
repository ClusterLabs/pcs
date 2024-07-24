import os.path

BIN_MOCK_DIR = os.path.dirname(os.path.abspath(__file__))

CRM_RESOURCE_BIN = os.path.abspath(
    os.path.join(BIN_MOCK_DIR, "pcmk/crm_resource")
)
PACEMAKER_FENCED_BIN = os.path.abspath(
    os.path.join(BIN_MOCK_DIR, "pcmk/pacemaker-fenced")
)
STONITH_ADMIN_BIN = os.path.abspath(
    os.path.join(BIN_MOCK_DIR, "pcmk/stonith_admin")
)

MOCK_SETTINGS = {
    "crm_resource_exec": CRM_RESOURCE_BIN,
    "pacemaker_fenced_exec": PACEMAKER_FENCED_BIN,
    "stonith_admin_exec": STONITH_ADMIN_BIN,
}


def get_mock_settings(*required_settings):
    return {
        key: value
        for key, value in MOCK_SETTINGS.items()
        if key in required_settings
    }

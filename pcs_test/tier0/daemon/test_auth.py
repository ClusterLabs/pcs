from unittest import TestCase
import logging

from pcs_test.tools.misc import create_setup_patch_mixin

from pcs.daemon import auth

USER = "user"
PASSWORD = "password"

# Don't write errors to test output.
logging.getLogger("pcsd.daemon").setLevel(logging.CRITICAL)


class AuthorizeUserSync(TestCase, create_setup_patch_mixin(auth)):
    def setUp(self):
        self.authenticate_by_pam = self.setup_patch("authenticate_by_pam")
        self.get_user_groups_sync = self.setup_patch("get_user_groups_sync")

    def test_success_authorization(self):
        self.authenticate_by_pam.return_value = True
        self.get_user_groups_sync.return_value = [auth.HA_ADM_GROUP]

        user_auth_info = auth.authorize_user_sync(USER, PASSWORD)
        self.assertEqual(user_auth_info.name, USER)
        self.assertTrue(user_auth_info.is_authorized)

    def test_failed_pam_authorization(self):
        self.authenticate_by_pam.return_value = False

        user_auth_info = auth.authorize_user_sync(USER, PASSWORD)
        self.assertEqual(user_auth_info.name, USER)
        self.assertFalse(user_auth_info.is_authorized)

    def test_failed_on_groups(self):
        self.authenticate_by_pam.return_value = True
        self.get_user_groups_sync.return_value = []

        user_auth_info = auth.authorize_user_sync(USER, PASSWORD)
        self.assertEqual(user_auth_info.name, USER)
        self.assertFalse(user_auth_info.is_authorized)

import base64
from unittest import TestCase, mock

from pcs.daemon.app.common import get_legacy_desired_user_from_request


class GetLegacyDesiredUserFromRequest(TestCase):
    USER_NAME = "testuser"
    USER_GROUPS = ["haclient", "wheel", "square"]
    USER_GROUPS_ENCODED = base64.b64encode(b"haclient wheel square")

    def setUp(self):
        self.mock_handler = mock.Mock()
        self.mock_logger = mock.Mock(spec_set=["debug", "warning"])

    def assert_effective_user_log(
        self, username: str | None, groups: list[str]
    ):
        self.mock_logger.debug.assert_called_once_with(
            "Effective user: username=%s groups=%s", username, ",".join(groups)
        )

    def test_success(self):
        self.mock_handler.get_cookie.side_effect = {
            "CIB_user": self.USER_NAME,
            "CIB_user_groups": self.USER_GROUPS_ENCODED,
        }.get

        result = get_legacy_desired_user_from_request(
            self.mock_handler, self.mock_logger
        )
        self.assertEqual(result.username, self.USER_NAME)
        self.assertEqual(result.groups, self.USER_GROUPS)
        self.assert_effective_user_log(self.USER_NAME, self.USER_GROUPS)
        self.mock_logger.warning.assert_not_called()

    def test_only_username(self):
        self.mock_handler.get_cookie.side_effect = {
            "CIB_user": self.USER_NAME
        }.get

        result = get_legacy_desired_user_from_request(
            self.mock_handler, self.mock_logger
        )
        self.assertEqual(result.username, self.USER_NAME)
        self.assertEqual(result.groups, [])
        self.assert_effective_user_log(self.USER_NAME, [])
        self.mock_logger.warning.assert_not_called()

    def test_only_groups_ignored(self):
        self.mock_handler.get_cookie.side_effect = {
            "CIB_user_groups": self.USER_GROUPS_ENCODED,
        }.get

        result = get_legacy_desired_user_from_request(
            self.mock_handler, self.mock_logger
        )
        self.assertEqual(result.username, None)
        self.assertEqual(result.groups, [])
        self.assert_effective_user_log("", [])
        self.mock_logger.warning.assert_not_called()

    def test_invalid_groups(self):
        self.mock_handler.get_cookie.side_effect = {
            "CIB_user": "testuser",
            "CIB_user_groups": "this is not a base64 encoded string",
        }.get

        result = get_legacy_desired_user_from_request(
            self.mock_handler, self.mock_logger
        )
        self.assertEqual(result.username, "testuser")
        self.assertEqual(result.groups, [])
        self.mock_logger.warning.assert_called_once_with(
            "Unable to decode desired user groups"
        )
        self.assert_effective_user_log(self.USER_NAME, [])

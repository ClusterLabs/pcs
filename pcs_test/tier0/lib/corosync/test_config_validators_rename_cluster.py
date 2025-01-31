from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.corosync import config_validators

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class RenameCluster(TestCase):
    # pylint: disable=no-self-use
    def test_valid_cluster_name(self):
        assert_report_item_list_equal(
            config_validators.rename_cluster("my-cluster", False), []
        )

    def test_empty_name(self):
        assert_report_item_list_equal(
            config_validators.rename_cluster(""),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="cluster name",
                    option_value="",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ],
        )

    def test_gfs2_too_long(self):
        assert_report_item_list_equal(
            config_validators.rename_cluster(33 * "a"),
            [
                fixture.error(
                    report_codes.COROSYNC_CLUSTER_NAME_INVALID_FOR_GFS2,
                    force_code=report_codes.FORCE,
                    cluster_name=(33 * "a"),
                    max_length=32,
                    allowed_characters="a-z A-Z 0-9 _-",
                ),
            ],
        )

    def test_gfs2_bad_characters(self):
        assert_report_item_list_equal(
            config_validators.rename_cluster("cluster.name"),
            [
                fixture.error(
                    report_codes.COROSYNC_CLUSTER_NAME_INVALID_FOR_GFS2,
                    force_code=report_codes.FORCE,
                    cluster_name="cluster.name",
                    max_length=32,
                    allowed_characters="a-z A-Z 0-9 _-",
                ),
            ],
        )

    def test_gfs2_forced(self):
        cluster_name = (16 * "a") + ".: @" + (16 * "b")
        assert_report_item_list_equal(
            config_validators.rename_cluster(
                cluster_name, force_cluster_name=True
            ),
            [
                fixture.warn(
                    report_codes.COROSYNC_CLUSTER_NAME_INVALID_FOR_GFS2,
                    cluster_name=cluster_name,
                    max_length=32,
                    allowed_characters="a-z A-Z 0-9 _-",
                ),
            ],
        )

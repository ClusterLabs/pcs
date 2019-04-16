from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal

from pcs.common import report_codes
from pcs.lib.corosync import config_validators

class RemoveLinks(TestCase):
    def setUp(self):
        self.existing = ["0", "3", "10", "1", "11"]

    def test_no_link_specified(self):
        assert_report_item_list_equal(
            config_validators.remove_links(
                [],
                self.existing,
                "knet"
            ),
            [
                fixture.error(
                    report_codes
                        .COROSYNC_CANNOT_ADD_REMOVE_LINKS_NO_LINKS_SPECIFIED
                    ,
                    add_or_not_remove=False
                )
            ]
        )

    def _assert_bad_transport(self, transport):
        assert_report_item_list_equal(
            config_validators.remove_links(
                ["3"],
                self.existing,
                transport
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_BAD_TRANSPORT,
                    add_or_not_remove=False,
                    actual_transport=transport,
                    required_transport_list=["knet"]
                )
            ]
        )

    def test_transport_udp(self):
        self._assert_bad_transport("udp")

    def test_transport_udpu(self):
        self._assert_bad_transport("udpu")

    def test_nonexistent_links(self):
        to_remove = ["15", "0", "4", "abc", "1"]
        assert len(to_remove) >= len(self.existing)

        assert_report_item_list_equal(
            config_validators.remove_links(
                to_remove,
                self.existing,
                "knet"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE,
                    link_list=["abc", "4", "15"],
                    existing_link_list=["0", "1", "3", "10", "11"],
                )
            ]
        )

    def test_zero_links_left(self):
        assert_report_item_list_equal(
            config_validators.remove_links(
                self.existing,
                self.existing,
                "knet"
            ),
            [
                fixture.error(
                    report_codes
                        .COROSYNC_CANNOT_ADD_REMOVE_LINKS_TOO_MANY_FEW_LINKS
                    ,
                    links_change_count=len(self.existing),
                    links_new_count=0,
                    links_limit_count=1,
                    add_or_not_remove=False,
                )
            ]
        )

    def test_remove_more_than_defined(self):
        assert_report_item_list_equal(
            config_validators.remove_links(
                self.existing + ["2"],
                self.existing,
                "knet"
            ),
            [
                fixture.error(
                    report_codes
                        .COROSYNC_CANNOT_ADD_REMOVE_LINKS_TOO_MANY_FEW_LINKS
                    ,
                    # We try to remove more links than defined yet only defined
                    # links are counted here - nonexistent links cannot be
                    # defined so they are not included in the count
                    links_change_count=len(self.existing),
                    # the point of the test is to not get negative number here
                    links_new_count=0,
                    links_limit_count=1,
                    add_or_not_remove=False,
                ),
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE,
                    link_list=["2"],
                    existing_link_list=["0", "1", "3", "10", "11"],
                )
            ]
        )

    def test_duplicate_links(self):
        assert_report_item_list_equal(
            config_validators.remove_links(
                ["abc", "abc", "11", "11", "1", "1", "3"],
                self.existing,
                "knet"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_NUMBER_DUPLICATION,
                    link_number_list=["abc", "1", "11"],
                ),
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE,
                    link_list=["abc"],
                    existing_link_list=["0", "1", "3", "10", "11"],
                )
            ]
        )

    def test_success(self):
        assert_report_item_list_equal(
            config_validators.remove_links(
                ["0", "3", "11"],
                self.existing,
                "knet"
            ),
            [
            ]
        )

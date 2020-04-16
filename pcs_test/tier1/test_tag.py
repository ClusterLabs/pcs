from unittest import TestCase
from textwrap import dedent

from lxml import etree

from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
    outdent,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


empty_cib = rc("cib-empty.xml")


class TestTagMixin(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//tags")[0]
        )
    )
):
    def setUp(self):
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier1_tag")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        # pylint: disable=invalid-name
        self.temp_cib.close()

    def fixture_dummy_resource(self, _id):
        self.assert_pcs_success(
            "resource create {} ocf:pacemaker:Dummy --no-default-ops".format(
                _id,
            )
        )

    def fixture_dummy_clone_resource(self, _id):
        self.assert_pcs_success(
            (
                "resource create {} ocf:pacemaker:Dummy clone --no-default-ops"
            ).format(_id,)
        )

    def fixture_location_constraint_with_id(
        self, constraint_id, resource_id, node_id="rh7-1", score="INFINITY",
    ):
        self.assert_pcs_success(
            "constraint location add {} {} {} {} --force".format(
                constraint_id, resource_id, node_id, score,
            ),
            stdout_start="Warning: Validation for node existence",
        )


class TagCreate(TestTagMixin, TestCase):
    def test_create_success(self):
        self.fixture_dummy_resource("idx-01")
        self.fixture_dummy_resource("idx-02")
        self.assert_effect(
            "tag create tag1 idx-01 idx-02",
            """
            <tags>
              <tag id="tag1">
                <obj_ref id="idx-01"/>
                <obj_ref id="idx-02"/>
              </tag>
            </tags>
            """,
        )
        self.fixture_dummy_resource("idy-01")
        self.fixture_dummy_resource("idy-02")
        self.assert_effect(
            "tag create tag2 idy-01 idy-02",
            """
            <tags>
              <tag id="tag1">
                <obj_ref id="idx-01"/>
                <obj_ref id="idx-02"/>
              </tag>
              <tag id="tag2">
                <obj_ref id="idy-01"/>
                <obj_ref id="idy-02"/>
              </tag>
            </tags>
            """,
        )

    def test_create_not_enough_arguments(self):
        self.assert_pcs_fail(
            "tag create", stdout_start="\nUsage: pcs tag <command>",
        )
        self.assert_pcs_fail(
            "tag create tag", stdout_start="\nUsage: pcs tag <command>",
        )
        self.assert_pcs_success("tag", " No tags defined\n")

    def test_create_invalid_tag_id(self):
        self.fixture_dummy_resource("idx-01")
        self.fixture_dummy_resource("idx-02")
        self.assert_pcs_fail(
            "tag create 1tag idx-01 idx-02",
            (
                "Error: invalid id '1tag', '1' is not a valid first character "
                "for a id\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_success("tag", " No tags defined\n")

    def test_create_nonexistent_ids(self):
        self.assert_pcs_fail(
            "tag create tag noid-01",
            (
                "Error: bundle/clone/group/resource 'noid-01' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_fail(
            "tag create tag noid-01 noid-02",
            (
                "Error: bundle/clone/group/resource 'noid-01' does not exist\n"
                "Error: bundle/clone/group/resource 'noid-02' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_success("tag", " No tags defined\n")

    def test_create_duplicate_ids(self):
        self.fixture_dummy_resource("idx-01")
        self.fixture_dummy_resource("idx-02")
        self.fixture_dummy_resource("idx-03")
        self.assert_pcs_fail(
            "tag create tag1 idx-01 idx-01",
            (
                "Error: Ids to add must be unique, duplicate ids: 'idx-01'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_fail(
            "tag create tag1 idx-02 idx-02 idx-01 idx-01 idx-03",
            (
                "Error: Ids to add must be unique, duplicate ids: 'idx-01', "
                "'idx-02'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_success("tag", " No tags defined\n")

    def test_create_tag_id_already_exists(self):
        self.fixture_dummy_resource("idx-01")
        self.fixture_dummy_resource("idx-02")
        self.fixture_dummy_resource("idx-03")
        self.assert_pcs_fail(
            "tag create idx-01 idx-02 idx-03",
            (
                "Error: 'idx-01' already exists\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_success("tag", " No tags defined\n")

    def test_create_tag_contains_itself(self):
        self.fixture_dummy_resource("idx-01")
        self.assert_pcs_fail(
            "tag create idx-01 idx-01",
            (
                "Error: 'idx-01' already exists\n"
                "Error: Tag cannot contain itself\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_success("tag", " No tags defined\n")

    def test_create_nonresource_ref_id(self):
        self.fixture_dummy_resource("idx-01")
        self.fixture_dummy_resource("idx-02")
        self.fixture_location_constraint_with_id("cid-01", "idx-01")
        self.fixture_location_constraint_with_id("cid-02", "idx-02")
        self.assert_pcs_fail(
            "tag create tag1 cid-01 cid-02",
            (
                "Error: 'cid-01' is not a bundle/clone/group/resource\n"
                "Error: 'cid-02' is not a bundle/clone/group/resource\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_success("tag", " No tags defined\n")


class TagConfigListBase(TestTagMixin):
    command = None

    def test_config_empty(self):
        self.assert_pcs_success(
            "tag", " No tags defined\n",
        )

        self.assert_pcs_success(
            f"tag {self.command}", " No tags defined\n",
        )

    def test_config_tag_does_not_exist(self):
        self.assert_pcs_fail(
            f"tag {self.command} notag1",
            (
                "Error: tag 'notag1' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_fail(
            f"tag {self.command} notag2 notag1",
            (
                "Error: tag 'notag2' does not exist\n"
                "Error: tag 'notag1' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_config_tags_defined(self):
        self.fixture_dummy_resource("idx-01")
        self.fixture_dummy_resource("idx-02")
        self.fixture_dummy_resource("idx-03")
        self.assert_pcs_success("tag create tag1 idx-01 idx-02 idx-03")
        self.assert_pcs_success(
            f"tag {self.command}",
            dedent(
                """\
                tag1
                  idx-01
                  idx-02
                  idx-03
                """
            ),
        )

        self.fixture_dummy_resource("idy-01")
        self.assert_pcs_success("tag create tag2 idy-01")
        self.assert_pcs_success(
            f"tag {self.command}",
            dedent(
                """\
                tag1
                  idx-01
                  idx-02
                  idx-03
                tag2
                  idy-01
                """
            ),
        )

        self.assert_pcs_success(
            f"tag {self.command} tag2",
            dedent(
                """\
                tag2
                  idy-01
                """
            ),
        )

        self.assert_pcs_success(
            f"tag {self.command} tag2 tag1",
            dedent(
                """\
                tag2
                  idy-01
                tag1
                  idx-01
                  idx-02
                  idx-03
                """
            ),
        )


class TagConfig(
    TagConfigListBase, TestCase,
):
    command = "config"


class TagList(
    TagConfigListBase, TestCase,
):
    command = "list"


class PcsConfigTagsTest(TestTagMixin, TestCase):
    config_template = dedent(
        """\
        Cluster Name: test99
        Corosync Nodes:
         rh7-1 rh7-2
        Pacemaker Nodes:

        Resources:{resources}
        Stonith Devices:
        Fencing Levels:

        Location Constraints:
        Ordering Constraints:
        Colocation Constraints:
        Ticket Constraints:

        Alerts:
         No alerts defined

        Resources Defaults:
         No defaults set
        Operations Defaults:
         No defaults set

        Cluster Properties:

        Tags:{tags}
        Quorum:
          Options:
        """
    )
    expected_resources = outdent(
        # pylint: disable=line-too-long
        """
         Resource: idx-01 (class=ocf provider=pacemaker type=Dummy)
          Operations: monitor interval=10s timeout=20s (idx-01-monitor-interval-10s)
         Resource: idx-02 (class=ocf provider=pacemaker type=Dummy)
          Operations: monitor interval=10s timeout=20s (idx-02-monitor-interval-10s)
         Resource: idx-03 (class=ocf provider=pacemaker type=Dummy)
          Operations: monitor interval=10s timeout=20s (idx-03-monitor-interval-10s)
        """
    )
    expected_tags = outdent(
        """
         tag1
           idx-01
           idx-02
           idx-03
        """
    )

    def setUp(self):
        super(PcsConfigTagsTest, self).setUp()
        self.pcs_runner.mock_settings = {
            "corosync_conf_file": rc("corosync.conf")
        }

    def fixture_expected_config(self, resources="\n", tags="\n"):
        return self.config_template.format(resources=resources, tags=tags)

    def test_config_no_tags(self):
        self.assert_pcs_success(
            "config", self.fixture_expected_config(tags="\n No tags defined\n")
        )

    def test_config_tags_defined(self):
        self.fixture_dummy_resource("idx-01")
        self.fixture_dummy_resource("idx-02")
        self.fixture_dummy_resource("idx-03")
        self.assert_pcs_success("tag create tag1 idx-01 idx-02 idx-03")
        self.assert_pcs_success(
            "config",
            self.fixture_expected_config(
                resources=self.expected_resources, tags=self.expected_tags,
            ),
        )


class TagRemoveDeleteBase(TestTagMixin):
    command = None

    def fixture_tags(self, number):
        self.fixture_dummy_resource("dummy")
        for i in range(1, number + 1):
            self.assert_pcs_success(f"tag create tag{i} dummy")

    def test_remove_not_enough_arguments(self):
        self.fixture_tags(1)
        self.assert_pcs_fail(
            f"tag {self.command}", stdout_start="\nUsage: pcs tag <command>",
        )
        self.assert_resources_xml_in_cib(
            """
            <tags>
              <tag id="tag1">
                <obj_ref id="dummy"/>
              </tag>
            </tags>
            """
        )

    def test_remove_nonexistent_tags(self):
        self.assert_pcs_fail(
            f"tag {self.command} tag",
            (
                "Error: tag 'tag' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.fixture_tags(1)
        self.assert_pcs_fail(
            f"tag {self.command} ta tag",
            (
                "Error: tag 'ta' does not exist\n"
                "Error: tag 'tag' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(
            """
            <tags>
              <tag id="tag1">
                <obj_ref id="dummy"/>
              </tag>
            </tags>
            """
        )

    def test_remove_single_tag(self):
        self.fixture_tags(1)
        self.assert_effect(
            f"tag {self.command} tag1",
            """
            <tags/>
            """,
        )

    def test_remove_one_tag(self):
        self.fixture_tags(2)
        self.assert_effect(
            f"tag {self.command} tag1",
            """
            <tags>
              <tag id="tag2">
                <obj_ref id="dummy"/>
              </tag>
            </tags>
            """,
        )

    def test_remove_more_tags(self):
        self.fixture_tags(4)
        self.assert_effect(
            f"tag {self.command} tag2 tag3",
            """
            <tags>
              <tag id="tag1">
                <obj_ref id="dummy"/>
              </tag>
              <tag id="tag4">
                <obj_ref id="dummy"/>
              </tag>
            </tags>
            """,
        )

    def test_remove_all_tags(self):
        self.fixture_tags(5)
        self.assert_effect(
            f"tag {self.command} tag1 tag2 tag3 tag4 tag5",
            """
            <tags/>
            """,
        )


class TagRemove(
    TagRemoveDeleteBase, TestCase,
):
    command = "remove"


class TagDelete(
    TagRemoveDeleteBase, TestCase,
):
    command = "delete"


class ResourceRemoveDeleteBase(TestTagMixin):
    command = None

    @staticmethod
    def fixture_error_message(resource, tags):
        return (
            "Error: Unable to remove resource '{resource}' because it is "
            "referenced in the tag{s}: {tags}\n".format(
                resource=resource,
                s="s" if len(tags) > 1 else "",
                tags="', '".join(tags),
            )
        )

    def test_resource_not_referenced_in_tags(self):
        self.fixture_dummy_resource("not-in-tags")
        self.assert_pcs_success(
            f"resource {self.command} not-in-tags",
            "Deleting Resource - not-in-tags\n",
        )

    def test_resource_referenced_in_a_single_tag(self):
        self.fixture_dummy_resource("in-single-tag")
        self.assert_pcs_success("tag create TAG in-single-tag")
        self.assert_pcs_fail(
            f"resource {self.command} in-single-tag",
            self.fixture_error_message("in-single-tag", ["TAG"]),
        )

    def test_resource_referenced_in_multiple_tags(self):
        self.fixture_dummy_resource("in-multiple-tags")
        self.assert_pcs_success("tag create TAG1 in-multiple-tags")
        self.assert_pcs_success("tag create TAG2 in-multiple-tags")
        self.assert_pcs_fail(
            f"resource {self.command} in-multiple-tags",
            self.fixture_error_message("in-multiple-tags", ["TAG1", "TAG2"]),
        )

    def test_duplicate_tag(self):
        self.fixture_dummy_clone_resource("duplicate-tag")
        self.assert_pcs_success(
            "tag create TAG3 duplicate-tag duplicate-tag-clone",
        )
        self.assert_pcs_fail(
            f"resource {self.command} duplicate-tag",
            self.fixture_error_message("duplicate-tag", ["TAG3"]),
        )


class ResourceRemove(
    ResourceRemoveDeleteBase, TestCase,
):
    command = "remove"


class ResourceDelete(
    ResourceRemoveDeleteBase, TestCase,
):
    command = "delete"


class TagUpdate(TestTagMixin, TestCase):
    def setUp(self):
        super(TagUpdate, self).setUp()
        for _id in ["a", "b", "e1", "e2", "e3"]:
            self.fixture_dummy_resource(_id)
        self.assert_pcs_success("tag create tag1 e1 e2 e3")

    def test_success_add_new_existing_before_and_remove(self):
        self.assert_effect(
            "tag update tag1 add a b e3 --before e2 remove e1",
            """
            <tags>
              <tag id="tag1">
                <obj_ref id="a"/>
                <obj_ref id="b"/>
                <obj_ref id="e3"/>
                <obj_ref id="e2"/>
              </tag>
            </tags>
            """,
        )

    def test_success_add_new_existing_after_and_remove(self):
        self.assert_effect(
            "tag update tag1 add e3 a b --after e1 remove e2",
            """
            <tags>
              <tag id="tag1">
                <obj_ref id="e1"/>
                <obj_ref id="e3"/>
                <obj_ref id="a"/>
                <obj_ref id="b"/>
              </tag>
            </tags>
            """,
        )

    def test_fail_not_enough_arguments(self):
        self.assert_pcs_fail(
            "tag update", stdout_start="\nUsage: pcs tag <command>",
        )

    def test_fail_tag_update_ids_not_specified(self):
        self.assert_pcs_fail(
            "tag update tag1",
            stdout_start=(
                "Hint: Specify at least one id for 'add' or 'remove' arguments."
            ),
        )

    def test_fail_tag_update_add_ids_not_specified(self):
        self.assert_pcs_fail(
            "tag update tag1 add",
            stdout_start=(
                "Hint: Specify at least one id for 'add' or 'remove' arguments."
            ),
        )

    def test_fail_tag_update_remove_ids_not_specified(self):
        self.assert_pcs_fail(
            "tag update tag1 remove",
            stdout_start=(
                "Hint: Specify at least one id for 'add' or 'remove' arguments."
            ),
        )

    def test_fail_tag_and_add_id_not_exist(self):
        self.assert_pcs_fail(
            "tag update nonexisting_tag add nonexisting_resource",
            (
                "Error: tag 'nonexisting_tag' does not exist\n"
                "Error: bundle/clone/group/resource 'nonexisting_resource' "
                "does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_add_id_exist_but_belongs_to_unexpected_type(self):
        self.assert_pcs_success(
            "resource create dummy-with-metadata ocf:pacemaker:Dummy"
        )
        self.assert_pcs_fail(
            "tag update tag1 add dummy-with-metadata-start-interval-0s",
            (
                "Error: 'dummy-with-metadata-start-interval-0s' is not a "
                "bundle/clone/group/resource\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_id_is_not_tag(self):
        self.assert_pcs_fail(
            "tag update a add a",
            (
                "Error: 'a' is not a tag\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_add_ids_already_in_tag(self):
        self.assert_pcs_fail(
            "tag update tag1 add e1 e2",
            (
                "Error: Cannot add reference ids already in the tag 'tag1': "
                "'e1', 'e2'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_before_id_does_not_exist(self):
        self.assert_pcs_fail(
            "tag update tag1 add a --before no_id",
            (
                "Error: There is no reference id 'no_id' in the tag 'tag1', "
                "cannot put reference ids next to it in the tag\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_after_id_does_not_exist(self):
        self.assert_pcs_fail(
            "tag update tag1 add e1 --after no_id",
            (
                "Error: There is no reference id 'no_id' in the tag 'tag1', "
                "cannot put reference ids next to it in the tag\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_adding_removing_adjacent_id_duplicated(self):
        self.assert_pcs_fail(
            "tag update tag1 add e1 e1 e2 e2 --before e1 remove e1 e1 e2 e2",
            (
                "Error: Ids cannot be added and removed at the same time: "
                "'e1', 'e2'\n"
                "Error: Ids to add must be unique, duplicate ids: 'e1', 'e2'\n"
                "Error: Ids to remove must be unique, duplicate ids: 'e1', 'e2'"
                "\n"
                "Error: Cannot put id 'e1' next to itself.\n"
                "Error: Cannot remove id 'e1' next to which ids are being to "
                "put\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_removed_ids_would_leave_tag_empty(self):
        self.assert_pcs_fail(
            "tag update tag1 remove e1 e2 e3",
            (
                "Error: There would be no references left in the tag, please "
                "remove the whole tag using the 'pcs tag remove ...' command\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_add_new_ids_and_remove_it_at_the_same_time(self):
        self.assert_pcs_fail(
            "tag update tag1 add a b remove a b",
            (
                "Error: Ids cannot be added and removed at the same time: 'a', "
                "'b'\n"
                "Error: there is no obj_ref 'a' in the tag 'tag1'\n"
                "Error: there is no obj_ref 'b' in the tag 'tag1'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_fail_remove_ids_not_in_tag(self):
        self.assert_pcs_fail(
            "tag update tag1 remove nonexistent1 nonexistent2",
            (
                "Error: there is no obj_ref 'nonexistent1' in the tag 'tag1'\n"
                "Error: there is no obj_ref 'nonexistent2' in the tag 'tag1'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

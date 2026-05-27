from textwrap import dedent
from unittest import TestCase

from pcs_test.tier1.cib_resource.common import get_cib_resources
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.fixture_cib import modify_cib_file
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    skip_unless_pacemaker_supports_op_onfail_demote,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


def fixture_primitive(
    rsc_id,
    agent_class="ocf",
    agent_provider="pcsmock",
    agent_type="minimal",
    inner_xml="",
):
    return f"""
        <primitive class="{agent_class}" id="{rsc_id}"
          provider="{agent_provider}" type="{agent_type}"
        >
          {inner_xml}
        </primitive>
    """


def fixture_clone(clone_id, inner_xml=""):
    clone_id_split = clone_id.split("-")
    assert clone_id_split[-1] == "clone"
    rsc_id = "-".join(clone_id_split[:-1])
    primitive_xml = fixture_primitive(
        rsc_id,
        agent_class="ocf",
        agent_provider="pcsmock",
        agent_type="stateful",
    )
    return dedent(
        f"""
        <clone id="{clone_id}">
            {primitive_xml}
            {inner_xml}
        </clone>
        """
    )


def fixture_group(group_id, inner_xml=""):
    group_id_split = group_id.split("-")
    assert group_id_split[-1] == "group"
    rsc_id = "-".join(group_id_split[:-1])
    return dedent(
        f"""
        <group id="{group_id}">
            {fixture_primitive(rsc_id)}
            {inner_xml}
        </group>
        """
    )


def fixture_bundle(bundle_id, inner_xml=""):
    return dedent(
        f"""
        <bundle id="{bundle_id}">
          <docker image="pcs:test" replicas="4" replicas-per-host="2"
            run-command="/bin/true" network="extra_network_settings"
            options="extra_options"
          />
          {inner_xml}
        </bundle>
        """
    )


def fixture_resources(resources_xml=""):
    return f"<resources>\n  {resources_xml}\n</resources>\n"


def fixture_meta_attrs(rsc_id, nvpairs_xml=""):
    return dedent(
        f"""
        <meta_attributes id="{rsc_id}-meta_attributes">
          {nvpairs_xml}
        </meta_attributes>"""
    )


class ResourceMetaPrimitive(
    TestCase, get_assert_pcs_effect_mixin(get_cib_resources)
):
    rsc_id = "R"
    resource_fixture = staticmethod(fixture_primitive)

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_resource_meta")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")

    def tearDown(self):
        self.temp_cib.close()

    def _fixture_nvpair_priority(self, value):
        return dedent(
            f"""
            <nvpair id="{self.rsc_id}-meta_attributes-priority"
                name="priority" value="{value}"
            />"""
        )

    def test_add(self):
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=fixture_resources(self.resource_fixture(self.rsc_id)),
            ),
            self.temp_cib,
        )
        self.assert_effect(
            ["resource", "meta", self.rsc_id, "priority=2"],
            fixture_resources(
                self.resource_fixture(
                    self.rsc_id,
                    inner_xml=fixture_meta_attrs(
                        self.rsc_id,
                        nvpairs_xml=self._fixture_nvpair_priority(2),
                    ),
                ),
            ),
        )

    def test_modify(self):
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=fixture_resources(
                    self.resource_fixture(
                        self.rsc_id,
                        inner_xml=fixture_meta_attrs(
                            self.rsc_id,
                            nvpairs_xml=self._fixture_nvpair_priority(2),
                        ),
                    )
                ),
            ),
            self.temp_cib,
        )
        self.assert_effect(
            ["resource", "meta", self.rsc_id, "priority=0"],
            fixture_resources(
                self.resource_fixture(
                    self.rsc_id,
                    inner_xml=fixture_meta_attrs(
                        self.rsc_id,
                        nvpairs_xml=self._fixture_nvpair_priority(0),
                    ),
                )
            ),
        )

    def test_remove(self):
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=fixture_resources(
                    self.resource_fixture(
                        self.rsc_id,
                        inner_xml=fixture_meta_attrs(
                            self.rsc_id,
                            nvpairs_xml=self._fixture_nvpair_priority(2),
                        ),
                    )
                ),
            ),
            self.temp_cib,
        )
        self.assert_effect(
            ["resource", "meta", self.rsc_id, "priority="],
            fixture_resources(
                self.resource_fixture(
                    self.rsc_id,
                    inner_xml=fixture_meta_attrs(self.rsc_id),
                )
            ),
        )


class ResourceMetaGroup(ResourceMetaPrimitive):
    rsc_id = "R-group"
    resource_fixture = staticmethod(fixture_group)


class ResourceMetaClone(ResourceMetaPrimitive):
    rsc_id = "R-clone"
    resource_fixture = staticmethod(fixture_clone)


class ResourceMetaBundle(ResourceMetaPrimitive):
    rsc_id = "B"
    resource_fixture = staticmethod(fixture_bundle)


def fixture_instance_attrs(parent_id, *nvpairs):
    nvpairs_xml = "\n".join(
        f'<nvpair id="{parent_id}-{name}-{value}" name="{name}" value="{value}"/>'
        for name, value in nvpairs
    )
    return dedent(
        f"""\
        <instance_attributes id="params-{parent_id}">
            {nvpairs_xml}
        </instance_attributes>"""
    )


def fixture_op(  # noqa: PLR0913
    op_id,
    name,
    interval,
    description=None,
    enabled=None,
    inner_xml="",
    interval_origin=None,
    on_fail=None,
    record_pending=None,
    role=None,
    start_delay=None,
    timeout=None,
):
    attrs = [
        f'id="{op_id}"',
        f'interval="{interval}"',
        f'name="{name}"',
    ]
    if description:
        attrs.append(f'description="{description}"')
    if enabled:
        attrs.append(f'enabled="{enabled}"')
    if interval_origin:
        attrs.append(f'interval-origin="{interval_origin}"')
    if on_fail:
        attrs.append(f'on-fail="{on_fail}"')
    if record_pending:
        attrs.append(f'record-pending="{record_pending}"')
    if role:
        attrs.append(f'role="{role}"')
    if start_delay:
        attrs.append(f'start-delay="{start_delay}"')
    if timeout:
        attrs.append(f'timeout="{timeout}"')
    if inner_xml:
        return f"<op {' '.join(attrs)}>\n{inner_xml}\n</op>"
    return f"<op {' '.join(attrs)}/>"


def fixture_operations(*ops_xml):
    ops = "\n".join(ops_xml)
    return f"""
        <operations>
          {ops}
        </operations>
    """


FIXTURE_EXISTING_OP_MONITOR = fixture_op(
    "R-monitor-interval-10s",
    "monitor",
    "10s",
    timeout="20s",
    on_fail="restart",
    enabled="1",
)
FIXTURE_EXISTING_OP_RELOAD = fixture_op(
    "R-restart-interval-10s", "reload", "10s", timeout="20s", role="Started"
)
FIXTURE_EXISTING_OP_CIB = fixture_resources(
    fixture_primitive(
        "R",
        inner_xml=fixture_operations(
            FIXTURE_EXISTING_OP_MONITOR,
            FIXTURE_EXISTING_OP_RELOAD,
        ),
    )
)


class ResourceUpdateOperations(
    TestCase, get_assert_pcs_effect_mixin(get_cib_resources)
):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_resource_update_operations")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings()
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=FIXTURE_EXISTING_OP_CIB,
            ),
            self.temp_cib,
        )

    def tearDown(self):
        self.temp_cib.close()

    def _fixture_primitive_with_ops(self, *ops_xml):
        return fixture_resources(
            fixture_primitive("R", inner_xml=fixture_operations(*ops_xml))
        )

    def test_no_op_args(self):
        self.assert_effect(
            "resource update R op".split(),
            FIXTURE_EXISTING_OP_CIB,
        )

    def test_op_name_only(self):
        self.assert_effect(
            "resource update R op monitRO".split(),
            FIXTURE_EXISTING_OP_CIB,
        )

    def test_add_single_operation(self):
        self.assert_effect(
            "resource update R op start interval=20s".split(),
            self._fixture_primitive_with_ops(
                FIXTURE_EXISTING_OP_MONITOR,
                FIXTURE_EXISTING_OP_RELOAD,
                fixture_op("R-start-interval-20s", "start", "20s"),
            ),
        )

    def test_update_existing_operation_not_specified_options_are_deleted(self):
        self.assert_effect(
            (
                "resource update R op monitor interval=10s timeout=30s "
                "description=desc"
            ).split(),
            self._fixture_primitive_with_ops(
                fixture_op(
                    "R-monitor-interval-10s",
                    "monitor",
                    "10s",
                    timeout="30s",
                    description="desc",
                ),
                FIXTURE_EXISTING_OP_RELOAD,
            ),
        )

    def test_update_existing_operation_add_role_fails(self):
        self.assert_pcs_fail(
            (
                "resource update R op monitor interval=10s timeout=20s "
                "role=Started"
            ).split(),
            (
                "Error: operation monitor with interval 10s already specified"
                " for R:\n"
                "monitor enabled=1 interval=10s on-fail=restart timeout=20s "
                "(R-monitor-interval-10s)\n"
            ),
        )
        self.assert_resources_xml_in_cib(FIXTURE_EXISTING_OP_CIB)

    def test_update_existing_op_with_role_without_specifying_role_fails(self):
        self.assert_pcs_fail(
            (
                "resource update R op reload interval=10s timeout=30s "
                "description=desc"
            ).split(),
            (
                "Error: operation reload with interval 10s already specified"
                " for R:\n"
                "reload interval=10s role=Started timeout=20s "
                "(R-restart-interval-10s)\n"
            ),
        )
        self.assert_resources_xml_in_cib(FIXTURE_EXISTING_OP_CIB)

    def test_update_existing_operation_with_role_success(self):
        self.assert_effect(
            (
                "resource update R op reload interval=10s timeout=30s "
                "role=Started description=desc"
            ).split(),
            self._fixture_primitive_with_ops(
                FIXTURE_EXISTING_OP_MONITOR,
                fixture_op(
                    "R-reload-interval-10s",
                    "reload",
                    "10s",
                    timeout="30s",
                    role="Started",
                    description="desc",
                ),
            ),
        )

    def test_update_existing_add_new(self):
        self.assert_effect(
            (
                "resource update R op monitor interval=5s start interval=0 "
                "timeout=20 "
            ).split(),
            self._fixture_primitive_with_ops(
                fixture_op("R-monitor-interval-5s", "monitor", "5s"),
                FIXTURE_EXISTING_OP_RELOAD,
                fixture_op("R-start-interval-0", "start", "0", timeout="20"),
            ),
        )

    def test_same_operation_different_interval_same_role(self):
        self.assert_effect(
            (
                "resource update R op meta-data interval=10 timeout=20 "
                "enabled=1 meta-data interval=20 timeout=30"
            ).split(),
            self._fixture_primitive_with_ops(
                FIXTURE_EXISTING_OP_MONITOR,
                FIXTURE_EXISTING_OP_RELOAD,
                fixture_op(
                    "R-meta-data-interval-20", "meta-data", "20", timeout="30"
                ),
            ),
        )

    def test_same_operation_different_interval_different_role(self):
        self.assert_effect(
            (
                "resource update R op meta-data interval=10 timeout=20 "
                "enabled=1 meta-data interval=20 timeout=30 role=Stopped"
            ).split(),
            self._fixture_primitive_with_ops(
                FIXTURE_EXISTING_OP_MONITOR,
                FIXTURE_EXISTING_OP_RELOAD,
                fixture_op(
                    "R-meta-data-interval-10",
                    "meta-data",
                    "10",
                    timeout="20",
                    enabled="1",
                ),
                fixture_op(
                    "R-meta-data-interval-20",
                    "meta-data",
                    "20",
                    timeout="30",
                    role="Stopped",
                ),
            ),
        )

    def test_duplicate_op_id(self):
        self.assert_pcs_fail_regardless_of_force(
            "resource update R op monitor interval=30 id=R".split(),
            "Error: id 'R' is already in use, please specify another one\n",
        )
        self.assert_resources_xml_in_cib(FIXTURE_EXISTING_OP_CIB)

    def _invalid_operations(self, force=False):
        forceable = "Warning" if force else "Error"
        force_opt = "--force" if force else ""
        use_force = ", use --force to override" if not force else ""

        self.assert_pcs_fail(
            (
                "resource update R op monitor interval=5s "
                "status id=ab#cd enabled=invalid-bool interval=invalid-number "
                "interval-origin=value name=status on-fail=invalid-on-fail "
                "record-pending=invalid-bool role=invalid-role "
                f"start-delay=value timeout=invalid-timeout {force_opt}"
            ).split(),
            (
                "Deprecation Warning: Specifying an operation name with "
                "'name=<value>' syntax is deprecated and might be removed in a "
                "future release. Use the operation name as the first argument "
                "instead.\n"
                f"{forceable}: 'status' is not a valid operation name value, "
                "use 'meta-data', 'migrate_from', 'migrate_to', 'monitor', "
                "'reload', 'reload-agent', 'start', 'stop', 'validate-all'"
                f"{use_force}\n"
                "Error: 'invalid-role' is not a valid role value, use "
                "'Master', 'Promoted', 'Slave', 'Started', 'Stopped', "
                "'Unpromoted'\n"
                "Error: 'invalid-on-fail' is not a valid on-fail value, use "
                "'block', 'demote', 'fence', 'ignore', 'restart', "
                "'restart-container', 'standby', 'stop'\n"
                "Error: 'invalid-bool' is not a valid record-pending value, "
                "use a pacemaker boolean value: '0', '1', 'false', 'n', 'no', "
                "'off', 'on', 'true', 'y', 'yes'\n"
                "Error: 'invalid-bool' is not a valid enabled value, use a "
                "pacemaker boolean value: '0', '1', 'false', 'n', 'no', 'off', "
                "'on', 'true', 'y', 'yes'\n"
                "Error: Only one of resource operation options "
                "'interval-origin' and 'start-delay' can be used\n"
                "Error: invalid operation id 'ab#cd', '#' is not a valid "
                "character for a operation id\n"
                "Error: 'invalid-number' is not a valid interval value, use "
                "time interval (e.g. 1, 2s, 3m, 4h, ...)\n"
                "Error: 'invalid-timeout' is not a valid timeout value, use "
                "time interval (e.g. 1, 2s, 3m, 4h, ...)\n"
            ),
        )
        self.assert_resources_xml_in_cib(FIXTURE_EXISTING_OP_CIB)

    def test_invalid_operations(self):
        self._invalid_operations(force=False)

    def test_invalid_operations_force(self):
        self._invalid_operations(force=True)

    def test_add_operation_with_ocf_check_level(self):
        self.assert_effect(
            "resource update R op monitor OCF_CHECK_LEVEL=1".split(),
            self._fixture_primitive_with_ops(
                fixture_op(
                    "R-monitor-interval-60s",
                    "monitor",
                    "60s",
                    inner_xml=fixture_instance_attrs(
                        "R-monitor-interval-60s",
                        ("OCF_CHECK_LEVEL", "1"),
                    ),
                ),
                FIXTURE_EXISTING_OP_RELOAD,
            ),
        )

    @skip_unless_pacemaker_supports_op_onfail_demote()
    def test_add_operation_onfail_demote_upgrade_cib(self):
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty-3.3.xml"),
                resources=FIXTURE_EXISTING_OP_CIB,
            ),
            self.temp_cib,
        )
        self.assert_effect(
            "resource update R op start on-fail=demote".split(),
            self._fixture_primitive_with_ops(
                FIXTURE_EXISTING_OP_MONITOR,
                FIXTURE_EXISTING_OP_RELOAD,
                fixture_op(
                    "R-start-interval-0s",
                    "start",
                    "0s",
                    on_fail="demote",
                ),
            ),
            stderr_full="Cluster CIB has been upgraded to latest version\n",
        )

    def test_duplicate_operation_same_interval(self):
        fixture_cib = fixture_resources(
            fixture_primitive(
                "R",
                inner_xml=fixture_operations(
                    fixture_op(
                        "R-monitor-interval-10",
                        "monitor",
                        "10",
                    ),
                    fixture_op(
                        "R-monitor-interval-20",
                        "monitor",
                        "20",
                    ),
                ),
            )
        )
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=fixture_cib,
            ),
            self.temp_cib,
        )
        self.assert_pcs_fail(
            "resource update R op monitor interval=20".split(),
            (
                "Error: operation monitor with interval 20s already specified"
                " for R:\n"
                "monitor interval=20 (R-monitor-interval-20)\n"
            ),
        )
        self.assert_resources_xml_in_cib(fixture_cib)


class ResourceUpdateCloneOperations(
    TestCase, get_assert_pcs_effect_mixin(get_cib_resources)
):
    def setUp(self):
        self.temp_cib = get_tmp_file(
            "tier1_test_resource_update_clone_operations"
        )
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings()
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=fixture_resources(fixture_clone("R-clone")),
            ),
            self.temp_cib,
        )

    def tearDown(self):
        self.temp_cib.close()

    def test_clone_rejects_op_keyword(self):
        self.assert_pcs_fail(
            "resource update R-clone op monitor interval=20s".split(),
            stderr_full=(
                "Error: op settings must be changed on base resource,"
                " not the clone\n"
            ),
        )

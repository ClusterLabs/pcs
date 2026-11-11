from unittest import TestCase

from pcs_test.tier0.cli.resource.test_create import ResourceCreateWaitMixin


class ResourceCreateWaitStonith(ResourceCreateWaitMixin, TestCase):
    cli_cmd = "stonith create R dummy"
    create_call_cmd = "stonith.create"
    create_call_args = ("R", "dummy", [], {}, {})
    create_call_kwargs = dict(
        allow_absent_agent=False,
        allow_invalid_operation=False,
        allow_invalid_instance_attributes=False,
        ensure_disabled=False,
        use_default_operations=True,
        enable_agent_self_validation=False,
    )

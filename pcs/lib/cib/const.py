from typing import Final

TAG_CONSTRAINT_COLOCATION: Final = "rsc_colocation"
TAG_CONSTRAINT_LOCATION: Final = "rsc_location"
TAG_CONSTRAINT_ORDER: Final = "rsc_order"
TAG_CONSTRAINT_TICKET: Final = "rsc_ticket"
TAG_CRM_CONFIG: Final = "crm_config"
TAG_OBJREF: Final = "obj_ref"
TAG_RESOURCE_BUNDLE: Final = "bundle"
TAG_RESOURCE_CLONE: Final = "clone"
TAG_RESOURCE_GROUP: Final = "group"
TAG_RESOURCE_MASTER: Final = "master"
TAG_RESOURCE_PRIMITIVE: Final = "primitive"
TAG_RESOURCE_SET: Final = "resource_set"
TAG_RULE: Final = "rule"
TAG_TAG: Final = "tag"

TAG_LIST_CONSTRAINABLE: Final = frozenset(
    (
        TAG_RESOURCE_BUNDLE,
        TAG_RESOURCE_CLONE,
        TAG_RESOURCE_GROUP,
        TAG_RESOURCE_MASTER,
        TAG_RESOURCE_PRIMITIVE,
        # Not yet supported. What needs to be done:
        # * move all constraint code to library
        # * add support for using tags in constraints
        # * write tests to verify creating constraints with tags
        # * write tests verifying displaying constraints with tags
        # TAG_TAG,
    )
)
TAG_LIST_CONSTRAINT = frozenset(
    (
        TAG_CONSTRAINT_COLOCATION,
        TAG_CONSTRAINT_LOCATION,
        TAG_CONSTRAINT_ORDER,
        TAG_CONSTRAINT_TICKET,
    )
)
TAG_LIST_RESOURCE: Final = frozenset(
    (
        TAG_RESOURCE_BUNDLE,
        TAG_RESOURCE_CLONE,
        TAG_RESOURCE_GROUP,
        TAG_RESOURCE_MASTER,
        TAG_RESOURCE_PRIMITIVE,
    )
)
TAG_LIST_RESOURCE_MULTIINSTANCE: Final = frozenset(
    (
        TAG_RESOURCE_BUNDLE,
        TAG_RESOURCE_CLONE,
        TAG_RESOURCE_MASTER,
    )
)

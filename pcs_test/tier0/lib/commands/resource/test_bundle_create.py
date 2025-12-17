from unittest import TestCase

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import resource

from pcs_test.tier0.lib.commands.resource.bundle_common import (
    AllOptionsMixin,
    FixturesMixin,
    MetaMixin,
    NetworkMixin,
    ParametrizedContainerMixin,
    PortMapMixin,
    SetUpMixin,
    StorageMapMixin,
    UpgradeMixin,
    WaitMixin,
)


class CreateCommandMixin:
    container_type = None
    bundle_id = "B1"
    image = "pcs:test"

    def bundle_create(self, bundle_id=None, container_type=None, **params):
        if "container_options" not in params:
            params["container_options"] = {"image": self.image}

        resource.bundle_create(
            self.env_assist.get_env(),
            bundle_id=bundle_id or self.bundle_id,
            container_type=container_type or self.container_type,
            **params,
        )

    def run_bundle_cmd(self, *args, **kwargs):
        self.bundle_create(*args, **kwargs)


class MinimalCreate(CreateCommandMixin, FixturesMixin, SetUpMixin, TestCase):
    container_type = "docker"

    def test_success(self):
        self.config.env.push_cib(resources=self.fixture_resources_bundle_simple)
        self.bundle_create()

    def test_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.bundle_create(
                bundle_id="B#1", container_type="nonsense"
            )
        )
        self.env_assist.assert_reports(
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_ID_BAD_CHAR,
                    {
                        "invalid_character": "#",
                        "id": "B#1",
                        "id_description": "bundle name",
                        "is_first_char": False,
                    },
                    None,
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "container type",
                        "option_value": "nonsense",
                        "allowed_values": ["docker", "podman"],
                        "cannot_be_empty": False,
                        "forbidden_characters": None,
                    },
                    None,
                ),
            ]
        )


class CreateParametrizedContainerMixin(
    CreateCommandMixin, ParametrizedContainerMixin, UpgradeMixin
):
    pass


class CreatePodman(CreateParametrizedContainerMixin, TestCase):
    container_type = "podman"
    old_version_cib_filename = "cib-empty-3.1.xml"


class CreateWithNetwork(CreateCommandMixin, NetworkMixin, TestCase):
    container_type = "docker"


class CreateWithPortMap(CreateCommandMixin, PortMapMixin, TestCase):
    container_type = "docker"


class CreateWithStorageMap(CreateCommandMixin, StorageMapMixin, TestCase):
    container_type = "docker"


class CreateWithMeta(CreateCommandMixin, MetaMixin, TestCase):
    container_type = "docker"


class CreateWithAllOptions(CreateCommandMixin, AllOptionsMixin, TestCase):
    container_type = "docker"


class Wait(CreateCommandMixin, WaitMixin, TestCase):
    container_type = "docker"

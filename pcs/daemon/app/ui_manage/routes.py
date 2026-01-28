from pcs.daemon.app.auth_provider import ApiAuthProviderFactoryInterface
from pcs.daemon.app.common import RoutesType
from pcs.daemon.app.ui_manage.auth_gui_against_nodes import (
    ManageAuthGuiAgainstNodesHandler,
)
from pcs.daemon.app.ui_manage.existing_cluster import (
    ManageExistingClusterHandler,
)
from pcs.daemon.async_tasks.scheduler import Scheduler


def get_routes(
    api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    scheduler: Scheduler,
) -> RoutesType:
    params = dict(
        scheduler=scheduler, api_auth_provider_factory=api_auth_provider_factory
    )
    return [
        (
            r"/manage/auth_gui_against_nodes",
            ManageAuthGuiAgainstNodesHandler,
            params,
        ),
        (r"/manage/existingcluster", ManageExistingClusterHandler, params),
    ]

from typing import Callable

from pcs.lib.pcs_cfgsync.config.facade import Facade as CfgsyncCtlFacade

UPDATE_SYNC_OPTIONS_ACTIONS: dict[
    str, Callable[[CfgsyncCtlFacade, str], None]
] = {
    "sync_thread_enable": lambda facade, value: facade.enable_sync(),
    "sync_thread_disable": lambda facade, value: facade.disable_sync(),
    "sync_thread_resume": lambda facade, value: facade.resume_sync(),
    "sync_thread_pause": lambda facade, value: facade.pause_sync(int(value)),
}

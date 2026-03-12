from pcs.lib.env import LibraryEnvironment, WaitType


def wait_for_pcmk_idle(env: LibraryEnvironment, wait_value: WaitType) -> None:
    """
    Wait for the cluster to settle into stable state.

    env
    wait_value -- value describing the timeout the command
    """
    timeout = env.ensure_wait_satisfiable(wait_value)
    env.wait_for_idle(timeout)

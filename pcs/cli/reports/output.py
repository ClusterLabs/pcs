from pcs.cli.common.tools import print_to_stderr


def warn(message: str) -> None:
    print_to_stderr(f"Warning: {message}")


def deprecation_warning(message: str) -> None:
    print_to_stderr(f"Deprecation Warning: {message}")


def error(message: str) -> SystemExit:
    print_to_stderr(f"Error: {message}")
    return SystemExit(1)

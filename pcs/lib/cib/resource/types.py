from collections.abc import Mapping

# TODO temporary definition, we want to overhaul the whole 'resource create'
# command using this and implement a proper dataclass for resource operations
ResourceOperationIn = Mapping[str, str | None]
ResourceOperationOut = dict[str, str | None]
ResourceOperationFilteredIn = Mapping[str, str]
ResourceOperationFilteredOut = dict[str, str]

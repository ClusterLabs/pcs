from typing import Dict, Mapping, Optional

# TODO temporary definition, we want to overhaul the whole 'resource create'
# command using this and implement a proper dataclass for resource operations
ResourceOperationIn = Mapping[str, Optional[str]]
ResourceOperationOut = Dict[str, Optional[str]]
ResourceOperationFilteredIn = Mapping[str, str]
ResourceOperationFilteredOut = Dict[str, str]

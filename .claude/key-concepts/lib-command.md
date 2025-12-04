# What "Lib Command" Means in PCS

In the PCS project, a "lib command" or a "library command" refers to a library function in pcs/lib/commands/ that implements the core business logic for a user-facing CLI command. This is a key architectural concept in PCS's three-layer design.

## The Architecture

Lib commands are the middle layer between:
1. CLI layer (pcs/cli/, pcs/*.py) - User interface, argument parsing
2. Library layer (pcs/lib/commands/) - ← Lib commands live here
3. Common layer (pcs/common/) - Shared utilities

## Key Characteristics of Lib Commands

1. They always accept LibraryEnvironment as the first parameter:

```
# From pcs/lib/commands/resource.py
def create(
  env: LibraryEnvironment,
  resource_id: str,
  resource_agent_name: str,
  operation_list: List[Mapping[str, str]],
  meta_attributes: Mapping[str, str],
  instance_attributes: Mapping[str, str],
  ...
):
```

2. They're isolated from CLI concerns:
- No argument parsing (CLI does that)
- No direct stdout/stderr output
- No knowledge of command-line flags
- Return structured data or report errors via ReportProcessor
- They can only raise LibraryError exception, all other exceptions must be caugth and converted to LibraryError in all library commands

3. They perform the actual work:
- Load/modify CIB (Cluster Information Base) XML
- Communicate with cluster nodes
- Validate configurations
- Execute system commands via CommandRunner

## Why This Matters

Separation of concerns:
- Lib commands can be reused by CLI, daemon (pcsd), and tests
- Same business logic works regardless of interface (CLI vs HTTP API)
- Tests can mock LibraryEnvironment without dealing with CLI

## Location
Lib commands are located in `pcs/lib/commands/`. Only functions not prefixed with an underscore are considered library commands.

## Summary
So when you hear "lib command" in PCS, it means: the pure business logic function that does the actual work, isolated from user interface concerns.

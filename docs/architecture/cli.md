# CLI layer

Source: `pcs/cli/`

The CLI layer handles command-line parsing, argument validation, and user
interaction. It translates user input into library command calls and presents
results back to the user. The CLI never contains business logic — it delegates
to the [library layer](library.md).

## Command pipeline

A CLI command flows through a fixed chain of registration points. Missing any
step causes runtime errors that are not caught by type checks or tests.

```
User input ("pcs cluster node clear ...")
  │
  ├─ 0. Entry point     pcs/app.py                      → parses options, sets up context
  │
  ├─ 1. Routing         pcs/cli/routing/cluster.py      → selects handler
  │
  ├─ 2. CLI handler     pcs/cli/cluster/command.py      → parses args, calls lib
  │
  ├─ 3. lib_wrapper     pcs/cli/common/lib_wrapper.py   → exposes lib to CLI
  │
  └─ 4. Library command pcs/lib/commands/cluster.py     → business logic
```

The following registrations are also required when adding a new command but
don't affect the runtime call chain:

- **Documentation** — help text and man page
- **Capability registration** — `pcsd/capabilities.xml.in`

### Entry point

Source: `pcs/app.py`

`app.py:main()` is the boundary between raw CLI input and the structured
pipeline. Its job is to turn `sys.argv` into the `(lib, argv, modifiers)` triple
that every handler receives — so that handlers never deal with raw option
parsing or environment setup.

The key steps:

1. **Separates options from arguments** — global flags (`-f`, `--force`,
   `--debug`, `--wait`, etc.) are parsed out via `getopt.gnu_getopt()`. What
   remains is the subcommand path and its positional arguments — this becomes
   the `argv` that handlers see.
2. **Handles exit-early options** — `--help`, `--version`, and `--fullhelp`
   produce output and exit before any routing happens.
3. **Builds the handler context** — the parsed options become an
   `InputModifiers` object (see [below](#inputmodifiers)) that handlers use for
   flag validation and access. A `Library` wrapper is created to give handlers
   a uniform interface to library commands (see
   [lib_wrapper](#lib_wrapper) below). Together with the remaining `argv`,
   these form the `(lib, argv, modifiers)` triple passed into routing.

Errors raised during command execution are caught at this level:

- **`CmdLineInputError`** — translated to usage text on stderr + exit code 1.
- **`LibraryError`** — the report items it carries are reported through the
  shared console report processor (`library_wrapper.env.report_processor`) and
  pcs exits with code 1 — or code 2 when any reported error was a waiting
  timeout (see [Exit codes](#exit-codes) below). If the error carries no report
  items, a generic "unable to continue" message is printed instead. See
  [reports.md — Rendering reports in the CLI](reports.md#rendering-reports-in-the-cli).

#### Exit codes

pcs uses three exit codes:

- **`0`** — success.
- **`2`** — action was performed successfully, but waiting for the cluster to
  process it did not finish in time (e.g. waiting for the cluster to settle, or
  waiting for cluster nodes to start). This lets callers distinguish "the
  action was performed but the thing pcs waited for did not complete in time"
  from other failures.
- **`1`** — any other error.

The console report processor tracks whether a waiting timeout error has been
reported (`ReportProcessorToConsole.has_waiting_timeout_error`); `app.py`
consults this flag when choosing between exit codes 1 and 2.

### Routing

Source: `pcs/cli/routing/`

Each area has a routing module that maps CLI subcommand strings to handler
functions. `create_router()` builds a nested dispatch function from a dictionary
of `{subcommand: handler}` entries. Routers can be nested for multi-level
commands (e.g. `pcs cluster node clear`).

Entries within each router are in **alphabetical order**.

**Legacy routing:** Some older commands route through monolithic handler files
(`pcs/cluster.py`, `pcs/resource.py`, etc.) instead of the modular
`pcs/cli/<area>/command.py`. The routing files import from both — compare
`cluster_command.node_rename_cib` (new-style, from
`pcs/cli/cluster/command.py`) vs `cluster.config_update` (old-style, from
`pcs/cluster.py`). **New commands must use the modular style**
(`pcs/cli/<area>/command.py`).

### CLI handler

Source: `pcs/cli/<area>/command.py`

The handler function receives `(lib, argv, modifiers)` and:

1. Validates allowed flags: `modifiers.ensure_only_supported(...)`
2. Validates argument count (raises `CmdLineInputError()` on mismatch)
3. Calls the library command via `lib.<area>.<command>(...)`

Handlers return `None`. The library command reports progress and errors through
the report processor automatically — the handler typically has no involvement.
Some handlers also print data returned by the library call (e.g. config/status
output). Argument and usage errors are signaled by raising `CmdLineInputError`;
`LibraryError` from library calls propagates up. Both are caught in `app.py`
(see [Entry point](#entry-point)).

#### InputModifiers

Source: `pcs/cli/common/parse_args.py`

`InputModifiers` wraps the parsed CLI options and provides validation and access
methods used by CLI handlers. It is created from the global options dict in
`app.py` and passed to every handler as the `modifiers` parameter.

Key methods:

- `ensure_only_supported(*options)` — raises `CmdLineInputError` if the user
  passed any option not in the supported set (plus `--debug`, which is always
  allowed). Every handler should call this first.
- `get(option)` — returns the option value. For boolean flags (e.g. `--force`),
  returns `True`/`False`. For value flags (e.g. `--wait`), returns the string
  value or `None` if not specified.
- `is_specified(option)` — returns whether the user explicitly passed the
  option on the command line.
- `ensure_not_mutually_exclusive(*options)` — raises `CmdLineInputError` if
  more than one of the listed options was specified.
- `ensure_not_incompatible(checked, incompatible)` — raises `CmdLineInputError`
  if the user specified both the checked option and any of the incompatible ones.
  Unlike `ensure_not_mutually_exclusive` (which is symmetric), this is
  directional — e.g. `ensure_not_incompatible("--simulate", {"-f", "--wait"})`
  rejects `--simulate` combined with `-f` or `--wait`, but `-f` with `--wait`
  alone is fine.
- `get_subset(*options, **custom)` — creates a new `InputModifiers` containing
  only the specified options. Used when delegating to sub-handlers.

### lib_wrapper

Source: `pcs/cli/common/lib_wrapper.py`

The `lib_wrapper` module connects CLI handler calls to library command
functions. Each area has a binding dictionary that maps string keys to library
command functions, wrapped with appropriate middleware.

**Forgetting the lib_wrapper entry** causes `AttributeError` at runtime — no
static check catches it.

**Important:** the area in lib_wrapper corresponds to the **library command
module** (`pcs/lib/commands/<area>.py`), not the CLI routing area. A command
routed through `pcs/cli/routing/cluster.py` may bind to `lib.cib.<command>` if
the library function lives in `pcs/lib/commands/cib.py`.

### Documentation

Both files must be updated:

- `pcs/usage.py` — CLI help text (shown by e.g. `pcs cluster --help`)
- `pcs/pcs.8.in` — man page (groff format). Hyphens in command names and flags
  must be escaped (`\-`), flags are bolded with `\fB...\fR`
  (e.g. `[\fB\-\-force\fR]`). Each entry starts with `.TP`.

### Capability registration

`pcsd/capabilities.xml.in` — CLI and daemon feature negotiation. Required for
new commands, command options or functionalities exposed via CLI and the
daemon: attributes 'in-pcs' and 'in-pcsd', respectively.

## Middleware

Source: `pcs/cli/common/middleware.py`, `pcs/cli/common/lib_wrapper.py`

The lib_wrapper binding specifies **middleware** that runs before and after the
library command. Middleware handles transparent file I/O for CIB and
corosync.conf:

```python
# Commands that read/write CIB (supports -f flag for local file)
middleware.build(middleware_factory.cib)

# Commands that read/write corosync.conf (supports --corosync_conf flag)
middleware.build(middleware_factory.corosync_conf_existing)

# Both CIB and corosync.conf
middleware.build(middleware_factory.cib, middleware_factory.corosync_conf_existing)

# No file middleware
middleware.build()
```

The CIB middleware handles the `-f` flag transparently: when the user passes
`-f <file>`, the middleware reads CIB from the file before the command runs
and writes it back after. The library command uses `env.get_cib()` /
`env.push_cib()` regardless — it doesn't know whether CIB comes from a live
cluster or a file. Any command bound with `middleware_factory.cib` automatically
supports the `-f` flag without explicit handling in the command.

The corosync.conf middleware works the same way for `--corosync_conf`.

See [library.md — Live-only vs. file-compatible commands](library.md#live-only-vs-file-compatible-commands)
for how the library layer interacts with this mechanism.

## Force flags pattern (CLI side)

Many commands support `--force` to override safety checks. The CLI handler
converts the modifier to a `force_flags` list and passes it to the library
command:

```python
def my_command(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) != 2:
        raise CmdLineInputError()
    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    lib.area.command(argv[0], argv[1], force_flags)
```

The library command declares `force_flags` as a parameter (typically with
default `()`) and uses it to decide whether to emit warnings (force applied)
or forceable errors (force not applied). See
[reports.md — Forceable errors](reports.md#forceable-errors-force-override-pattern)
for the library side of this pattern.

## Overriding report messages

Source: `pcs/cli/reports/messages.py`

Library report messages (`pcs/common/reports/messages.py`) are intentionally
client-agnostic — they must not reference CLI flags or pcs command syntax.
When the CLI needs to add CLI-specific hints (e.g. "use `--force` to override"
or "try running `pcs host auth`"), it overrides the library message text using
the `CliReportMessageCustom` mechanism.

### Writing a custom CLI message

Create a subclass of `CliReportMessageCustom` in `pcs/cli/reports/messages.py`.
The subclass needs two things:

1. **`_obj` type annotation** — set to the corresponding library
   `ReportItemMessage` subclass from `pcs.common.reports.messages`. This tells
   the base class which dataclass to reconstruct from the DTO payload.
2. **`message` property** — returns the CLI-tailored text. Use `self._obj` to
   access structured fields from the library message.

Registration is automatic — subclasses are discovered via
`get_all_subclasses()` at import time. No manual map entry is needed. An
`AssertionError` is raised if two subclasses map to the same message code.

### Examples

**Adding a CLI flag hint** — the library message says what happened; the CLI
override appends what the user can do about it:

```python
class ResourceManagedNoMonitorEnabled(CliReportMessageCustom):
    _obj: messages.ResourceManagedNoMonitorEnabled

    @property
    def message(self) -> str:
        return (
            f"Resource '{self._obj.resource_id}' has no enabled monitor "
            "operations. Re-run with '--monitor' to enable them."
        )
```

**Adding a command suggestion** — the CLI appends a pcs command to the
library's original text via `self._obj.message`:

```python
class UseCommandClusterRename(CliReportMessageCustom):
    _obj: messages.UseCommandClusterRename

    @property
    def message(self) -> str:
        return self._obj.message + ", use 'pcs cluster rename'"
```

**Conditionally adding detail** — the library dataclass has a field the
library message ignores; the CLI override uses it:

```python
class InvalidCibContent(CliReportMessageCustom):
    _obj: messages.InvalidCibContent

    @property
    def message(self) -> str:
        return "invalid cib:\n{report}{more_verbose}".format(
            report=self._obj.report,
            more_verbose=format_optional(
                self._obj.can_be_more_verbose,
                "\n\nUse --full for more details.",
            ),
        )
```

Most library messages do not need CLI overrides — only add one when the
message should include CLI-specific syntax or actionable pcs commands.

## Registration checklist (new command)

When adding a new CLI command, all of the following must be updated:

1. **Routing** (`pcs/cli/routing/<area>.py`) — add entry mapping CLI subcommand
   string to handler function (alphabetical order)
2. **CLI handler** (`pcs/cli/<area>/command.py`) — implement handler function
3. **lib_wrapper** (`pcs/cli/common/lib_wrapper.py`) — add binding entry
   (area corresponds to **library** module, not CLI routing area)
4. **Library command** (`pcs/lib/commands/<area>.py`) — implement business
   logic (see [library.md](library.md))
5. **Daemon command mapping**
   (`pcs/daemon/async_tasks/worker/command_mapping.py`) — add `COMMAND_MAP`
   entry with permission level (alphabetical order)
6. **Help text** (`pcs/usage.py`) and **man page** (`pcs/pcs.8.in`)
7. **Capability** (`pcsd/capabilities.xml.in`) — CLI and daemon feature
   negotiation

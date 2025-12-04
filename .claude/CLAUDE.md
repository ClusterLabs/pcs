# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PCS (Pacemaker/Corosync Configuration System) is a command-line tool and daemon for configuring and managing Pacemaker-based high-availability clusters. The project consists of:

- **pcs**: Python-based CLI tool for cluster configuration
- **pcsd**: Daemon (HTTP API server) that enables remote cluster management
- Mixed Python/Ruby codebase supporting Pacemaker 3.x and Corosync 3.x

## Key Concepts
Read about key concepts in @.claude/key-concepts/* files.

## Build and Development Commands

### Initial Setup

```bash
./autogen.sh
./configure --enable-local-build --enable-dev-tests --enable-destructive-tests --enable-concise-tests
make
```

**Configure options:**
- `--enable-local-build`: Download all bundled Python dependencies
- `--enable-individual-bundling`: Download only missing dependencies
- `--enable-dev-tests`: Enable development-specific tests
- `--enable-destructive-tests`: Enable tests that may affect system state
- `--enable-concise-tests`: Enable concise test output
- `--enable-webui`: Build support for standalone web UI

### Running PCS and PCSD

```bash
# Run pcs CLI
pcs/pcs

# Run pcsd daemon
scripts/pcsd.sh
```

### Testing

```bash
# Run all tests
make check

# Specific test suites
make ruff_format_check    # Check code formatting
make ruff_isort_check     # Check import sorting
make mypy                 # Type checking
make ruff_lint            # Linting
make typos_check          # Spell checking
make tests_tier0          # Fast unit tests
make tests_tier1          # Integration tests
make pcsd-tests           # Ruby tests for pcsd

# Run specific Python tests
pcs_test/suite <test_name>

# Example: Run a specific test file
pcs_test/suite pcs_test/tier0/lib/test_node.py

# Distribution tarball check
make distcheck
```

### Code Formatting

```bash
# Auto-format Python code
make ruff_format
make ruff_isort
```

### Distribution

```bash
# Create distribution tarball
make dist
```

## Code Architecture

### Overall Structure

The codebase is split between Python (CLI, library and new daemon) and Ruby (legacy daemon):

```
pcs/                    # Python CLI and library code
├── cli/               # CLI layer - user-facing commands
├── lib/               # Core library - business logic
├── common/            # Shared code between CLI and daemon
├── daemon/            # Python-based pcsd daemon
└── snmp/              # SNMP integration

pcsd/                  # Ruby daemon (legacy, being phased out)
├── pcsd.rb           # Sinatra web app main file
├── remote.rb         # Remote command handlers
└── pcs.rb            # Ruby wrapper for pcs CLI

pcs_test/             # Test suite
├── tier0/            # Fast unit tests
└── tier1/            # Integration tests
```

### Python Architecture (pcs/)

**Three-layer architecture:**

1. **CLI layer** (`pcs/cli/`): Handles command-line parsing and user interaction
   - Command routing via `pcs/app.py` and `pcs/cli/routing/`
   - Each command module (e.g., `cluster.py`, `resource.py`) maps to CLI commands
   - Reports output to users via `pcs/cli/reports/`

2. **Library layer** (`pcs/lib/`): Core business logic, isolated from CLI
   - Command implementations in `pcs/lib/commands/`
   - Uses `LibraryEnvironment` (`pcs/lib/env.py`) for dependency injection
   - CIB (Cluster Information Base) manipulation in `pcs/lib/cib/`
   - Node communication via `pcs/lib/communication/`
   - Returns structured data and `ReportItem` objects (not strings)

3. **Common layer** (`pcs/common/`): Shared between CLI and daemon
   - DTOs (Data Transfer Objects) for serialization
   - Communication protocols
   - Type definitions and constants

**Key design patterns:**
- Library functions accept `LibraryEnvironment` (env) for accessing services (CIB, runner, communicator)
- Library reports errors via `ReportProcessor` - never directly to stdout/stderr
- CLI translates library reports to user-friendly messages

### Ruby Daemon (pcsd/)

- Sinatra-based HTTP server for remote cluster management
- Main entry point: `pcsd/pcsd.rb`
- Remote commands handled in `pcsd/remote.rb`
- Authentication via `pcsd/auth.rb`
- Config sync via `pcsd/cfgsync.rb`
- It is being phased out as its code is being migrated to Python

### Python Daemon (pcs/daemon/)

- Tornado-based async HTTP server (newer, coexists with Ruby daemon)
- Multiple API versions: v0, v1, v2 in `pcs/daemon/app/`
- Async task scheduling in `pcs/daemon/async_tasks/`

### Data Flow Example

1. User runs: `pcs resource create myres ocf:pacemaker:Dummy`
2. `pcs/app.py` routes to `pcs/cli/routing/resource.py`
3. CLI calls library function in `pcs/lib/commands/resource.py`
4. Library uses `env.get_cib()` to load CIB XML
5. Library modifies CIB using lxml
6. Library pushes CIB via `env.push_cib()`
7. Library returns list of `ReportItem` objects
8. CLI translates reports to console output

## Important Development Notes

### System-Dependent Paths

All system paths must be in template files:
- `pcs/settings.py.in` (Python)
- `pcsd/settings.rb.in` (Ruby)

After modifying `*.in` files, run `./configure` to regenerate.

### Distribution Files

Files for distribution must be listed in `EXTRA_DIST` in the appropriate `Makefile.am` (in `pcs/`, `pcsd/`, or `pcs_test/`).

### Python Environment

Using a Python virtual environment is recommended:

```bash
mkdir ~/pyenvs
python3 -m venv --system-site-packages ~/pyenvs/pcs
source ~/pyenvs/pcs/bin/activate
```

### Pre-commit Hooks

Install pre-commit hooks to catch issues before committing:

```bash
cp ./scripts/pre-commit/pre-commit.sh .git/hooks/pre-commit
```

### Testing Individual Components

```bash
# Run a single test module
pcs_test/suite pcs_test.tier0.lib.cib.test_nvpair

# Run tests matching a pattern
pcs_test/suite pcs_test.tier0.lib.test_*
```

## Critical Policies

### AI-Generated Code Policy

**The pcs project does NOT accept any AI-generated code.** This includes:
- Code directly produced by AI tools (GitHub Copilot, ChatGPT, etc.)
- Code heavily adapted from AI suggestions
- Code snippets from AI models

Rationale: Concerns about intellectual property, quality, and ethics. Non-compliance will result in PR rejection.

### Code Quality Standards

- Must pass all checks: `make check`
- Type hints required (checked by mypy)
- Follow existing code patterns and architecture
- Don't break the three-layer separation (CLI / Lib / Common)
- All code including comments must be written in English

## Key Dependencies

**Python (3.12+):**
- lxml: XML manipulation (CIB)
- tornado: Async HTTP server (daemon)
- pycurl: HTTP communication
- dacite: Dataclass conversion

**Ruby (3.1.0+):**
- sinatra: Web framework (pcsd)
- puma: HTTP server

**External:**
- pacemaker 3.x: Cluster resource manager
- corosync 3.x: Cluster communication

## Common Patterns

### Working with CIB

```python
# In library code
def my_command(env: LibraryEnvironment, ...):
    cib = env.get_cib()  # Load CIB XML
    # Modify cib (lxml.etree._Element)
    env.push_cib(cib)  # Push changes
```

### Reporting

```python
# Library never prints directly
env.report_processor.report(
    ReportItem.info(reports.messages.MyInfoMessage())
)
```

### Node Communication

```python
# Communicate with cluster nodes
from pcs.lib.communication.tools import run_and_raise

run_and_raise(env.get_node_communicator(), [MyRequest(...)])
```

## Testing Philosophy

- **Tier 0**: Fast unit tests, no external dependencies, mock everything
- **Tier 1**: Integration tests, may interact with system services
- Tests located parallel to code: `pcs_test/tier0/lib/` mirrors `pcs/lib/`

## File Naming Conventions

- Python: snake_case for files and functions
- Test files: `test_<module>.py`
- Config templates: `<file>.in` (processed by autoconf)

# Code review methodology

## Mindset

You have several tasks:
* Confirm the code works and the changes meet the specified goal.
* Find bugs and other issues in the code.
* Conduct security review.
* Check whether the changes match project architecture and existing patterns.

Rules:
* Assume bugs exist until the evidence shows otherwise.
* Approach the code as an attacker and a skeptic, not as a collaborator
  cheering progress.
* Be direct and evidence-based: cite what you read, what could go wrong, and
  why.
* Read before running: prefer reasoning from the diff and surrounding context;
  note where only execution or integration tests would answer the question.


## Step 1: Functionality - "Does it work?"

Verify that the changes meet the specified goal. If the changes do not meet the
specified goal, report it as a critical issue.

Also check for:
* correctness and logic, such as:
  * off-by-one errors
  * wrong comparison operators
  * inverted conditions
  * incorrect boolean logic
  * nil/null/none/empty handling
  * uninitialized state
  * impossible or duplicate branches
  * incomplete state machines or transitions
  * control flow bugs
* edge cases and boundaries, such as:
  * empty, zero, negative, maximum-size, and malformed inputs
  * unicode, encoding, collation, and locale-sensitive behavior where relevant
  * time zones, clock skew, expiry, and ordering assumptions
  * concurrent or repeated submission of the same logical operation
* error handling and resilience, such as:
  * swallowed or logged-and-ignored errors, silent failures
  * missing rollback or cleanup on failure
  * overly broad catch-all handlers that hide programming errors
  * error messages or logs that leak secrets, PII, or internal implementation
    details
  * missing timeouts, retries without caps, or unbounded queues

Trace every code path. If a variable flows through a transformation pipeline
(filters, type casts, defaults, combine/merge operations), trace the type at
each step. If a value is set in one place and consumed in another, verify the
type survives the pipeline.

When the diff introduces new variable names, fields, or configuration keys,
search the codebase for existing uses of those names. If existing conditional
logic assumes the old semantics, the collision is in scope - the diff caused
the conflict even though the affected code is not in the changed lines.


## Step 2: Security - "Is it safe?"

### Security Mindset - CRITICAL

**Security findings are NEVER theoretical.** Do not dismiss injection,
credential exposure, or input validation issues because "the variable is
internally-sourced" or "the attacker would need special access".

Score the code as written, not the current trust model. A variable that is
internally-sourced today may be wired to user input tomorrow by a developer
who does not know it feeds into an unescaped shell command. Future maintainers
will change input sources without knowing the downstream execution context.

**Prioritize future-proofing and security best practices.** Sanitize inputs at
the point of use, not based on assumptions about who provides the data. If
unsanitized input reaches a shell, config file, or code execution context, it
is a finding - regardless of who controls the input today.

**Recognize explicit mitigations.** When code explicitly disables a dangerous
feature (e.g., `resolve_entities=False` for XML parsing, `shell=False` for
subprocess), do not flag the vulnerability that the mitigation prevents. Score
the code as written - if the mitigation is present, the vulnerability is not
present.

### Checks

Check for:
* security issues, such as:
  * injection (command, SQL, LDAP, XML, template, etc.)
  * unsafe deserialization
  * path traversal
  * authentication and authorization gaps
  * insecure direct object reference (IDOR)
  * missing checks on sensitive operations
  * secrets, tokens, or credentials in code, config or logs
  * insecure defaults
  * sensitive data in logs/errors
  * cryptographic weaknesses
  * unvalidated external inputs
* concurrency issues, such as:
  * time-of-check to time-of-use (TOCTOU)
  * race conditions and race-shaped security issues
  * deadlocks
  * incorrect lock ordering
  * unsynchronized shared mutable state
  * lost updates
  * "check-then-act" without proper synchronization
  * thread/async lifecycle: cancellation, shutdown, and resource release
  * timing attacks
* cryptographic compliance:
  * FIPS or other regulated crypto requirements: module usage, OpenSSL/JVM/FIPS
    mode notes when the user states them
  * deprecated algorithms: MD5, SHA-1 for signing, weak TLS (1.0/1.1), bad
    cipher suites, hardcoded keys
  * TLS version floors, cert validation bypass, insecure defaults in
    clients/servers


## Step 3: Quality - "Is it well-built?"

Check for:
* consistency:
  * backward-incompatible API changes
  * when the diff deletes code, search the codebase for references to the
    deleted code
* performance and scalability:
  * unbounded memory, CPU, or connection use
  * loading entire datasets without pagination
  * N+1 query patterns
  * accidental O(n²) patterns
  * hot-path allocations or logging
  * blocking calls in async or latency-sensitive paths
  * redundant computation
* code smells:
  * inappropriate coupling
  * leaky abstractions
  * DRY violations
  * abandoned TODO/FIXME, commented-out code, or "temporary" shortcuts left in
  * inaccurate documentation
* test quality:
  * missing test cases for success paths
  * missing tests for negative cases, error paths, and boundary tests
  * trivially passing tests
  * tests that assert on mocks instead of observable behavior
  * flaky setup, shared mutable test state
  * tests that cannot fail meaningfully
  * coverage that traces implementation details instead of requirements
* AI-generated code smells:
  * hallucinated APIs, flags, config keys or library behavior - verify against
    code / documentation
  * over-engineering or pattern drift vs. established project style
  * plausible-but-wrong logic that reads well but misses edge cases
* grammar errors and typos - suggest wording improvements
* documentation issues:
  * missing changelog entries
  * missing updates in man pages and usage / help
  * commit messages matching the actual changes

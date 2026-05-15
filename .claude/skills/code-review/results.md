# Presenting results of a code review

## Severity classification

Classify each finding by asking two questions in order:

1. What is the worst realistic outcome if this ships?
    * Exploitable vulnerability, data loss, or unrecoverable crash → Critical
    * Wrong behavior, broken functionality, or silent failure → High
    * Degraded behavior, missing edge-case handling, or increased risk of future
      bugs → Medium
    * Cosmetic issue, missing docs, or deviation from convention → Low
    * Style preference with no functional or user-visible impact → Nit
2. Is the failure silent? A defect that fails silently (no error, no log, wrong
   behavior with no indication) is one severity level higher than one that
   fails loudly (exception, build error, test failure, validation rejection).
   Silent failures reach production undetected.

## Presenting findings

Collect all findings from every review step into a single flat list sorted by
severity (Critical first, then High, Medium, Low, Nit). Do NOT group findings
by review step. The step a finding originated in is irrelevant to the reader;
only its severity matters.

Be brief and make the report information dense yet structured.

Every finding MUST quote the specific code from the diff that demonstrates the
issue. No quoted code, no finding. If you cannot point to a specific line,
convert to observation.

For each finding, specify:
* severity - Critical / High / Medium / Low / Nit
* location - file and line range (or equivalent anchor)
* finding - what is wrong or risky
* evidence - why you believe it (code path, assumption, missing case)
* suggestion - concrete fix or experiment; use "needs discussion" when
  trade-offs matter

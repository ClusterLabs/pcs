Review specified changes and point out any potential issues.

Follow these steps:
1. If not specified, ask which changes should be reviewed: the most recent
   commit(s), the current branch, a range of commits, uncommitted changes and
   untracked files. Use AskUserQuestion prompt.
2. If not specified, ask whether this is still work in progress and if so, which
   aspects should be ignored (e.g. missing tests, missing input validation).
   Use AskUserQuestion prompt.
3. Try to understand the goal of the specified changes. Verify with me that you
   understand the goal correctly before you proceed further.
4. Think hard about issues (logic errors, edge cases, race conditions, security
   issues) caused by the changes and point them out. Also check against project
   coding standards. List issues by impact, most critical first. Be brief and
   make the report information dense yet structured.
5. Check for grammar errors and typos, and suggest wording improvements.

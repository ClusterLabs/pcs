# Issues to be resolved later

## Multi-agent workflow

For the skill to be effectively useful in a multi-agent workflow, the skill's
frontmatter should contain:
```
context: fork
```
This makes the skill run in an isolated subagent to prevent overfilling the
main context. The problem is that the skill is then unable to ask the user.
Subagents cannot interact with the user - they run to completion and return
results. For now, I'm disabling forking, since we don't have a multi-agent
workflow ready yet.

Alternatively, try instructing the orchestrating agent to run this skill in an
isolated subagent.

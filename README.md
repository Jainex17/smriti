# Personal Dev Harness

An installable Claude Code plugin for autonomous MR-ready task delivery. It selects a proportionate pipeline, uses specialist agents only when useful, retains compact durable learning, and supports private/isolated sessions.

## Install once

From this marketplace root in Claude Code:

```text
/plugin marketplace add /Users/jainex/projects/arya
/plugin install personal-dev-harness@personal-dev-harness
```

Install at user scope. Start a new Claude Code session or run `/reload-plugins`. The plugin does not replace Claude Code's visible main-agent header; it activates through hooks, memory context, and the automatic routing skill.

The memory store supports Python 3.10 and newer. Hook failures are fail-open: if the local Python runtime or memory state is unavailable, Claude Code continues normally without memory context.

## Use

Start work normally; the default harness agent routes it automatically:

```text
Fix the checkout total bug. Don't ask me questions.
```

Repository setup is automatic at session start: the harness quietly discovers package managers,
scripts, browser tooling, and likely UI paths. `/personal-dev-harness:setup` is only a manual
override when you want to inspect or correct that profile.

Manage learned rules in natural language, for example: “remember simple questions should be 1–4 lines”, “show what you learned about this repository”, or “forget the old UI policy”.

The normal workflow needs no harness commands. Check the compact operational dashboard only when
you want diagnostics:

```text
/personal-dev-harness:status
```

It reports active/candidate/archived learning, recent rules, privacy, and session/cleanup counts. It
never displays raw transcripts. Housekeeping runs automatically at the end of normal sessions;
private and isolated sessions never write or clean harness memory.

For sensitive work, prefix the task with `private:` (no new learning) or `isolated:` (no memory read or write). Run `/personal-dev-harness:cleanup-memory` every 2–3 months to remove stale candidate memory and archive unused low-confidence rules.

After verified normal work, a silent curator reviews only the outcome for one conservative durable
rule (for example a small bug invariant), or does nothing. It never stores raw transcripts or
secrets. For a session where you explicitly want the full custom director agent, launch
`claude --agent personal-dev-harness:harness`; this will show the agent label by design.

## Delivery policy

The default is MR-ready: the harness works in an isolated branch/worktree, verifies the result, and returns branch, diff summary, proof, assumptions, and risk. It never creates an MR, merges, deploys, or changes production state unless explicitly authorized in the task or saved repository policy.

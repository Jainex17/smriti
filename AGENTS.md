# AGENTS.md

## What this is

`smriti` is a local Claude Code plugin marketplace with one plugin:
`smriti` — autonomous MR-ready task delivery with task routing,
subagents, durable learning (memory), and privacy controls.

- `.claude-plugin/marketplace.json` — marketplace manifest; its `version` must
  match `plugins/smriti/.claude-plugin/plugin.json` (bump both on
  behavior changes).
- `plugins/smriti/` — `agents/`, `skills/`, `hooks/hooks.json`,
  `bin/smriti-memory` (bash wrapper that execs `scripts/smriti_memory.py`),
  and stdlib-only Python `scripts/` (`smriti_memory.py` is the state store;
  `session_start.py` etc. are hook entry points).
- `tests/` — stdlib `unittest` suite.

## Commands

```bash
python3 -m unittest discover -s tests -v
```

Tests run the scripts as subprocesses with `CLAUDE_PLUGIN_DATA` set to a temp
dir; follow that pattern in new tests.

## Rules

- Python 3 stdlib only; `from __future__ import annotations` + type hints.
- Hook failures must never block user work — degrade silently and exit 0.
  On success, hook scripts emit only their hook-protocol JSON
  (`hookSpecificOutput`), never stray diagnostics.
- Tests pin the Stop-curator prompt in `hooks/hooks.json`: it must contain
  `smriti-memory remember` and `skip learning silently`, and must not contain
  `bug-invariant`. Rewording that prompt breaks the suite.
- Memory stores compact rules only (never transcripts, secrets, raw prompts).
  Canonical API: `smriti-memory remember --scope <personal|repo> --kind
  <preference|repo-fact|bug-pattern|verification|workflow|decision> --rule
  <text>`. Legacy aliases (`add --type bug-invariant --text`) are accepted and
  normalized to canonical kinds — keep them working; a test asserts it.
- Running `smriti_memory.py` without `CLAUDE_PLUGIN_DATA` writes to the
  real fallback `~/.claude/plugins/data/smriti-dev` — set it to a
  temp dir when invoking scripts by hand. Pre-rename
  `personal-dev-harness-dev` data and `harness-memory.json` state
  migrate automatically on first run.
- Privacy: `normal` (read+write), `private:` (read-only), `isolated:` (no
  memory read or write).
- MR-ready by default; never create MRs, merge, deploy, or touch production
  unless explicitly authorized.
- Keep `README.md` in sync with user-facing
  changes.

## Codex automatic smriti mode

When Codex is working in this workspace, apply smriti
automatically for every coding task. Do not require the user to invoke a skill
or repeat these instructions.

- Silently classify the task as answer, quick, standard, bug, UI, or complex/risky.
- For development work, read relevant approved memory with
  `python3 plugins/smriti/scripts/smriti_memory.py context` and
  use the current task as the query. Do not read raw transcripts.
- Use the smallest reliable workflow, verify proportionally, and report the
  verification result. UI work needs screenshot or browser evidence when the
  app can be run.
- Treat `private:` as read-only memory and `isolated:` as no memory read/write.
  Never store secrets, raw prompts, transcripts, or speculative rules.
- After successful normal work, save at most one concise, durable,
  evidence-backed rule with the canonical `remember` command; skip silently if
  memory access is unavailable.
- Keep work MR-ready by default. Never create MRs, merge, deploy, or touch
  production without explicit authorization.

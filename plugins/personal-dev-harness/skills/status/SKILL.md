---
description: Show personal development harness status, learning statistics, recent learned rules, session privacy state, repository setup, and memory cleanup candidates. Use when asked for harness status, what it learned, how much it remembers, statistics, or whether cleanup is needed.
disable-model-invocation: true
---

Run `harness-memory status --cwd "$PWD" --session "${CLAUDE_CODE_SESSION_ID:-}"` and present the result exactly as a concise three-line report. If the user invokes `/personal-dev-harness:status --verbose` or explicitly asks for detailed statistics, append `--verbose`.

The status output includes:

- active, candidate, and archived learning counts;
- personal versus current-repository scope;
- counts by learning kind, including bug patterns and preferences;
- recent active rules with their confidence and exact rule text;
- current session privacy/quarantine state;
- total sessions and modes;
- repository setup state;
- records eligible for the configured cleanup age.

Use `harness-memory status --verbose` when the user explicitly asks for detailed statistics, and `harness-memory status --json` when a machine-readable report is requested. Do not expose raw transcripts or private-session content.

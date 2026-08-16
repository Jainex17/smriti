---
description: Change smriti privacy mode for this Claude Code session. Use when asked to make work private, confidential, isolated, normal again, or to prevent smriti from learning from a task.
---

Use `smriti-memory session-mode --session "$CLAUDE_CODE_SESSION_ID" --cwd "$PWD" --mode <normal|private|isolated>`.

- `normal`: retrieve relevant memory and learn durable verified outcomes.
- `private`: retrieve relevant memory but write no learning, artifacts, or cross-session messages.
- `isolated`: retrieve no smriti memory and write nothing.

When privacy is enabled after work has begun, quarantine the whole session so earlier candidates cannot be promoted. Switching back to normal restores memory reads but keeps the current session non-learning; start a fresh session to resume learning. Confirm the selected mode in one line. This protects smriti memory only; do not claim it changes Claude Code transcript retention or provider data controls.

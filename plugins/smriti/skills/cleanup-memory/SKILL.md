---
description: Clean up stale smriti memory. Use when asked to clean, prune, minimize, audit, expire, or review memory, especially after two to three months.
disable-model-invocation: true
---

Run the memory cleanup directly because the user explicitly invoked this command.

1. Run `smriti-memory cleanup --days 90 --cwd "$PWD"`.
2. Report counts for removed candidates, archived stale active rules, and retained active rules.
3. Offer a concise list of archived rule IDs/titles only when the user asks for detail.

Cleanup removes expired/rejected/old unproven candidates and archives low-confidence active rules that have not been used or refreshed in the chosen period. It does not delete active high-confidence preferences or verified bug invariants without explicit user direction.

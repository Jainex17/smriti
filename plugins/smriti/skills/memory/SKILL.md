---
description: Manage durable smriti memory from Claude Code. Use for requests to remember, forget, list, explain, audit, or change personal preferences, repository knowledge, bug invariants, workflow rules, or verification policies.
---

Manage memory through `smriti-memory`; never ask the user to edit JSON or Markdown files.

- For an explicit preference, store one short personal rule with `kind=preference`.
- For a repository fact, scope it to the current repository.
- For a bug, store a semantic `bug-pattern` with trigger, root cause, invariant, and guardrail. Mention the relevant coverage as evidence, but do not make a test filename the rule itself.
- Before changing or deleting an existing rule, list/search matching records and explain the exact effect concisely.
- Never store secrets, personal data, raw prompts, transcripts, or a private/isolated session outcome.
- Prefer expiry/review dates for tool-specific facts and unproven candidates.

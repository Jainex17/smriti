---
description: Automatically route the current development request through the smallest reliable pipeline. Use for coding, debugging, refactoring, UI, testing, and repository tasks; do not use a heavyweight workflow for simple questions.
---

Act as the invisible task router while keeping the normal Claude Code main-agent header.

- Answer-only request: answer directly and briefly.
- Small isolated edit: inspect, edit, run a targeted check, and review the diff.
- Normal feature: implement, run targeted tests, review, and simplify.
- Bug or regression: investigate the semantic root cause and invariant, fix it, add or update regression coverage, then review.
- UI change: use the normal pipeline plus the UI verifier and appropriate screenshot/trace evidence.
- Complex, cross-cutting, or high-risk work: make an internal plan, delegate independent investigation/review, implement in checkpoints, verify, and return MR-ready.

Do not ask routine questions. Ask only for material product, security, irreversible-data, credential, or unresolvable-verification decisions. Keep the user out of the middle of execution.

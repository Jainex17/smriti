# Smriti

An installable Claude Code plugin for autonomous MR-ready task delivery. It selects a proportionate pipeline, uses specialist agents only when useful, retains compact durable learning, and supports private/isolated sessions.

## Install once

From this marketplace root in Claude Code:

```text
/plugin marketplace add /Users/jainex/projects/smriti
/plugin install smriti@smriti-plugins
```

Install at user scope. Start a new Claude Code session or run `/reload-plugins`. The plugin does not replace Claude Code's visible main-agent header; it activates through hooks, memory context, and the automatic routing skill.

The memory store supports Python 3.10 and newer. Hook failures are fail-open: if the local Python runtime or memory state is unavailable, Claude Code continues normally without memory context. Learning saved by pre-rename `personal-dev-harness` versions migrates automatically on first run.

## Use

Start work normally; the default harness agent routes it automatically:

```text
Fix the checkout total bug. Don't ask me questions.
```

Repository setup is automatic at session start: smriti quietly discovers package managers,
scripts, browser tooling, and likely UI paths. `/smriti:setup` is only a manual
override when you want to inspect or correct that profile.

Manage learned rules in natural language, for example: “remember simple questions should be 1–4 lines”, “show what you learned about this repository”, or “forget the old UI policy”.

The normal workflow needs no smriti commands. Check the compact operational dashboard only when
you want diagnostics:

```text
/smriti:status
```

It reports active/candidate/archived learning, recent rules, privacy, and session/cleanup counts. It
never displays raw transcripts. Housekeeping runs automatically at the end of normal sessions;
private and isolated sessions never write or clean smriti memory.

For sensitive work, prefix the task with `private:` (no new learning) or `isolated:` (no memory read or write). Run `/smriti:cleanup-memory` every 2–3 months to remove stale candidate memory and archive unused low-confidence rules.

After verified normal work, a silent curator reviews only the outcome for one conservative durable
rule (for example a small bug invariant), or does nothing. It never stores raw transcripts or
secrets. For a session where you explicitly want the full custom director agent, launch
`claude --agent smriti:harness`; this will show the agent label by design.

## Measure improvement over time

Run the deterministic black-box suite whenever the plugin changes:

```bash
python3 plugins/smriti/scripts/smriti_eval.py run --fail-on-regression
python3 plugins/smriti/scripts/smriti_eval.py report
```

Each contract run appends one historical snapshot to the smriti data directory. The report compares the first and latest scores and identifies case-level regressions and improvements; if the suite version changes, it marks the percentage comparison as unavailable. The ledger stores only case IDs, pass/fail scores, timing, suite version, revision, and timestamps—never prompts, transcripts, or subprocess output.

Measure harness quality from real task outcomes

The harness-quality score evaluates representative task behavior, not just plugin infrastructure:

```bash
python3 plugins/smriti/scripts/smriti_eval.py task-catalog
python3 plugins/smriti/scripts/smriti_eval.py task-score \
  --outcomes plugins/smriti/evals/harness-outcomes.example.json \
  --fail-below 0.80
python3 plugins/smriti/scripts/smriti_eval.py task-report
```

Task outcomes are structured records produced from actual harness runs. The rubric scores routing, correctness, proportionate verification and evidence, privacy, MR-ready delivery, unnecessary questions, and whether approved learning was applied. Scores are weighted partial credit, so a task can be partly successful. [harness-outcomes.example.json](plugins/smriti/evals/harness-outcomes.example.json) is only a schema fixture, not evidence of harness quality: replace its fields with a real task outcome and score it with `--scenario <scenario-id>`. Do not put prompts or transcripts in the outcome file or ledger. The rolling task report compares recent usage with earlier usage, so it becomes a meaningful “previous vs now” quality signal as real outcomes accumulate.

## Delivery policy

The default is MR-ready: smriti works in an isolated branch/worktree, verifies the result, and returns branch, diff summary, proof, assumptions, and risk. It never creates an MR, merges, deploys, or changes production state unless explicitly authorized in the task or saved repository policy.

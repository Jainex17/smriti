---
description: Run smriti's privacy-safe longitudinal evals and compare quality over time.
disable-model-invocation: true
---

Use the evaluator when asked whether smriti is improving, regressing, or how it compares with an earlier run. Use the contract suite for infrastructure health and the task rubric for actual harness behavior.

Run the stable black-box suite:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smriti_eval.py" run --fail-on-regression
```

Summarize history:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smriti_eval.py" report
```

The suite covers memory compatibility and retrieval, private/isolated privacy, fail-open hooks, and legacy state migration. Each run appends one aggregate JSONL snapshot. The ledger contains case IDs, scores, timing, suite version, revision, and timestamps only; it does not contain prompts, transcripts, or subprocess output. If the suite version changes, the report marks percentage comparisons as unavailable rather than mixing unlike benchmarks.

For harness behavior, first inspect scenarios:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smriti_eval.py" task-catalog
```

Then score structured outcomes from real runs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smriti_eval.py" task-score \
  --outcomes <outcomes.json> --scenario <scenario-id> --fail-below 0.80
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smriti_eval.py" task-report
```

The task rubric measures routing, correctness, verification, privacy, MR-ready delivery, unnecessary questions, and approved learning. It stores only case IDs, weighted scores, failed rubric labels, suite version, revision, and timestamps. It never stores prompts or transcripts. The checked-in example outcome is schema-only, not evidence. Use evidence-backed outcomes from real runs and the rolling task report to compare earlier and recent usage; the contract suite alone is not a user-quality score.

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "plugins" / "smriti" / "scripts" / "smriti_memory.py"
HOOKS = ROOT / "plugins" / "smriti" / "hooks" / "hooks.json"
SESSION_START = ROOT / "plugins" / "smriti" / "scripts" / "session_start.py"
PROMPT_CONTEXT = ROOT / "plugins" / "smriti" / "scripts" / "prompt_context.py"
SESSION_END = ROOT / "plugins" / "smriti" / "scripts" / "session_end.py"
COMPLETION_GUARD = ROOT / "plugins" / "smriti" / "scripts" / "completion_guard.py"
EVAL = ROOT / "plugins" / "smriti" / "scripts" / "smriti_eval.py"


class SmritiMemoryTests(unittest.TestCase):
    def temp_data_dir(self) -> str:
        path = Path(tempfile.mkdtemp()) / ".state"
        path.mkdir()
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)
        return str(path)

    def run_memory(self, *args: str, cwd: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(Path(cwd) / ".state")}
        return subprocess.run(
            [sys.executable, str(MEMORY), *args, "--cwd", cwd],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_legacy_curator_command_is_accepted_and_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_memory(
                "add",
                "--type",
                "bug-invariant",
                "--text",
                "Reduced motion must cancel keyframe animation.",
                cwd=directory,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("[repo/bug-pattern/medium]", result.stdout)

    def test_hook_prompt_has_canonical_command_and_silent_fallback(self) -> None:
        hooks = json.loads(HOOKS.read_text(encoding="utf-8"))
        prompt = hooks["hooks"]["Stop"][1]["hooks"][0]["prompt"]
        self.assertIn("smriti-memory remember", prompt)
        self.assertIn("skip learning silently", prompt)
        self.assertNotIn("bug-invariant", prompt)

    def test_legacy_state_file_migrates_on_first_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".state"
            state.mkdir()
            legacy = {
                "schema_version": 1,
                "profile": {"privacy_default": "normal"},
                "repositories": {},
                "memories": [
                    {
                        "id": "m-0001-legacy",
                        "scope": "personal",
                        "repo_key": None,
                        "kind": "preference",
                        "title": "Short answers",
                        "rule": "Keep simple answers to 1-4 lines.",
                        "tags": "",
                        "evidence": "",
                        "confidence": "high",
                        "status": "active",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "last_used_at": None,
                        "expires_at": None,
                    }
                ],
                "sessions": {},
            }
            (state / "harness-memory.json").write_text(json.dumps(legacy), encoding="utf-8")
            result = self.run_memory("list", "--scope", "personal", cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("m-0001-legacy", result.stdout)
            self.assertTrue((state / "smriti-memory.json").exists())
            self.assertFalse((state / "harness-memory.json").exists())

    def test_hook_entry_points_fail_open_on_invalid_input(self) -> None:
        for hook in (SESSION_START, PROMPT_CONTEXT, SESSION_END, COMPLETION_GUARD):
            result = subprocess.run(
                [sys.executable, str(hook)],
                input="{}",
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "CLAUDE_PLUGIN_DATA": self.temp_data_dir()},
            )
            self.assertEqual(result.returncode, 0, (hook, result.stderr))
            self.assertEqual(result.stdout, "")


class SmritiEvalTests(unittest.TestCase):
    def run_eval(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(EVAL), *args],
            text=True,
            capture_output=True,
            env={**os.environ, **(env or {})},
            check=False,
        )

    def test_eval_suite_passes_and_stores_only_aggregate_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "evals.jsonl"
            completed = self.run_eval("run", "--results", str(results), "--json")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            snapshot = json.loads(completed.stdout)
            self.assertEqual(snapshot["summary"], {"passed": 6, "total": 6, "score": 1.0})
            self.assertEqual(len(snapshot["cases"]), 6)
            self.assertNotIn("prompt", completed.stdout.lower())
            self.assertNotIn("transcript", completed.stdout.lower())
            self.assertEqual(len(results.read_text(encoding="utf-8").splitlines()), 1)

    def test_eval_report_tracks_previous_and_latest_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "evals.jsonl"
            first = self.run_eval("run", "--results", str(results))
            second = self.run_eval("run", "--results", str(results))
            report = self.run_eval("report", "--results", str(results), "--json")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(report.returncode, 0, report.stderr)
            summary = json.loads(report.stdout)
            self.assertEqual(summary["snapshots"], 2)
            self.assertEqual(summary["first"]["score"], 1.0)
            self.assertEqual(summary["latest"]["score"], 1.0)
            self.assertEqual(summary["score_delta"], 0.0)

    def test_eval_marks_changed_suite_versions_as_not_comparable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "evals.jsonl"
            first = self.run_eval("run", "--results", str(results), "--json")
            self.assertEqual(first.returncode, 0, first.stderr)
            historical = json.loads(results.read_text(encoding="utf-8").splitlines()[0])
            historical["suite_version"] = "0.0.0"
            results.write_text(json.dumps(historical) + "\n", encoding="utf-8")
            current = self.run_eval("run", "--results", str(results), "--json")
            self.assertEqual(current.returncode, 0, current.stderr)
            snapshot = json.loads(current.stdout)
            self.assertFalse(snapshot["comparison"]["comparable"])
            self.assertIsNone(snapshot["comparison"]["score_delta"])

    def test_harness_score_uses_task_rubric_and_keeps_outcome_details_out_of_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "evals.jsonl"
            outcomes = ROOT / "plugins" / "smriti" / "evals" / "harness-outcomes.example.json"
            completed = self.run_eval(
                "task-score",
                "--outcomes",
                str(outcomes),
                "--results",
                str(results),
                "--fail-below",
                "1.0",
                "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            snapshot = json.loads(completed.stdout)
            self.assertEqual(snapshot["kind"], "harness")
            self.assertEqual(snapshot["summary"]["score"], 1.0)
            self.assertEqual(snapshot["summary"]["scored"], 6)
            self.assertNotIn('"route"', results.read_text(encoding="utf-8"))
            self.assertNotIn("transcript", results.read_text(encoding="utf-8").lower())

    def test_harness_score_detects_privacy_regression_and_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "evals.jsonl"
            outcomes_path = Path(directory) / "outcomes.json"
            outcomes = json.loads(
                (ROOT / "plugins" / "smriti" / "evals" / "harness-outcomes.example.json").read_text(encoding="utf-8")
            )
            outcomes_path.write_text(json.dumps(outcomes), encoding="utf-8")
            baseline = self.run_eval("task-score", "--outcomes", str(outcomes_path), "--results", str(results))
            self.assertEqual(baseline.returncode, 0, baseline.stderr)
            for item in outcomes:
                if item["scenario_id"] == "privacy.private_task":
                    item["privacy"]["memory_write"] = True
            outcomes_path.write_text(json.dumps(outcomes), encoding="utf-8")
            regression = self.run_eval(
                "task-score",
                "--outcomes",
                str(outcomes_path),
                "--results",
                str(results),
                "--fail-below",
                "1.0",
                "--json",
            )
            report = self.run_eval("task-report", "--results", str(results), "--window", "1", "--json")
            self.assertEqual(regression.returncode, 1)
            self.assertEqual(report.returncode, 0, report.stderr)
            snapshot = json.loads(regression.stdout)
            self.assertLess(snapshot["summary"]["score"], 1.0)
            self.assertIn("privacy.no_memory_write", next(item for item in snapshot["cases"] if item["case_id"] == "privacy.private_task")["failed_checks"])
            history = json.loads(report.stdout)
            self.assertLess(history["latest"]["score"], history["baseline"]["score"])
            self.assertIn("privacy.private_task", history["latest_regressions"])


if __name__ == "__main__":
    unittest.main()

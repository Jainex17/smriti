#!/usr/bin/env python3
"""Run privacy-safe longitudinal evaluations for smriti.

The eval suite exercises observable plugin contracts in isolated temporary
state.  Its durable ledger stores aggregate results only: case ids, scores,
suite/revision metadata, and timestamps.  It never stores prompts, transcripts,
or subprocess output.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "smriti"
MEMORY = PLUGIN_ROOT / "scripts" / "smriti_memory.py"
HOOKS = [
    PLUGIN_ROOT / "scripts" / "session_start.py",
    PLUGIN_ROOT / "scripts" / "prompt_context.py",
    PLUGIN_ROOT / "scripts" / "session_end.py",
    PLUGIN_ROOT / "scripts" / "completion_guard.py",
]
SUITE_VERSION = "0.1.0"
HARNESS_SUITE_VERSION = "0.1.0"
UTC = timezone.utc


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def default_results_path() -> Path:
    configured = os.environ.get("CLAUDE_PLUGIN_DATA")
    if configured:
        return Path(configured) / "smriti-evals.jsonl"
    return Path.home() / ".claude" / "plugins" / "data" / "smriti-dev" / "smriti-evals.jsonl"


def run_command(
    command: list[str],
    *,
    cwd: Path,
    data_dir: Path,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(data_dir)}
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def memory(
    *args: str,
    cwd: Path,
    data_dir: Path,
) -> subprocess.CompletedProcess[str]:
    return run_command(
        [sys.executable, str(MEMORY), *args, "--cwd", str(cwd)],
        cwd=cwd,
        data_dir=data_dir,
    )


def hook(
    script: Path,
    payload: dict[str, Any],
    *,
    cwd: Path,
    data_dir: Path,
) -> subprocess.CompletedProcess[str]:
    return run_command(
        [sys.executable, str(script)],
        cwd=cwd,
        data_dir=data_dir,
        input_text=json.dumps(payload),
    )


def result(case_id: str, category: str, started: float, passed: bool, reason: str = "") -> dict[str, Any]:
    return {
        "case_id": case_id,
        "category": category,
        "passed": passed,
        "score": 1 if passed else 0,
        "duration_ms": round((time.monotonic() - started) * 1000, 1),
        **({"reason": reason} if reason else {}),
    }


def case_legacy_alias() -> dict[str, Any]:
    case_id, category, started = "memory.legacy_alias_normalizes", "compatibility", time.monotonic()
    with tempfile.TemporaryDirectory() as directory:
        data_dir = Path(directory) / "state"
        data_dir.mkdir()
        completed = memory(
            "add",
            "--type",
            "bug-invariant",
            "--text",
            "A completed task must include proportionate verification.",
            cwd=ROOT,
            data_dir=data_dir,
        )
        passed = completed.returncode == 0 and "[repo/bug-pattern/medium]" in completed.stdout
        return result(case_id, category, started, passed, "legacy alias was not normalized" if not passed else "")


def case_normal_round_trip() -> dict[str, Any]:
    case_id, category, started = "memory.normal_round_trip", "learning", time.monotonic()
    rule = "Run targeted tests before reporting a normal repository change complete."
    with tempfile.TemporaryDirectory() as directory:
        data_dir = Path(directory) / "state"
        data_dir.mkdir()
        remembered = memory(
            "remember",
            "--scope",
            "repo",
            "--kind",
            "verification",
            "--rule",
            rule,
            "--confidence",
            "high",
            cwd=ROOT,
            data_dir=data_dir,
        )
        context = memory(
            "context",
            "--query",
            "verification tests",
            cwd=ROOT,
            data_dir=data_dir,
        )
        passed = remembered.returncode == 0 and context.returncode == 0 and rule in context.stdout
        return result(case_id, category, started, passed, "normal memory could not be retrieved" if not passed else "")


def case_private_blocks_learning() -> dict[str, Any]:
    case_id, category, started = "privacy.private_blocks_learning", "privacy", time.monotonic()
    rule = "Private sessions never create durable learning."
    with tempfile.TemporaryDirectory() as directory:
        data_dir = Path(directory) / "state"
        data_dir.mkdir()
        session = "eval-private"
        started_session = memory("session-start", "--session", session, cwd=ROOT, data_dir=data_dir)
        private = memory("session-mode", "--session", session, "--mode", "private", cwd=ROOT, data_dir=data_dir)
        remembered = memory(
            "remember",
            "--session",
            session,
            "--scope",
            "repo",
            "--kind",
            "workflow",
            "--rule",
            rule,
            cwd=ROOT,
            data_dir=data_dir,
        )
        listed = memory("list", "--scope", "repo", cwd=ROOT, data_dir=data_dir)
        passed = (
            started_session.returncode == 0
            and private.returncode == 0
            and remembered.returncode == 0
            and "Memory skipped" in remembered.stdout
            and rule not in listed.stdout
        )
        return result(case_id, category, started, passed, "private mode allowed durable learning" if not passed else "")


def case_isolated_hides_memory() -> dict[str, Any]:
    case_id, category, started = "privacy.isolated_hides_memory", "privacy", time.monotonic()
    rule = "This approved rule must not be visible in an isolated session."
    with tempfile.TemporaryDirectory() as directory:
        data_dir = Path(directory) / "state"
        data_dir.mkdir()
        remembered = memory(
            "remember",
            "--scope",
            "repo",
            "--kind",
            "workflow",
            "--rule",
            rule,
            "--confidence",
            "high",
            cwd=ROOT,
            data_dir=data_dir,
        )
        session = "eval-isolated"
        started_session = memory("session-start", "--session", session, cwd=ROOT, data_dir=data_dir)
        isolated = memory("session-mode", "--session", session, "--mode", "isolated", cwd=ROOT, data_dir=data_dir)
        context = memory(
            "context",
            "--session",
            session,
            "--query",
            "approved rule",
            cwd=ROOT,
            data_dir=data_dir,
        )
        passed = (
            remembered.returncode == 0
            and started_session.returncode == 0
            and isolated.returncode == 0
            and context.returncode == 0
            and "isolated" in context.stdout
            and rule not in context.stdout
        )
        return result(case_id, category, started, passed, "isolated mode exposed approved memory" if not passed else "")


def case_hooks_fail_open() -> dict[str, Any]:
    case_id, category, started = "hooks.invalid_input_fails_open", "resilience", time.monotonic()
    with tempfile.TemporaryDirectory() as directory:
        data_dir = Path(directory) / "state"
        data_dir.mkdir()
        outcomes = [hook(script, {}, cwd=ROOT, data_dir=data_dir) for script in HOOKS]
        passed = all(item.returncode == 0 and item.stdout == "" for item in outcomes)
        return result(case_id, category, started, passed, "an invalid hook payload blocked or emitted output" if not passed else "")


def case_state_migration() -> dict[str, Any]:
    case_id, category, started = "storage.legacy_state_migrates", "compatibility", time.monotonic()
    with tempfile.TemporaryDirectory() as directory:
        data_dir = Path(directory) / "state"
        data_dir.mkdir()
        legacy = {
            "schema_version": 1,
            "profile": {"privacy_default": "normal"},
            "repositories": {},
            "memories": [
                {
                    "id": "m-eval-legacy",
                    "scope": "personal",
                    "repo_key": None,
                    "kind": "preference",
                    "title": "Compact answers",
                    "rule": "Keep simple answers compact.",
                    "tags": "",
                    "evidence": "",
                    "confidence": "high",
                    "status": "active",
                    "created_at": now(),
                    "updated_at": now(),
                    "last_used_at": None,
                    "expires_at": None,
                }
            ],
            "sessions": {},
        }
        legacy_path = data_dir / "harness-memory.json"
        current_path = data_dir / "smriti-memory.json"
        legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
        listed = memory("list", "--scope", "personal", cwd=ROOT, data_dir=data_dir)
        passed = listed.returncode == 0 and "m-eval-legacy" in listed.stdout and current_path.exists() and not legacy_path.exists()
        return result(case_id, category, started, passed, "legacy state was not migrated safely" if not passed else "")


CASE_FUNCTIONS: dict[str, Callable[[], dict[str, Any]]] = {
    "memory.legacy_alias_normalizes": case_legacy_alias,
    "memory.normal_round_trip": case_normal_round_trip,
    "privacy.private_blocks_learning": case_private_blocks_learning,
    "privacy.isolated_hides_memory": case_isolated_hides_memory,
    "hooks.invalid_input_fails_open": case_hooks_fail_open,
    "storage.legacy_state_migrates": case_state_migration,
}

CASE_DESCRIPTIONS = {
    "memory.legacy_alias_normalizes": "Legacy curator syntax remains compatible with canonical memory kinds.",
    "memory.normal_round_trip": "Approved normal-mode learning can be retrieved by a relevant query.",
    "privacy.private_blocks_learning": "Private sessions do not create durable learning.",
    "privacy.isolated_hides_memory": "Isolated sessions neither read nor expose approved memory.",
    "hooks.invalid_input_fails_open": "Malformed hook input never blocks work or emits stray output.",
    "storage.legacy_state_migrates": "Pre-rename state migrates to the current state filename.",
}


# These are behavior contracts for representative harness tasks.  The harness
# produces an outcome record after a real task; this evaluator scores the
# record without retaining the task prompt or assistant transcript.
HARNESS_SCENARIOS: dict[str, dict[str, Any]] = {
    "bug.small_regression": {
        "category": "bug",
        "description": "A small regression is investigated, fixed, and verified.",
        "checks": [
            ("routing.bug", "route", "bug", 15),
            ("correctness.pass", "correctness.status", "pass", 30),
            ("verification.proportionate", "verification.proportionate", True, 10),
            ("verification.evidence", "verification.evidence", True, 10),
            ("privacy.normal", "privacy.mode", "normal", 5),
            ("privacy.memory_read", "privacy.memory_read", True, 5),
            ("delivery.mr_ready", "delivery.mr_ready", True, 10),
            ("delivery.not_merged", "delivery.merged", False, 5),
            ("delivery.not_deployed", "delivery.deployed", False, 5),
            ("interaction.no_routine_questions", "interaction.questions_asked", 0, 5),
        ],
    },
    "feature.standard_change": {
        "category": "feature",
        "description": "A bounded feature is implemented through the standard pipeline.",
        "checks": [
            ("routing.standard", "route", "standard", 15),
            ("correctness.pass", "correctness.status", "pass", 30),
            ("verification.proportionate", "verification.proportionate", True, 10),
            ("verification.evidence", "verification.evidence", True, 10),
            ("privacy.normal", "privacy.mode", "normal", 5),
            ("privacy.memory_read", "privacy.memory_read", True, 5),
            ("delivery.mr_ready", "delivery.mr_ready", True, 10),
            ("delivery.not_merged", "delivery.merged", False, 5),
            ("delivery.not_deployed", "delivery.deployed", False, 5),
            ("interaction.no_routine_questions", "interaction.questions_asked", 0, 5),
        ],
    },
    "privacy.private_task": {
        "category": "privacy",
        "description": "A private task may read existing memory but must not write learning.",
        "checks": [
            ("routing.standard", "route", "standard", 10),
            ("correctness.pass", "correctness.status", "pass", 25),
            ("verification.proportionate", "verification.proportionate", True, 10),
            ("verification.evidence", "verification.evidence", True, 10),
            ("privacy.private", "privacy.mode", "private", 10),
            ("privacy.memory_read_only", "privacy.memory_read", True, 5),
            ("privacy.no_memory_write", "privacy.memory_write", False, 10),
            ("delivery.mr_ready", "delivery.mr_ready", True, 10),
            ("delivery.not_merged", "delivery.merged", False, 5),
            ("delivery.not_deployed", "delivery.deployed", False, 5),
            ("interaction.no_routine_questions", "interaction.questions_asked", 0, 5),
        ],
    },
    "privacy.isolated_task": {
        "category": "privacy",
        "description": "An isolated task must not read or write smriti memory.",
        "checks": [
            ("routing.standard", "route", "standard", 10),
            ("correctness.pass", "correctness.status", "pass", 25),
            ("verification.proportionate", "verification.proportionate", True, 10),
            ("verification.evidence", "verification.evidence", True, 10),
            ("privacy.isolated", "privacy.mode", "isolated", 10),
            ("privacy.no_memory_read", "privacy.memory_read", False, 10),
            ("privacy.no_memory_write", "privacy.memory_write", False, 10),
            ("delivery.mr_ready", "delivery.mr_ready", True, 10),
            ("delivery.not_merged", "delivery.merged", False, 5),
            ("delivery.not_deployed", "delivery.deployed", False, 5),
            ("interaction.no_routine_questions", "interaction.questions_asked", 0, 5),
        ],
    },
    "ui.screenshot_verified": {
        "category": "ui",
        "description": "A UI change includes browser or screenshot evidence before completion.",
        "checks": [
            ("routing.ui", "route", "ui", 15),
            ("correctness.pass", "correctness.status", "pass", 25),
            ("verification.proportionate", "verification.proportionate", True, 10),
            ("verification.evidence", "verification.evidence", True, 10),
            ("verification.screenshot", "verification.screenshot", True, 10),
            ("privacy.normal", "privacy.mode", "normal", 5),
            ("privacy.memory_read", "privacy.memory_read", True, 5),
            ("delivery.mr_ready", "delivery.mr_ready", True, 10),
            ("delivery.not_merged", "delivery.merged", False, 5),
            ("delivery.not_deployed", "delivery.deployed", False, 5),
            ("interaction.no_routine_questions", "interaction.questions_asked", 0, 5),
        ],
    },
    "learning.followup_applies_rule": {
        "category": "learning",
        "description": "A later task uses an approved durable rule without exposing raw history.",
        "checks": [
            ("routing.standard", "route", "standard", 15),
            ("correctness.pass", "correctness.status", "pass", 25),
            ("verification.proportionate", "verification.proportionate", True, 10),
            ("verification.evidence", "verification.evidence", True, 10),
            ("privacy.normal", "privacy.mode", "normal", 5),
            ("privacy.memory_read", "privacy.memory_read", True, 10),
            ("learning.applied", "learning.applied", True, 10),
            ("delivery.mr_ready", "delivery.mr_ready", True, 10),
            ("delivery.not_merged", "delivery.merged", False, 5),
            ("delivery.not_deployed", "delivery.deployed", False, 5),
            ("interaction.no_routine_questions", "interaction.questions_asked", 0, 5),
        ],
    },
}


def revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout.strip()
    except OSError:
        pass
    return "unknown"


def load_history(path: Path, kind: str = "contracts") -> list[dict[str, Any]]:
    if not path.exists():
        return []
    snapshots: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if (
                    isinstance(record, dict)
                    and isinstance(record.get("cases"), list)
                    and record.get("kind", "contracts") == kind
                ):
                    snapshots.append(record)
    except (OSError, json.JSONDecodeError):
        return []
    return snapshots


MISSING = object()


def value_at(record: dict[str, Any], path: str) -> Any:
    value: Any = record
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return MISSING
        value = value[part]
    return value


def read_outcomes(path: str) -> list[dict[str, Any]]:
    raw = sys.stdin.read() if path == "-" else Path(path).expanduser().read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if isinstance(parsed, dict) and isinstance(parsed.get("outcomes"), list):
        outcomes = parsed["outcomes"]
    elif isinstance(parsed, dict) and isinstance(parsed.get("scenario_id"), str):
        outcomes = [parsed]
    elif isinstance(parsed, list):
        outcomes = parsed
    elif isinstance(parsed, dict):
        outcomes = [{**value, "scenario_id": scenario_id} for scenario_id, value in parsed.items() if isinstance(value, dict)]
    else:
        raise ValueError("outcomes must be a JSON object or list")
    if not all(isinstance(item, dict) and isinstance(item.get("scenario_id"), str) for item in outcomes):
        raise ValueError("each outcome must be an object with a scenario_id")
    scenario_ids = [item["scenario_id"] for item in outcomes]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("outcomes must contain one record per scenario_id")
    return outcomes


def score_harness_outcomes(outcomes: list[dict[str, Any]], scenario_ids: list[str] | None = None) -> dict[str, Any]:
    requested = scenario_ids or list(HARNESS_SCENARIOS)
    unknown = sorted(set(requested) - set(HARNESS_SCENARIOS))
    if unknown:
        raise ValueError(f"unknown harness scenario: {', '.join(unknown)}")
    by_id = {item["scenario_id"]: item for item in outcomes}
    cases: list[dict[str, Any]] = []
    total_points = 0
    total_max_points = 0
    scored = 0
    for scenario_id in requested:
        scenario = HARNESS_SCENARIOS[scenario_id]
        checks = scenario["checks"]
        max_points = sum(check[3] for check in checks)
        total_max_points += max_points
        outcome = by_id.get(scenario_id)
        if outcome is None:
            cases.append(
                {
                    "case_id": scenario_id,
                    "category": scenario["category"],
                    "status": "missing",
                    "score": 0.0,
                    "points": 0,
                    "max_points": max_points,
                    "failed_checks": ["outcome.present"],
                }
            )
            continue
        scored += 1
        points = 0
        failed_checks: list[str] = []
        for check_id, path, expected, weight in checks:
            actual = value_at(outcome, path)
            if actual == expected:
                points += weight
            else:
                failed_checks.append(check_id)
        total_points += points
        cases.append(
            {
                "case_id": scenario_id,
                "category": scenario["category"],
                "status": "scored",
                "score": round(points / max_points, 4) if max_points else 0.0,
                "points": points,
                "max_points": max_points,
                "failed_checks": failed_checks,
            }
        )
    return {
        "kind": "harness",
        "schema_version": 1,
        "suite_version": HARNESS_SUITE_VERSION,
        "captured_at": now(),
        "revision": revision(),
        "cases": cases,
        "summary": {
            "score": round(total_points / total_max_points, 4) if total_max_points else 0.0,
            "points": total_points,
            "max_points": total_max_points,
            "scored": scored,
            "missing": len(requested) - scored,
            "total": len(requested),
        },
    }


def aggregate_harness_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    points = sum(item.get("summary", {}).get("points", 0) for item in snapshots)
    max_points = sum(item.get("summary", {}).get("max_points", 0) for item in snapshots)
    case_points: dict[str, list[float]] = {}
    for snapshot in snapshots:
        for case in snapshot.get("cases", []):
            if case.get("status") == "scored":
                case_points.setdefault(case["case_id"], []).append(float(case.get("score", 0.0)))
    return {
        "score": round(points / max_points, 4) if max_points else 0.0,
        "samples": len(snapshots),
        "case_scores": {
            case_id: round(sum(scores) / len(scores), 4)
            for case_id, scores in case_points.items()
            if scores
        },
    }


def comparison(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if not previous:
        return {
            "baseline": "unavailable",
            "baseline_suite_version": None,
            "comparable": False,
            "regressions": [],
            "improvements": [],
            "score_delta": None,
        }
    comparable = previous.get("suite_version") == current.get("suite_version")
    old = {item.get("case_id"): item for item in previous.get("cases", [])}
    regressions: list[str] = []
    improvements: list[str] = []
    for item in current.get("cases", []):
        case_id = item.get("case_id")
        prior = old.get(case_id, {})
        old_score = prior.get("score")
        current_score = item.get("score")
        if isinstance(old_score, (int, float)) and isinstance(current_score, (int, float)) and current_score < old_score:
            regressions.append(case_id)
        elif isinstance(old_score, (int, float)) and isinstance(current_score, (int, float)) and current_score > old_score:
            improvements.append(case_id)
    current_score = current.get("summary", {}).get("score", 0.0)
    previous_score = previous.get("summary", {}).get("score", 0.0)
    return {
        "baseline": previous.get("revision", "unknown"),
        "baseline_suite_version": previous.get("suite_version", "unknown"),
        "comparable": comparable,
        "regressions": sorted(regressions),
        "improvements": sorted(improvements),
        "score_delta": round(current_score - previous_score, 4) if comparable else None,
    }


def run_suite() -> dict[str, Any]:
    cases = [CASE_FUNCTIONS[case_id]() for case_id in CASE_FUNCTIONS]
    passed = sum(1 for item in cases if item["passed"])
    total = len(cases)
    return {
        "kind": "contracts",
        "schema_version": 1,
        "suite_version": SUITE_VERSION,
        "captured_at": now(),
        "revision": revision(),
        "cases": cases,
        "summary": {"passed": passed, "total": total, "score": round(passed / total, 4) if total else 0.0},
    }


def append_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True) + "\n")


def print_run(snapshot: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return
    summary = snapshot["summary"]
    comparison_result = snapshot["comparison"]
    print(f"Smriti eval: {summary['passed']}/{summary['total']} passed ({summary['score']:.1%})")
    print(f"Revision: {snapshot['revision']} | suite={snapshot['suite_version']}")
    if comparison_result["baseline"] == "unavailable":
        print("Previous: unavailable (this run is the baseline)")
    else:
        delta = comparison_result["score_delta"]
        change = f"{delta:+.1%}" if delta is not None else "unavailable (suite version changed)"
        print(f"Previous: {comparison_result['baseline']} | change={change}")
        print(f"Regressions: {', '.join(comparison_result['regressions']) or 'none'}")
        print(f"Improvements: {', '.join(comparison_result['improvements']) or 'none'}")
    for item in snapshot["cases"]:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"{status} {item['case_id']}")
        if item.get("reason"):
            print(f"  {item['reason']}")


def command_catalog(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps([{"case_id": key, "description": CASE_DESCRIPTIONS[key]} for key in CASE_FUNCTIONS], indent=2))
    else:
        for case_id, description in CASE_DESCRIPTIONS.items():
            print(f"{case_id}: {description}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    path = Path(args.results).expanduser() if args.results else default_results_path()
    history = load_history(path, "contracts")
    snapshot = run_suite()
    snapshot["comparison"] = comparison(snapshot, history[-1] if history else None)
    append_snapshot(path, snapshot)
    print_run(snapshot, as_json=args.json)
    if snapshot["summary"]["passed"] != snapshot["summary"]["total"]:
        return 1
    if args.fail_on_regression and snapshot["comparison"]["regressions"]:
        return 2
    return 0


def command_report(args: argparse.Namespace) -> int:
    path = Path(args.results).expanduser() if args.results else default_results_path()
    history = load_history(path)
    if not history:
        print("No smriti eval history found.", file=sys.stderr)
        return 2
    selected = history[-max(1, args.limit):]
    first = selected[0]
    latest = selected[-1]
    first_score = first.get("summary", {}).get("score", 0.0)
    latest_score = latest.get("summary", {}).get("score", 0.0)
    comparable = first.get("suite_version") == latest.get("suite_version")
    report = {
        "snapshots": len(history),
        "shown": len(selected),
        "first": {"captured_at": first.get("captured_at"), "revision": first.get("revision"), "score": first_score},
        "latest": {"captured_at": latest.get("captured_at"), "revision": latest.get("revision"), "score": latest_score},
        "comparable": comparable,
        "score_delta": round(latest_score - first_score, 4) if comparable else None,
        "latest_regressions": latest.get("comparison", {}).get("regressions", []),
        "latest_improvements": latest.get("comparison", {}).get("improvements", []),
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Smriti eval history: {report['snapshots']} snapshots")
        print(f"First: {first_score:.1%} ({first.get('revision', 'unknown')})")
        print(f"Latest: {latest_score:.1%} ({latest.get('revision', 'unknown')})")
        change = f"{report['score_delta']:+.1%}" if report["score_delta"] is not None else "unavailable (suite version changed)"
        print(f"Change: {change}")
        print(f"Latest regressions: {', '.join(report['latest_regressions']) or 'none'}")
        print(f"Latest improvements: {', '.join(report['latest_improvements']) or 'none'}")
    return 0


def command_task_catalog(args: argparse.Namespace) -> int:
    catalog = [
        {
            "scenario_id": scenario_id,
            "category": scenario["category"],
            "description": scenario["description"],
            "checks": [check[0] for check in scenario["checks"]],
        }
        for scenario_id, scenario in HARNESS_SCENARIOS.items()
    ]
    if args.json:
        print(json.dumps(catalog, indent=2))
    else:
        for item in catalog:
            print(f"{item['scenario_id']} [{item['category']}]: {item['description']}")
            print(f"  checks: {', '.join(item['checks'])}")
    return 0


def print_task_score(snapshot: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return
    summary = snapshot["summary"]
    print(
        f"Smriti harness quality: {summary['score']:.1%} "
        f"({summary['scored']}/{summary['total']} scenarios scored)"
    )
    print(f"Revision: {snapshot['revision']} | suite={snapshot['suite_version']}")
    comparison_result = snapshot["comparison"]
    if comparison_result["baseline"] == "unavailable":
        print("Previous: unavailable (this run is the baseline)")
    else:
        delta = comparison_result["score_delta"]
        change = f"{delta:+.1%}" if delta is not None else "unavailable (suite version changed)"
        print(f"Previous: {comparison_result['baseline']} | change={change}")
        print(f"Regressions: {', '.join(comparison_result['regressions']) or 'none'}")
        print(f"Improvements: {', '.join(comparison_result['improvements']) or 'none'}")
    for item in snapshot["cases"]:
        failed = f"; failed: {', '.join(item['failed_checks'])}" if item["failed_checks"] else ""
        print(f"{item['status'].upper()} {item['case_id']}: {item['score']:.1%}{failed}")


def command_task_score(args: argparse.Namespace) -> int:
    try:
        outcomes = read_outcomes(args.outcomes)
        scenario_ids = [args.scenario] if args.scenario else None
        snapshot = score_harness_outcomes(outcomes, scenario_ids)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Could not score harness outcomes: {error}", file=sys.stderr)
        return 2
    path = Path(args.results).expanduser() if args.results else default_results_path()
    history = load_history(path, "harness")
    snapshot["comparison"] = comparison(snapshot, history[-1] if history else None)
    append_snapshot(path, snapshot)
    print_task_score(snapshot, as_json=args.json)
    if args.fail_below is not None and snapshot["summary"]["score"] < args.fail_below:
        return 1
    return 0


def command_task_report(args: argparse.Namespace) -> int:
    path = Path(args.results).expanduser() if args.results else default_results_path()
    history = load_history(path, "harness")
    if not history:
        print("No harness eval history found.", file=sys.stderr)
        return 2
    window = max(1, args.window)
    baseline_snapshots = history[:window]
    latest_snapshots = history[-window:]
    baseline = aggregate_harness_snapshots(baseline_snapshots)
    latest = aggregate_harness_snapshots(latest_snapshots)
    comparable = len({item.get("suite_version") for item in baseline_snapshots + latest_snapshots}) == 1
    regressions: list[str] = []
    improvements: list[str] = []
    for case_id in sorted(set(baseline["case_scores"]) | set(latest["case_scores"])):
        old_score = baseline["case_scores"].get(case_id)
        new_score = latest["case_scores"].get(case_id)
        if old_score is not None and new_score is not None and new_score < old_score:
            regressions.append(case_id)
        elif old_score is not None and new_score is not None and new_score > old_score:
            improvements.append(case_id)
    report = {
        "snapshots": len(history),
        "window": window,
        "comparable": comparable,
        "baseline": baseline,
        "latest": latest,
        "score_delta": round(latest["score"] - baseline["score"], 4) if comparable else None,
        "latest_regressions": regressions,
        "latest_improvements": improvements,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Smriti harness quality history: {report['snapshots']} snapshots")
        print(f"Baseline ({len(baseline_snapshots)} snapshots): {baseline['score']:.1%}")
        print(f"Latest ({len(latest_snapshots)} snapshots): {latest['score']:.1%}")
        change = f"{report['score_delta']:+.1%}" if report["score_delta"] is not None else "unavailable (suite version changed)"
        print(f"Change: {change}")
        print(f"Latest regressions: {', '.join(regressions) or 'none'}")
        print(f"Latest improvements: {', '.join(improvements) or 'none'}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Privacy-safe longitudinal evals for smriti")
    sub = root.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser("catalog", help="List stable eval cases")
    catalog.add_argument("--json", action="store_true")
    catalog.set_defaults(func=command_catalog)

    run = sub.add_parser("run", help="Run the suite and append one aggregate snapshot")
    run.add_argument("--results", help="JSONL ledger path; defaults to the smriti data directory")
    run.add_argument("--fail-on-regression", action="store_true")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=command_run)

    report = sub.add_parser("report", help="Summarize previous, current, and latest eval history")
    report.add_argument("--results", help="JSONL ledger path; defaults to the smriti data directory")
    report.add_argument("--limit", type=int, default=20)
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=command_report)

    task_catalog = sub.add_parser("task-catalog", help="List harness behavior scenarios and rubric checks")
    task_catalog.add_argument("--json", action="store_true")
    task_catalog.set_defaults(func=command_task_catalog)

    task_score = sub.add_parser("task-score", help="Score structured outcomes from real harness tasks")
    task_score.add_argument("--outcomes", required=True, help="JSON file, JSONL-equivalent list, or - for stdin")
    task_score.add_argument("--scenario", choices=sorted(HARNESS_SCENARIOS), help="Score only one scenario")
    task_score.add_argument("--results", help="JSONL ledger path; defaults to the smriti data directory")
    task_score.add_argument("--fail-below", type=float, help="Return failure when the quality score is below this fraction")
    task_score.add_argument("--json", action="store_true")
    task_score.set_defaults(func=command_task_score)

    task_report = sub.add_parser("task-report", help="Report longitudinal harness-quality scores")
    task_report.add_argument("--results", help="JSONL ledger path; defaults to the smriti data directory")
    task_report.add_argument("--window", type=int, default=5, help="Snapshots in each baseline/latest rolling window")
    task_report.add_argument("--json", action="store_true")
    task_report.set_defaults(func=command_task_report)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

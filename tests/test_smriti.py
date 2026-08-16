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


if __name__ == "__main__":
    unittest.main()

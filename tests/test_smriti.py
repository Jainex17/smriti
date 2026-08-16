from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "plugins" / "personal-dev-harness" / "scripts" / "harness_memory.py"
HOOKS = ROOT / "plugins" / "personal-dev-harness" / "hooks" / "hooks.json"
SESSION_START = ROOT / "plugins" / "personal-dev-harness" / "scripts" / "session_start.py"
PROMPT_CONTEXT = ROOT / "plugins" / "personal-dev-harness" / "scripts" / "prompt_context.py"
SESSION_END = ROOT / "plugins" / "personal-dev-harness" / "scripts" / "session_end.py"
COMPLETION_GUARD = ROOT / "plugins" / "personal-dev-harness" / "scripts" / "completion_guard.py"


class HarnessMemoryTests(unittest.TestCase):
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
        self.assertIn("harness-memory remember", prompt)
        self.assertIn("skip learning silently", prompt)
        self.assertNotIn("bug-invariant", prompt)

    def test_hook_entry_points_fail_open_on_invalid_input(self) -> None:
        for hook in (SESSION_START, PROMPT_CONTEXT, SESSION_END, COMPLETION_GUARD):
            result = subprocess.run(
                [sys.executable, str(hook)],
                input="{}",
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, (hook, result.stderr))
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()

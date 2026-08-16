#!/usr/bin/env python3
"""Inject relevant memory per prompt without retaining the prompt."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def run_memory(*args: str) -> str:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parents[1])
    command = ["python3", os.path.join(root, "scripts", "smriti_memory.py"), *args]
    return subprocess.check_output(command, text=True, env=os.environ.copy()).strip()


def desired_mode(prompt: str) -> str | None:
    normalized = prompt.strip().lower()
    if re.match(r"^(private|confidential)\s*:", normalized) or "make this session private" in normalized:
        return "private"
    if re.match(r"^(isolated|clean room)\s*:", normalized) or "make this session isolated" in normalized:
        return "isolated"
    if "make this session normal" in normalized:
        return "normal"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        session = payload["session_id"]
        cwd = payload["cwd"]
        prompt = payload.get("prompt", "")
        mode = desired_mode(prompt)
        if mode:
            run_memory("session-mode", "--session", session, "--cwd", cwd, "--mode", mode)
        context = run_memory("context", "--session", session, "--cwd", cwd, "--query", prompt, "--limit", "6")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}))
    except Exception:
        # Context injection is best-effort and must never interrupt user work.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

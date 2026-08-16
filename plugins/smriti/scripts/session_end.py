#!/usr/bin/env python3
"""Keep only session metadata; never copy the transcript into harness storage."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    # Session learning is written explicitly by the harness agent only after verified work.
    # This hook deliberately does not inspect or persist transcript contents.
    if os.environ.get("CLAUDE_PLUGIN_DATA"):
        marker = os.path.join(os.environ["CLAUDE_PLUGIN_DATA"], "last-session.json")
        record = {"session_id": payload.get("session_id"), "ended_at": payload.get("timestamp"), "reason": payload.get("reason")}
        try:
            with open(marker, "w", encoding="utf-8") as handle:
                json.dump(record, handle)
        except OSError:
            # Session cleanup is best-effort and must never interrupt Claude Code.
            pass
    # Automatic housekeeping is allowed only after we know the session was normal.
    # Private/isolated sessions never mutate harness memory.
    try:
        root = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parents[1])
        memory = Path(root) / "scripts" / "harness_memory.py"
        session = payload.get("session_id") or ""
        report = subprocess.check_output(
            ["python3", str(memory), "status", "--cwd", payload.get("cwd", os.getcwd()), "--session", session, "--json"],
            text=True,
            env=os.environ.copy(),
        )
        if json.loads(report).get("current_session", {}).get("mode") == "normal":
            subprocess.run(["python3", str(memory), "cleanup", "--days", "90"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

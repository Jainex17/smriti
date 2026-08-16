#!/usr/bin/env python3
"""One deterministic completion nudge for changed repositories.

It intentionally avoids judging code quality; Claude/the specialist agents do that.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


UI_SUFFIXES = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".html"}


def changed_files(cwd: str) -> list[str]:
    paths: set[str] = set()
    try:
        output = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=cwd, text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        try:
            output = subprocess.check_output(["git", "diff", "--name-only"], cwd=cwd, text=True, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError):
            output = ""
    paths.update(line for line in output.splitlines() if line)
    try:
        untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=cwd, text=True, stderr=subprocess.DEVNULL)
        paths.update(line for line in untracked.splitlines() if line)
    except (OSError, subprocess.CalledProcessError):
        pass
    return sorted(paths)


def is_ui_change(paths: list[str]) -> bool:
    return any(os.path.splitext(path)[1].lower() in UI_SUFFIXES or any(part in path.lower() for part in ("/components/", "/pages/", "/app/")) for path in paths)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("stop_hook_active"):
        return 0
    # Read-only status/memory commands can run while a repository has unrelated dirty files.
    # They do not need a code-verification gate.
    last_message = payload.get("last_assistant_message", "").lower()
    if any(marker in last_message for marker in ("personal dev harness status", "harness status", "cleanup candidates", "memory:", "learned:")):
        return 0
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return 0
    paths = changed_files(cwd)
    if not paths:
        return 0
    has_verification = any(token in last_message for token in ("verified:", "test", "lint", "typecheck", "build"))
    has_ui_evidence = any(token in last_message for token in ("screenshot", "trace", "video", ".png", ".zip"))
    missing = []
    if not has_verification:
        missing.append("run proportionate verification and include its result")
    if is_ui_change(paths) and not has_ui_evidence:
        missing.append("verify the UI change and capture a screenshot or explain why it is not runnable")
    if not missing:
        return 0
    print(json.dumps({"decision": "block", "reason": "Before completing, " + " and ".join(missing) + ". Then return the MR-ready result."}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

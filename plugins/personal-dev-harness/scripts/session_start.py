#!/usr/bin/env python3
"""Initialize a harness session and inject compact approved memory."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_memory(*args: str) -> str:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(Path(__file__).resolve().parents[1])
    command = ["python3", os.path.join(root, "scripts", "harness_memory.py"), *args]
    return subprocess.check_output(command, text=True, env=os.environ.copy()).strip()


def discover_repo(cwd: str) -> dict[str, object]:
    """Build a conservative repo profile without asking the user anything."""
    root = Path(cwd)
    profile: dict[str, object] = {"auto_discovered": True}
    package = root / "package.json"
    if package.exists():
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
            if isinstance(scripts, dict):
                profile["package_scripts"] = {key: value for key, value in scripts.items() if key in {"test", "lint", "typecheck", "build", "check", "format"}}
        except (OSError, json.JSONDecodeError):
            pass
        locks = [("pnpm", "pnpm-lock.yaml"), ("yarn", "yarn.lock"), ("bun", "bun.lockb"), ("npm", "package-lock.json")]
        profile["package_manager"] = next((name for name, filename in locks if (root / filename).exists()), "npm")
    for filename, manager in (("pyproject.toml", "python"), ("Cargo.toml", "cargo"), ("Makefile", "make")):
        if (root / filename).exists():
            profile.setdefault("project_types", []).append(manager)
    browser = [name for name in ("playwright.config.ts", "playwright.config.js", "cypress.config.ts", "cypress.config.js") if (root / name).exists()]
    if browser:
        profile["browser_tools"] = browser
    ui_dirs = [str(path.relative_to(root)) for path in (root / "src", root / "app", root / "pages", root / "components") if path.is_dir()]
    if ui_dirs:
        profile["ui_paths"] = ui_dirs
    return profile


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        session = payload["session_id"]
        cwd = payload["cwd"]
        run_memory("session-start", "--session", session, "--cwd", cwd)
        # Repo discovery is idempotent and intentionally silent: normal use should not need /setup.
        run_memory("configure-repo", "--cwd", cwd, "--json", json.dumps(discover_repo(cwd), separators=(",", ":")))
        policy = (
            "Personal development loop is active without replacing the normal Claude Code main agent. "
            "Silently classify each task as answer, quick, standard, bug, UI, or complex/risky; use the smallest reliable pipeline. "
            "Do not ask routine questions. Work to MR-ready, verify proportionally, and ask only material product/security/data/credential blockers."
        )
        context = policy + "\n" + run_memory("context", "--session", session, "--cwd", cwd, "--query", "development workflow verification")
        env_file = os.environ.get("CLAUDE_ENV_FILE")
        if env_file:
            with open(env_file, "a", encoding="utf-8") as handle:
                handle.write(f"export CLAUDE_CODE_SESSION_ID={session!r}\n")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))
    except Exception:
        # Hooks are an enhancement; a broken runtime or unavailable state store
        # must never block Claude Code or emit stray diagnostics.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

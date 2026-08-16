#!/usr/bin/env python3
"""Small local state store for smriti.

The store intentionally contains compact, reviewable rules rather than raw transcripts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Claude Code's supported Unix platforms have fcntl.
    fcntl = None


SCHEMA_VERSION = 1
MEMORY_KINDS = {"preference", "repo-fact", "bug-pattern", "verification", "workflow", "decision"}
# Keep accepting the names used by early curator prompts.  The canonical API
# remains `remember --kind bug-pattern`; these aliases prevent a stale prompt
# from turning a best-effort Stop hook into a user-visible failure.
MEMORY_KIND_ALIASES = {"bug-invariant": "bug-pattern"}
MODES = {"normal", "private", "isolated"}
WORD_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,}", re.IGNORECASE)
# `datetime.UTC` was added in Python 3.11.  Claude Code installations may
# still resolve `python3` to Python 3.10, so use the compatible spelling.
UTC = timezone.utc


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


LEGACY_DATA_DIR_NAME = "personal-dev-harness-dev"


def data_dir() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_DATA")
    if raw:
        root = Path(raw)
    else:
        base = Path.home() / ".claude" / "plugins" / "data"
        root = base / "smriti-dev"
        legacy = base / LEGACY_DATA_DIR_NAME
        if legacy.is_dir() and not root.exists():
            # Carry over durable learning written before the plugin was renamed.
            try:
                os.rename(legacy, root)
            except OSError:
                root = legacy
    try:
        root.mkdir(parents=True, exist_ok=True)
        return root
    except OSError:
        # A hook must never block the development task when plugin state is unavailable.
        # The fallback is ephemeral and should not be treated as durable learning.
        fallback = Path(tempfile.gettempdir()) / "smriti-runtime"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def state_path() -> Path:
    path = data_dir() / "smriti-memory.json"
    legacy = path.with_name("harness-memory.json")
    if legacy.exists() and not path.exists():
        try:
            os.rename(legacy, path)
        except OSError:
            return legacy
    return path


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile": {"privacy_default": "normal"},
        "repositories": {},
        "memories": [],
        "sessions": {},
    }


@contextmanager
def locked_state(write: bool = False):
    path = state_path()
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a+") as lock_file:
        if fcntl:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if path.exists():
                try:
                    state = json.loads(path.read_text())
                except (OSError, json.JSONDecodeError):
                    state = empty_state()
            else:
                state = empty_state()
            yield state
            if write:
                fd, tmp_name = tempfile.mkstemp(prefix="smriti-memory-", suffix=".json", dir=path.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(state, handle, indent=2, sort_keys=True)
                        handle.write("\n")
                    os.replace(tmp_name, path)
                finally:
                    if os.path.exists(tmp_name):
                        os.unlink(tmp_name)
        finally:
            if fcntl:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def repository_key(cwd: str) -> str:
    root = str(Path(cwd).resolve())
    digest = hashlib.sha256(root.encode()).hexdigest()[:16]
    return f"repo-{digest}"


def ensure_repository(state: dict[str, Any], cwd: str) -> tuple[str, dict[str, Any]]:
    key = repository_key(cwd)
    repositories = state.setdefault("repositories", {})
    repo = repositories.setdefault(
        key,
        {
            "key": key,
            "path_hint": str(Path(cwd).resolve()),
            "config": {},
            "created_at": now(),
            "updated_at": now(),
        },
    )
    repo["path_hint"] = str(Path(cwd).resolve())
    repo["updated_at"] = now()
    return key, repo


def token_set(text: str) -> set[str]:
    return {token.lower() for token in WORD_RE.findall(text)}


def memory_text(memory: dict[str, Any]) -> str:
    parts = [memory.get("title", ""), memory.get("rule", ""), memory.get("tags", ""), memory.get("kind", "")]
    return " ".join(parts)


def scored_memories(state: dict[str, Any], cwd: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
    repo_key = repository_key(cwd)
    query_tokens = token_set(query)
    result: list[tuple[int, dict[str, Any]]] = []
    for memory in state.get("memories", []):
        if memory.get("status") != "active":
            continue
        if memory.get("scope") == "repo" and memory.get("repo_key") != repo_key:
            continue
        expiry = parse_time(memory.get("expires_at"))
        if expiry and expiry < datetime.now(UTC):
            continue
        memory_tokens = token_set(memory_text(memory))
        overlap = len(query_tokens & memory_tokens)
        if query_tokens and overlap == 0:
            continue
        score = overlap * 10 + {"high": 3, "medium": 2, "low": 1}.get(memory.get("confidence"), 1)
        result.append((score, memory))
    result.sort(key=lambda item: (item[0], item[1].get("updated_at", "")), reverse=True)
    selected = [memory for _, memory in result[:limit]]
    for memory in selected:
        memory["last_used_at"] = now()
    return selected


def baseline_memories(state: dict[str, Any], cwd: str, limit: int = 4) -> list[dict[str, Any]]:
    """Return the few rules that should apply before a task gives us search terms."""
    repo_key = repository_key(cwd)
    result: list[dict[str, Any]] = []
    for memory in state.get("memories", []):
        if memory.get("status") != "active":
            continue
        if memory.get("scope") == "repo" and memory.get("repo_key") != repo_key:
            continue
        if memory.get("scope") == "personal" and memory.get("kind") == "preference":
            result.append(memory)
        elif memory.get("scope") == "repo" and memory.get("kind") in {"workflow", "verification"}:
            result.append(memory)
    result.sort(key=lambda memory: (memory.get("confidence") == "high", memory.get("updated_at", "")), reverse=True)
    return result[:limit]


def create_memory_id(state: dict[str, Any]) -> str:
    return f"m-{len(state.get('memories', [])) + 1:04d}-{hashlib.sha1(now().encode()).hexdigest()[:6]}"


def render_memory(memory: dict[str, Any]) -> str:
    title = memory.get("title") or memory.get("rule", "")[:72]
    return f"{memory['id']} [{memory.get('scope')}/{memory.get('kind')}/{memory.get('confidence')}]: {title}"


def command_context(args: argparse.Namespace) -> int:
    with locked_state(write=True) as state:
        session = state.get("sessions", {}).get(args.session, {}) if args.session else {}
        mode = session.get("mode", state.get("profile", {}).get("privacy_default", "normal"))
        quarantined = session.get("quarantined", False)
        if mode == "isolated":
            print("Smriti mode: isolated. Do not retrieve or write smriti memory for this session.")
            return 0
        memories = scored_memories(state, args.cwd, args.query or "", args.limit)
        if not args.query:
            memories = baseline_memories(state, args.cwd, args.limit)
        lines = [f"Smriti mode: {mode}{' (quarantined)' if quarantined else ''}."]
        if mode == "private" or quarantined:
            lines.append("Do not write smriti learning, retain artifacts, or send cross-session messages.")
        if memories:
            lines.append("Relevant approved memory:")
            for memory in memories:
                lines.append(f"- {memory.get('rule')}")
        else:
            lines.append("No matching approved memory.")
        print("\n".join(lines))
    return 0


def command_session_start(args: argparse.Namespace) -> int:
    with locked_state(write=True) as state:
        repo_key, _ = ensure_repository(state, args.cwd)
        sessions = state.setdefault("sessions", {})
        existing = sessions.get(args.session, {})
        mode = existing.get("mode", state.get("profile", {}).get("privacy_default", "normal"))
        sessions[args.session] = {
            "id": args.session,
            "repo_key": repo_key,
            "mode": mode,
            "quarantined": existing.get("quarantined", False),
            "started_at": existing.get("started_at", now()),
            "updated_at": now(),
        }
        print(f"Smriti session initialized in {mode} mode.")
    return 0


def command_session_mode(args: argparse.Namespace) -> int:
    with locked_state(write=True) as state:
        repo_key, _ = ensure_repository(state, args.cwd)
        session_id = args.session or os.environ.get("CLAUDE_CODE_SESSION_ID")
        if not session_id:
            raise SystemExit("A session id is required; invoke this from Claude Code or pass --session.")
        session = state.setdefault("sessions", {}).setdefault(session_id, {"id": session_id, "repo_key": repo_key, "started_at": now()})
        session["mode"] = args.mode
        session["updated_at"] = now()
        if args.mode in {"private", "isolated"}:
            session["quarantined"] = True
        print(f"Session {session_id[:8]} is now {args.mode}." )
    return 0


def command_configure_repo(args: argparse.Namespace) -> int:
    config = json.loads(args.json) if args.json else {}
    if not isinstance(config, dict):
        raise SystemExit("--json must be a JSON object")
    with locked_state(write=True) as state:
        _, repo = ensure_repository(state, args.cwd)
        repo.setdefault("config", {}).update(config)
        repo["updated_at"] = now()
        print(json.dumps(repo["config"], indent=2, sort_keys=True))
    return 0


def command_show_config(args: argparse.Namespace) -> int:
    with locked_state() as state:
        repo = state.get("repositories", {}).get(repository_key(args.cwd), {})
        print(json.dumps(repo.get("config", {}), indent=2, sort_keys=True))
    return 0


def command_remember(args: argparse.Namespace) -> int:
    requested_kind = args.kind
    kind = MEMORY_KIND_ALIASES.get(requested_kind, requested_kind)
    if kind not in MEMORY_KINDS:
        raise SystemExit(f"Unknown memory kind: {requested_kind}")
    with locked_state(write=True) as state:
        repo_key, _ = ensure_repository(state, args.cwd)
        session = state.get("sessions", {}).get(args.session or os.environ.get("CLAUDE_CODE_SESSION_ID"), {})
        if session.get("mode") in {"private", "isolated"} or session.get("quarantined"):
            print("Memory skipped: this session is private or isolated.")
            return 0
        record = {
            "id": create_memory_id(state),
            "scope": args.scope,
            "repo_key": repo_key if args.scope == "repo" else None,
            "kind": kind,
            "title": args.title or args.rule[:80],
            "rule": args.rule.strip(),
            "tags": args.tags.strip(),
            "evidence": args.evidence.strip(),
            "confidence": args.confidence,
            "status": "active" if args.confidence in {"medium", "high"} else "candidate",
            "created_at": now(),
            "updated_at": now(),
            "last_used_at": None,
            "expires_at": args.expires_at or None,
        }
        state.setdefault("memories", []).append(record)
        print(render_memory(record))
    return 0


def command_search(args: argparse.Namespace) -> int:
    with locked_state(write=True) as state:
        memories = scored_memories(state, args.cwd, args.query, args.limit)
        if not memories:
            print("No matching approved memory.")
            return 0
        for memory in memories:
            print(render_memory(memory))
            print(f"  {memory.get('rule')}")
            if memory.get("evidence"):
                print(f"  Evidence: {memory['evidence']}")
    return 0


def command_list(args: argparse.Namespace) -> int:
    with locked_state() as state:
        repo_key = repository_key(args.cwd)
        for memory in state.get("memories", []):
            if args.scope and memory.get("scope") != args.scope:
                continue
            if memory.get("scope") == "repo" and memory.get("repo_key") != repo_key:
                continue
            if args.status and memory.get("status") != args.status:
                continue
            print(render_memory(memory))
            print(f"  {memory.get('rule')}")
    return 0


def command_forget(args: argparse.Namespace) -> int:
    with locked_state(write=True) as state:
        for memory in state.get("memories", []):
            if memory.get("id") == args.id:
                memory["status"] = "archived"
                memory["updated_at"] = now()
                print(f"Archived {args.id}.")
                return 0
    raise SystemExit(f"No memory with id {args.id}")


def command_cleanup(args: argparse.Namespace) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=args.days)
    removed = 0
    archived = 0
    retained = 0
    with locked_state(write=True) as state:
        kept: list[dict[str, Any]] = []
        for memory in state.get("memories", []):
            updated = parse_time(memory.get("updated_at")) or datetime.now(UTC)
            last_used = parse_time(memory.get("last_used_at")) or updated
            expiry = parse_time(memory.get("expires_at"))
            status = memory.get("status")
            if status in {"candidate", "rejected"} and updated < cutoff:
                removed += 1
                continue
            if expiry and expiry < datetime.now(UTC):
                removed += 1
                continue
            if (
                status == "active"
                and memory.get("confidence") == "low"
                and last_used < cutoff
                and memory.get("kind") not in {"preference", "bug-pattern"}
            ):
                memory["status"] = "archived"
                memory["updated_at"] = now()
                archived += 1
            if memory.get("status") == "active":
                retained += 1
            kept.append(memory)
        state["memories"] = kept
    print(json.dumps({"removed": removed, "archived": archived, "active_retained": retained, "period_days": args.days}))
    return 0


def command_set_default_privacy(args: argparse.Namespace) -> int:
    with locked_state(write=True) as state:
        state.setdefault("profile", {})["privacy_default"] = args.mode
        print(f"Default privacy mode is now {args.mode}.")
    return 0


def command_status(args: argparse.Namespace) -> int:
    """Show compact operational and learning statistics without changing state."""
    with locked_state() as state:
        repo_key = repository_key(args.cwd)
        session_id = args.session or os.environ.get("CLAUDE_CODE_SESSION_ID")
        session = state.get("sessions", {}).get(session_id, {}) if session_id else {}
        memories = state.get("memories", [])
        current_memories = [
            memory for memory in memories
            if memory.get("scope") == "personal"
            or (memory.get("scope") == "repo" and memory.get("repo_key") == repo_key)
        ]
        status_counts = Counter(memory.get("status", "unknown") for memory in current_memories)
        kind_counts = Counter(memory.get("kind", "unknown") for memory in current_memories if memory.get("status") == "active")
        scope_counts = Counter(memory.get("scope", "unknown") for memory in current_memories if memory.get("status") == "active")
        cutoff = datetime.now(UTC) - timedelta(days=args.days)
        cleanup_candidates = 0
        for memory in current_memories:
            updated = parse_time(memory.get("updated_at")) or datetime.now(UTC)
            last_used = parse_time(memory.get("last_used_at")) or updated
            expiry = parse_time(memory.get("expires_at"))
            if (memory.get("status") in {"candidate", "rejected"} and updated < cutoff) or (expiry and expiry < datetime.now(UTC)):
                cleanup_candidates += 1
            elif memory.get("status") == "active" and memory.get("confidence") == "low" and last_used < cutoff:
                cleanup_candidates += 1
        active = [memory for memory in current_memories if memory.get("status") == "active"]
        active.sort(key=lambda memory: memory.get("updated_at", ""), reverse=True)
        sessions = list(state.get("sessions", {}).values())
        sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        session_modes = Counter(item.get("mode", "normal") for item in sessions)
        repo = state.get("repositories", {}).get(repo_key, {})
        result = {
            "current_repo": args.cwd,
            "current_repo_configured": bool(repo.get("config")),
            "current_session": {
                "id": session_id,
                "mode": session.get("mode", state.get("profile", {}).get("privacy_default", "normal")),
                "quarantined": bool(session.get("quarantined")),
            },
            "memory": {
                "active": status_counts.get("active", 0),
                "candidate": status_counts.get("candidate", 0),
                "archived": status_counts.get("archived", 0),
                "by_scope": dict(scope_counts),
                "by_kind": dict(kind_counts),
                "cleanup_candidates": cleanup_candidates,
                "recent_active": [
                    {
                        "id": memory.get("id"),
                        "kind": memory.get("kind"),
                        "scope": memory.get("scope"),
                        "confidence": memory.get("confidence"),
                        "title": memory.get("title"),
                        "rule": memory.get("rule"),
                        "updated_at": memory.get("updated_at"),
                    }
                    for memory in active[:args.limit]
                ],
            },
            "sessions": {
                "total": len(sessions),
                "by_mode": dict(session_modes),
                "recent": [
                    {"id": item.get("id"), "mode": item.get("mode"), "updated_at": item.get("updated_at")}
                    for item in sessions[:args.limit]
                ],
            },
            "privacy_default": state.get("profile", {}).get("privacy_default", "normal"),
            "cleanup_days": args.days,
        }
        memory = result["memory"]
        sessions_result = result["sessions"]
        current = result["current_session"]
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if not args.verbose:
            scope_text = ", ".join(f"{key}={value}" for key, value in sorted(memory["by_scope"].items())) or "none"
            kind_text = ", ".join(f"{key}={value}" for key, value in sorted(memory["by_kind"].items())) or "none"
            current_session = "current active" if session_id and not session else "current recorded"
            recent = memory["recent_active"][:3]
            recent_text = "; ".join(f"{item['kind']}: {item['title']}" for item in recent) or "none yet"
            cleanup_text = f"{memory['cleanup_candidates']} due" if memory["cleanup_candidates"] else "none due"
            print(f"Smriti: {memory['active']} active, {memory['candidate']} candidates, {memory['archived']} archived | {scope_text} | mode={current['mode']}")
            print(f"Learned: {recent_text}")
            print(f"Kinds: {kind_text} | sessions: {sessions_result['total']} saved ({current_session}) | cleanup: {cleanup_text} ({args.days}d)")
            return 0
        print("Smriti status")
        print(f"Repo: {args.cwd} ({'configured' if result['current_repo_configured'] else 'not configured'})")
        print(f"Session: {str(current['id'])[:12] if current['id'] else 'unknown'} | mode={current['mode']}{' | quarantined' if current['quarantined'] else ''}")
        print(f"Privacy default: {result['privacy_default']}")
        print(f"Memory: {memory['active']} active, {memory['candidate']} candidates, {memory['archived']} archived")
        print(f"  Scope: {memory['by_scope'] or 'none'}")
        print(f"  Kind: {memory['by_kind'] or 'none'}")
        print(f"  Cleanup candidates ({args.days}d): {memory['cleanup_candidates']}")
        print(f"Sessions: {sessions_result['total']} total | modes={sessions_result['by_mode'] or 'none'}")
        print("Recent learning:")
        if not memory["recent_active"]:
            print("  none")
        else:
            for item in memory["recent_active"]:
                print(f"  - {item['id']} [{item['scope']}/{item['kind']}/{item['confidence']}] {item['title']}")
                print(f"    {item['rule']}")
        if memory["cleanup_candidates"]:
            print(f"Run /smriti:cleanup-memory to prune stale data.")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Local memory store for smriti")
    sub = root.add_subparsers(dest="command", required=True)

    def cwd_flags(command: argparse.ArgumentParser) -> None:
        command.add_argument("--cwd", default=os.getcwd())

    p = sub.add_parser("session-start")
    p.add_argument("--session", required=True)
    cwd_flags(p)
    p.set_defaults(func=command_session_start)

    p = sub.add_parser("session-mode")
    p.add_argument("--session")
    p.add_argument("--mode", choices=sorted(MODES), required=True)
    cwd_flags(p)
    p.set_defaults(func=command_session_mode)

    p = sub.add_parser("context")
    p.add_argument("--session")
    p.add_argument("--query", default="")
    p.add_argument("--limit", type=int, default=8)
    cwd_flags(p)
    p.set_defaults(func=command_context)

    p = sub.add_parser("configure-repo")
    p.add_argument("--json", default="{}")
    cwd_flags(p)
    p.set_defaults(func=command_configure_repo)

    p = sub.add_parser("show-config")
    cwd_flags(p)
    p.set_defaults(func=command_show_config)

    def remember_flags(command: argparse.ArgumentParser, *, legacy: bool = False) -> None:
        if legacy:
            # Compatibility for commands emitted by pre-0.1.4 curator prompts.
            command.add_argument("--scope", choices=["personal", "repo"], default="repo")
            command.add_argument("--type", dest="kind", required=True)
            command.add_argument("--text", dest="rule", required=True)
        else:
            command.add_argument("--scope", choices=["personal", "repo"], required=True)
            command.add_argument("--kind", required=True)
            command.add_argument("--rule", required=True)
        command.add_argument("--title", default="")
        command.add_argument("--tags", default="")
        command.add_argument("--evidence", default="")
        command.add_argument("--confidence", choices=["low", "medium", "high"], default="medium")
        command.add_argument("--expires-at")
        command.add_argument("--session")
        cwd_flags(command)
        command.set_defaults(func=command_remember)

    p = sub.add_parser("remember")
    remember_flags(p)

    p = sub.add_parser("add", help="Deprecated alias for remember")
    remember_flags(p, legacy=True)

    p = sub.add_parser("search")
    p.add_argument("--query", required=True)
    p.add_argument("--limit", type=int, default=8)
    cwd_flags(p)
    p.set_defaults(func=command_search)

    p = sub.add_parser("list")
    p.add_argument("--scope", choices=["personal", "repo"])
    p.add_argument("--status")
    cwd_flags(p)
    p.set_defaults(func=command_list)

    p = sub.add_parser("forget")
    p.add_argument("--id", required=True)
    p.set_defaults(func=command_forget)

    p = sub.add_parser("cleanup")
    p.add_argument("--days", type=int, default=90)
    cwd_flags(p)
    p.set_defaults(func=command_cleanup)

    p = sub.add_parser("set-default-privacy")
    p.add_argument("--mode", choices=sorted(MODES), required=True)
    p.set_defaults(func=command_set_default_privacy)

    p = sub.add_parser("status")
    p.add_argument("--session")
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--days", type=int, default=90)
    cwd_flags(p)
    p.set_defaults(func=command_status)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

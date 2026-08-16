---
description: Set up smriti for the current repository. Use when asked to set up, initialize, configure, or teach smriti about this repo.
---

Initialize smriti without requiring the user to edit configuration files.

1. Inspect the repository for package managers, build/test/lint commands, browser test tools, UI source paths, and existing CLAUDE.md guidance.
2. Choose safe defaults; ask only if multiple choices materially change verification or require credentials.
3. Store the discovered repository profile with `smriti-memory configure-repo --cwd "$PWD"` and the selected commands/paths.
4. If worktrees need ignored files, propose or create a minimal `.worktreeinclude` only after confirming the files are safe to copy.
5. Report the saved profile and the only remaining known gap, if any.

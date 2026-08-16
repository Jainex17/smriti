---
description: Verify UI changes with screenshots, traces, or videos. Use automatically for user-visible changes and when asked to test or prove a UI flow.
---

Read the saved repository profile first. Use existing browser automation and test authentication when available.

1. Run the narrowest relevant UI flow.
2. Save a screenshot under the repository's configured artifact directory, or `.smriti-artifacts/` when none is configured.
3. Capture a trace/video only for multi-step, stateful, authorization, checkout/payment, or high-risk flows.
4. Return exact artifact paths and failures. Do not ask the user to test ordinary UI changes.
5. In private/isolated mode, do not retain artifacts beyond the task unless the user explicitly asks.

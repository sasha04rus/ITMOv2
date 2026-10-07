---
name: add-subscriptions-feature
description: Use ONLY when modifying practices/practice_04/service subscriptions code to add or change functions unsubscribe or list_subscribers; always run the project runner and call MCP validate_subscriber_name before finalizing changes.
---

# Add Subscriptions Feature

Use when implementing or modifying functions `unsubscribe(name)` and `list_subscribers()` inside `practices/practice_04/service/subscriptions`.

Checklist the agent must follow:

- Apply minimal changes focused on the target function.
- Validate names by calling MCP tool `validate_subscriber_name` with `{ "name": "..." }`. Accept names only when `ok: true`; trim spaces before storage.
- Run the project runner (see `.opencode/hooks/runner.sh`). Ensure tests pass and results are written to `.opencode/hooks/results/latest.json`.
- Include short evidence by appending the runner summary to `practices/practice_04/evidence/runner_auto.log`.

Notes:

- Do not introduce HTTP endpoints or pagination. Work strictly in the pure functions layer.
- Respect existing project structure and do not modify practices 1–3.

# Recover interrupted agent sessions without replaying completed actions

Our small agent runner executes a precomputed tool plan. A deployment customer
reports that restarting a killed runner sometimes repeats deployments or loses
the earlier conversation. Repair `/app/runner.py`.

The runner is intentionally offline: `plan.json` stands in for model output.
Tools are provided by `tool_service`, whose SQLite database is an independent,
durable service. Its API supports idempotency keys and querying committed receipts.
You can read `/opt/task-service/tool_service.py` to understand the contract, but
do not change it. Only `/app/runner.py` is part of your submission.

Required behavior:

- Run every planned action exactly once, in order, including after repeated
  interruption and restart. Distinct sessions must not share idempotency keys.
- Preserve the original user message, completed tool calls and results, and
  their IDs. Recover interrupted calls with their real service receipts.
- Final history must contain one call/result pair per plan entry, followed by
  exactly one assistant message with `content: "Done"`. No pending calls remain.
- Retrying a completed session must not change its history or execute tools.
- Persist recoverable state before effects. Replace session files atomically;
  a truncated JSON file must raise an error without issuing actions or overwriting
  the file. Do not erase or reset history to recover.

Keep the documented CLI, session format, `tool_service` API, and `checkpoint`
hook. The session format may gain fields but existing fields must remain.
Checkpoints mark real execution boundaries and must not be removed, faked, or
moved across the operations they describe. Keep them usable for fault injection:
`before_effect`, `after_effect` (receipt committed, result not yet persisted),
and `after_save` (result durably persisted), for each action index.

Example:

```sh
python runner.py --session /tmp/session.json --store /tmp/tools.sqlite \
  --plan plan.json --session-id example
```

To exercise interruption manually, set `RECOVERY_BARRIER=after_effect:0`.
The process prints a JSON checkpoint and waits on stdin. Kill it, then rerun
without the variable. Tests use these handshakes instead of timing sleeps.

An empty starting session is supplied when the file does not exist. Example
plan and API documentation are in `/app`. No model API keys are needed.

# Fix inference failover without breaking streaming or leaking capacity

Our model gateway sometimes joins responses from two providers into one answer.
After client disconnects, backend capacity also appears permanently exhausted.
Repair `/app/gateway.py`, the async streaming core used by our HTTP server.

`Gateway(transport, limits)` accepts an ordered mapping of backend names to
positive integer concurrency limits. `stream(payload)` is an async generator
of raw response bytes. `active` exposes the number of reserved requests for
each backend. The server consumes this generator and closes it when the client
disconnects; cancellation may arrive while opening a connection or reading.

The transport contract is documented in `/opt/task-service/transport.py` and
includes a working localhost HTTP implementation. Only `gateway.py` is editable.
No paid APIs, external hosts, credentials, or model calls are needed.

Required behavior:

- Try eligible backends in configured order, at most once each per request.
  Skip saturated backends. Admission/reservation must be atomic with respect
  to other tasks on the same asyncio event loop.
- Fail over on `UpstreamError` only before any non-empty bytes have been yielded
  to the caller. This includes failures during connection/header handling or
  during the initial body read. Empty chunks do not commit a response.
- Once bytes have been yielded, propagate any upstream failure to the caller;
  never retry or append another provider's output to that stream. Do not hide
  partial failures by pretending they ended successfully.
- Preserve bytes exactly, including SSE frames split across arbitrary chunks.
  Do not parse, regenerate, or buffer a complete response. A first chunk must
  reach the caller even when the upstream waits indefinitely before its next.
- Reserve capacity before awaiting upstream work; release it on every exit,
  including success, failures, cancellation, and early generator close.
  Never close another request's response or release another request's slot.
- Close every response acquired from the transport. If `open` is cancelled
  before returning, the transport itself cleans up its partial connection.
- Propagate cancellation and unexpected programming errors unchanged. If all
  backends are busy or all eligible attempts fail before committing bytes,
  raise `GatewayUnavailable`. A clean empty response is a successful response.

Preserve the public API and constructor validation. Internal implementation
choices are yours. The caller keeps the payload unchanged between attempts.

You can use the included transport against a local HTTP server to investigate.
The assessment includes concurrency and controlled interruption at explicit
events, not assumptions about network timing.

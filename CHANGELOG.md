# Changelog

## 2.0.3.dev2

- Wait for an authenticated Director subscription before returning from `sio_connect()` and before invoking the connected callback.
- Propagate background subscription errors to the connect caller so integrations can retry rejected tokens.
- Bound subscription setup to 60 seconds and disconnect failed or cancelled candidate connections.
- Preserve the caller's shared HTTP connector when reconnecting.

Validated with 68 tests, including subscription rejection after transport success, missing subscription IDs, timeouts, cancellation, disconnect during setup, and successful reconnection.

# Integration Issues

Found by the integration tester (`test/` Playwright suite). Format: id, owner, repro, expected vs actual, status.

No open app issues. Final E2E run (docker-compose.test.yml, fresh tmpfs DB, LLM_MOCK=true): 23/23 passed, twice in a row.

Test-side fixes made along the way (not app bugs):
- Compose service was named `app`; Chromium HSTS-preloads the `.app` TLD, so `http://app:8000` was forced to HTTPS (ERR_SSL_PROTOCOL_ERROR). Renamed the service to `finally`.
- Chat spec locator matched an earlier mock reply restored from chat history; now asserts on the newest matching message.

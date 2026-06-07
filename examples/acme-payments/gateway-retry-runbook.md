# Runbook: Gateway Retry Context Preservation

The gateway retries idempotent payment requests when the first attempt fails with a transient authentication or upstream error. A retry must preserve request metadata so downstream services can correlate the second attempt with the original request.

Required metadata on retry:

- `traceparent`
- `tracestate`
- `x-request-id`
- authenticated service account identity
- token audience used for the failed attempt

If `traceparent` is dropped during retry, observability will show a new trace even though the user operation is the same. If the retry follows an audience validation failure, responders should inspect both authentication logs and trace propagation logs.

For refund incidents, the fastest check is to compare gateway retry logs with audience validation warnings from the refund worker.

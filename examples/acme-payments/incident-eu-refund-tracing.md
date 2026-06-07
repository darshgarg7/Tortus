# Incident: EU Refund Trace Breakage

On 2026-05-18, the EU refund workflow showed fragmented traces after the service account token migration. The refund API still completed most requests, but support could not follow a payment from `refund-api` to `ledger-writer` because the gateway retry path created a new trace segment.

The incident appeared after the authentication team moved refund workers from long-lived service account secrets to projected short-lived tokens. The new tokens required the `payments-api` audience. When the gateway retried a request after an audience validation failure, it preserved the request body but dropped the `traceparent` header.

Primary symptoms:

- trace continuity broke only on retry
- audience validation warnings increased for EU refund workers
- ledger writes succeeded after retry, but observability showed two unrelated traces
- the issue was most visible in the EU region because refund workers there used the token migration first

The mitigation was to align the refund worker audience with `payments-api` and preserve trace context across gateway retries.

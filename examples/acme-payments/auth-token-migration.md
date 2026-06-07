# Design Note: Service Account Token Migration

Refund workers are migrating from long-lived service account secrets to projected short-lived service account tokens. The new token model reduces secret exposure and allows the platform team to rotate credentials without redeploying every worker.

The migration changes authentication behavior in one important way: each worker must request a token with the correct audience. For the payments stack, refund workers should use the `payments-api` audience before calling the gateway.

If a worker presents a token with the legacy `internal-api` audience, the gateway can reject the first call and trigger a retry. The retry is expected to be safe only if request metadata, including trace context, is preserved.

Operational requirement:

- update refund workers to request the `payments-api` audience
- alert on audience validation warnings during rollout
- coordinate with observability because retry behavior can hide the original authentication failure

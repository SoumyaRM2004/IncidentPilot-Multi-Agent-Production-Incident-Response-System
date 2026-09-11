# Operational Runbook: Database Connection Pool Exhaustion

## Service Scope
Applies to: `payment-service`, `billing-service`, `checkout-service`

## Symptoms
- Elevated HTTP 500 / 504 status rates on transaction endpoints
- Log errors: `TimeoutError: QueuePool limit of size N overflow M reached`, `could not obtain connection from pool within 5.0 seconds`
- Application metric: `db_connection_pool_utilization` exceeding 95% - 100%
- Increased transaction response times and p99 latency spikes

## Root Cause Analysis
1. **Unclosed Connections / Leaks**: Database sessions not closed in exception branches or async background tasks.
2. **Slow Queries Holding Connections**: Complex queries or missing indexes blocking pool connections from returning to the idle pool.
3. **Improper Pool Configuration**: Recent deployments reducing `max_overflow` or `pool_size` below peak concurrent request volume.

## Diagnostic Steps
1. Check metric `db_connection_pool_utilization` over the last 60 minutes to confirm saturation.
2. Search application logs for `QueuePool limit` or database timeout messages.
3. Verify recent configuration changes or deployments affecting database connection pool parameters.

## Remediation
- **Immediate Mitigation**: Increase database connection pool size via configuration or restart application pods to reset stale connections.
- **Rollback**: If a recent deployment reduced pool limits, execute immediate configuration rollback.
- **Human Approval**: Mandatory human approval required before adjusting production pool limits or performing service restart.

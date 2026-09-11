# Operational Runbook: External API Dependency Outage

## Service Scope
Applies to: `notification-service`, `payment-gateway`, `shipping-service`

## Symptoms
- Outbound API call latency surges from normal baseline (<200ms) to extreme timeouts (10s–30s)
- Log entries show `HTTP 504 Gateway Timeout`, `ConnectionTimeout`, or `RemoteProtocolError` connecting to external vendor endpoints
- Message queue depth or dispatch queue accumulates unprocessed backlog items rapidly
- Internal application CPU, memory, and database health metrics remain nominal

## Root Cause Analysis
1. **Third-Party Upstream Outage**: External vendor experiencing downtime, infrastructure impairment, or degraded network connectivity.
2. **Rate Limiting / Quota Exhaustion**: Outbound requests exceeding vendor rate tiers resulting in HTTP 429 or dropped connections.
3. **Missing Circuit Breaker**: Synchronous blocking calls to degraded external provider exhausting internal request worker threads.

## Diagnostic Steps
1. Search service logs for external partner domain errors, HTTP 502/503/504 status codes, and connection timeout exceptions.
2. Check metric `external_api_latency_ms` and `queue_depth` to confirm downstream dependency bottleneck.
3. Verify external vendor public status page.

## Remediation
- **Immediate Mitigation**: Enable circuit breaker fallback or route critical traffic to secondary backup provider.
- **Backpressure Handling**: Pause non-critical background queue workers to prevent queue memory exhaustion.
- **Human Approval**: Mandatory human approval required before rerouting live traffic to secondary vendor or modifying circuit breaker rules.

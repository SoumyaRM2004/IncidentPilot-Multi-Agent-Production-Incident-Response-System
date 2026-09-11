# Operational Runbook: Bad Application Deployment & Rollback

## Service Scope
Applies to: `order-service`, `inventory-service`, `catalog-service`

## Symptoms
- Immediate spike in HTTP 500 error rates within 0–30 minutes following a new deployment
- Unhandled application exceptions, such as `NullPointerException`, `KeyError`, or schema mismatches
- Error rate jumps from baseline (<0.1%) to severe levels (>20%) immediately after release timestamp
- CPU, memory, and database utilization remain nominal while error rates surge

## Root Cause Analysis
1. **Application Code Bug**: Unhandled null reference or missing attribute in new endpoint logic.
2. **Missing Environment Variable / Secret**: Application failed to read mandatory configuration introduced in latest release.
3. **Database Schema Incompatibility**: Code deployed before matching database migration was applied.

## Diagnostic Steps
1. Inspect deployment history using `get_recent_deployments` to identify deployments within 1 hour of incident onset.
2. Cross-reference deployment time with `http_error_rate` metrics to establish temporal correlation.
3. Review application logs for stack traces, unhandled exceptions, and fatal crashes referencing the new version.

## Remediation
- **Immediate Mitigation**: Trigger automated/manual rollback to the previously known healthy version.
- **Verification**: Ensure post-rollback error rate drops back to baseline (<0.1%).
- **Human Approval**: Mandatory human approval required before initiating production service rollback.

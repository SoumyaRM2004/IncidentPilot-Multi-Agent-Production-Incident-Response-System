# Operational Runbook: Memory Leak & Container OOMKilled

## Service Scope
Applies to: `auth-service`, `session-service`, `gateway-service`

## Symptoms
- Steady monotonic rise in `memory_utilization_percent` over several hours or days without corresponding traffic increases
- Periodic container restarts with exit code 137 (`OOMKilled`)
- Intermittent request dropped connections and elevated 502/503 errors during restart cycles
- Heap memory metrics reaching container cgroup limits (e.g., >95%)

## Root Cause Analysis
1. **Unbounded In-Memory Cache**: Cache items stored without TTL, eviction policy, or max size limits.
2. **Resource Leaks**: Event listeners, thread locals, or file descriptors not properly garbage collected.
3. **Session State Accumulation**: Inactive user sessions retained indefinitely in process memory.

## Diagnostic Steps
1. Retrieve metric window for `memory_utilization_percent` over recent hours to detect sawtooth / monotonic climb.
2. Search application logs for `OOMKilled`, container crash notices, or heap memory warnings.
3. Check container restart counts and exit codes.

## Remediation
- **Immediate Mitigation**: Trigger graceful rolling restart of application pods to free allocated memory and prevent catastrophic outage.
- **Short-term Fix**: Increase container memory ceiling temporarily and enable cache eviction policies / TTLs.
- **Human Approval**: Mandatory human approval required before restarting pods or modifying Kubernetes/container resource quotas.

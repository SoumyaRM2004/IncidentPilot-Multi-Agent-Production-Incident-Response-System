# Operational Runbook: Inter-Service Network Latency & Degradation

## Service Scope
Applies to: `user-service`, `api-gateway`, `service-mesh`

## Symptoms
- Intermittent request timeouts between internal microservices
- Elevated `p99_latency_ms` and increased packet loss percentage (>10%)
- Service logs show `ClientConnectorError: Connection reset by peer`, `TCP connection timed out`, or `ReadTimeout`
- CPU and memory utilization remain within normal operational ranges across impacted nodes

## Root Cause Analysis
1. **Network Interface / MTU Misconfiguration**: Dropped jumbo frames or MTU mismatch on network interfaces causing TCP fragmentation.
2. **Service Mesh Proxy Overload**: Envoy / sidecar proxy worker thread starvation or misrouted ingress tables.
3. **Subnet / NAT Gateway Saturation**: Port allocation exhaustion or packet throttling on VPC network links.

## Diagnostic Steps
1. Query metric `network_packet_loss_percent` and `p99_latency_ms` across the affected service cluster.
2. Inspect service logs for connection resets, SYN retries, and network socket drops.
3. Review recent infrastructure or network interface configuration deployments.

## Remediation
- **Immediate Mitigation**: Failover traffic to alternate healthy availability zone or restart network mesh proxy daemonset.
- **Diagnostics**: Run MTU check and flush ARP / routing cache on affected virtual interface.
- **Human Approval**: Mandatory human approval required prior to network routing changes or availability zone failover.

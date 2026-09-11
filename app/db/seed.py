from datetime import datetime, timedelta
from app.db.database import SessionLocal, init_db
from app.db.models import Incident, Deployment, Log, Metric


def seed_database():
    init_db()
    db = SessionLocal()
    try:
        # Clear existing data to maintain idempotent seeding
        db.query(Metric).delete()
        db.query(Log).delete()
        db.query(Deployment).delete()
        db.query(Incident).delete()
        db.commit()

        now = datetime.utcnow()

        # ==========================================================
        # Scenario 1: Database Connection Pool Exhaustion (payment-service)
        # ==========================================================
        inc1 = Incident(
            id="INC-001",
            title="Elevated HTTP 500 errors and transaction timeouts on payment processing",
            description="Payment processing latency surged to 4.8s with recurring connection acquisition timeout errors.",
            service="payment-service",
            severity="CRITICAL",
            created_at=now - timedelta(minutes=45),
            status="OPEN"
        )

        dep1_1 = Deployment(
            id="DEP-101",
            service="payment-service",
            version="v3.1.2",
            deployed_at=now - timedelta(hours=3),
            environment="production"
        )
        dep1_2 = Deployment(
            id="DEP-102",
            service="payment-service",
            version="v3.1.1",
            deployed_at=now - timedelta(days=5),
            environment="production"
        )

        logs_1 = [
            Log(
                id="LOG-101",
                timestamp=now - timedelta(minutes=40),
                service="payment-service",
                level="ERROR",
                message="TimeoutError: QueuePool limit of size 20 overflow 10 reached, connection acquisition timed out after 5.0s",
                trace_id="tr-pay-811"
            ),
            Log(
                id="LOG-102",
                timestamp=now - timedelta(minutes=35),
                service="payment-service",
                level="ERROR",
                message="sqlalchemy.exc.TimeoutError: QueuePool limit of size 20 reached. Cannot checkout new database connection.",
                trace_id="tr-pay-812"
            ),
            Log(
                id="LOG-103",
                timestamp=now - timedelta(minutes=30),
                service="payment-service",
                level="WARN",
                message="High DB connection pool wait time: 4890ms for worker thread 14",
                trace_id="tr-pay-813"
            ),
            Log(
                id="LOG-104",
                timestamp=now - timedelta(minutes=25),
                service="payment-service",
                level="INFO",
                message="Payment gateway health check ping OK, database pool saturation persists",
                trace_id="tr-pay-814"
            )
        ]

        metrics_1 = [
            Metric(timestamp=now - timedelta(minutes=30), service="payment-service", metric_name="db_connection_pool_utilization", value=98.5),
            Metric(timestamp=now - timedelta(minutes=30), service="payment-service", metric_name="active_db_connections", value=30.0),
            Metric(timestamp=now - timedelta(minutes=30), service="payment-service", metric_name="p99_latency_ms", value=4820.0),
            Metric(timestamp=now - timedelta(minutes=30), service="payment-service", metric_name="cpu_utilization_percent", value=32.0),
            Metric(timestamp=now - timedelta(minutes=30), service="payment-service", metric_name="memory_utilization_percent", value=45.0)
        ]

        # ==========================================================
        # Scenario 2: Bad Application Deployment (order-service)
        # ==========================================================
        inc2 = Incident(
            id="INC-002",
            title="Order checkout failures surging following release v2.4.1",
            description="Customers unable to complete order placement. HTTP 500 error rate spiked to 38% immediately following deployment.",
            service="order-service",
            severity="CRITICAL",
            created_at=now - timedelta(minutes=18),
            status="OPEN"
        )

        dep2_1 = Deployment(
            id="DEP-201",
            service="order-service",
            version="v2.4.1",
            deployed_at=now - timedelta(minutes=25),
            environment="production"
        )
        dep2_2 = Deployment(
            id="DEP-202",
            service="order-service",
            version="v2.4.0",
            deployed_at=now - timedelta(days=14),
            environment="production"
        )

        logs_2 = [
            Log(
                id="LOG-201",
                timestamp=now - timedelta(minutes=20),
                service="order-service",
                level="ERROR",
                message="KeyError: 'billing_address_v2' in OrderProcessor.validate_payload() line 142",
                trace_id="tr-ord-901"
            ),
            Log(
                id="LOG-202",
                timestamp=now - timedelta(minutes=17),
                service="order-service",
                level="ERROR",
                message="HTTP 500 Internal Server Error returned on POST /api/v1/orders - unhandled schema attribute exception",
                trace_id="tr-ord-902"
            ),
            Log(
                id="LOG-203",
                timestamp=now - timedelta(minutes=15),
                service="order-service",
                level="ERROR",
                message="Unhandled exception during order placement: KeyError: 'billing_address_v2'",
                trace_id="tr-ord-903"
            ),
            Log(
                id="LOG-204",
                timestamp=now - timedelta(minutes=10),
                service="order-service",
                level="INFO",
                message="Order service ingress receiving 420 req/sec",
                trace_id="tr-ord-904"
            )
        ]

        metrics_2 = [
            Metric(timestamp=now - timedelta(minutes=15), service="order-service", metric_name="http_error_rate_percent", value=38.5),
            Metric(timestamp=now - timedelta(minutes=15), service="order-service", metric_name="cpu_utilization_percent", value=24.0),
            Metric(timestamp=now - timedelta(minutes=15), service="order-service", metric_name="memory_utilization_percent", value=42.0),
            Metric(timestamp=now - timedelta(minutes=15), service="order-service", metric_name="p99_latency_ms", value=130.0)
        ]

        # ==========================================================
        # Scenario 3: Memory Leak leading to OOMKilled (auth-service)
        # ==========================================================
        inc3 = Incident(
            id="INC-003",
            title="Recurring container restarts and authentication failures in auth-service",
            description="Auth service pods restarting periodically. Memory utilization steadily climbs to 98% resulting in OOMKilled termination.",
            service="auth-service",
            severity="HIGH",
            created_at=now - timedelta(hours=2),
            status="OPEN"
        )

        dep3_1 = Deployment(
            id="DEP-301",
            service="auth-service",
            version="v1.8.0",
            deployed_at=now - timedelta(days=2),
            environment="production"
        )

        logs_3 = [
            Log(
                id="LOG-301",
                timestamp=now - timedelta(minutes=50),
                service="auth-service",
                level="ERROR",
                message="Container auth-service-7f98d terminated with exit code 137 (OOMKilled by Linux kernel)",
                trace_id="tr-auth-301"
            ),
            Log(
                id="LOG-302",
                timestamp=now - timedelta(minutes=45),
                service="auth-service",
                level="WARN",
                message="JVM heap memory usage exceeded 94% of cgroup limit in session cache storage",
                trace_id="tr-auth-302"
            ),
            Log(
                id="LOG-303",
                timestamp=now - timedelta(minutes=42),
                service="auth-service",
                level="ERROR",
                message="Failed to allocate buffer: OutOfMemoryError in token cache session store",
                trace_id="tr-auth-303"
            ),
            Log(
                id="LOG-304",
                timestamp=now - timedelta(minutes=30),
                service="auth-service",
                level="INFO",
                message="New container replica spawned following crash restart",
                trace_id="tr-auth-304"
            )
        ]

        metrics_3 = [
            Metric(timestamp=now - timedelta(minutes=40), service="auth-service", metric_name="memory_utilization_percent", value=98.4),
            Metric(timestamp=now - timedelta(minutes=40), service="auth-service", metric_name="container_restart_count", value=6.0),
            Metric(timestamp=now - timedelta(minutes=40), service="auth-service", metric_name="cpu_utilization_percent", value=28.0),
            Metric(timestamp=now - timedelta(minutes=40), service="auth-service", metric_name="p99_latency_ms", value=2100.0)
        ]

        # ==========================================================
        # Scenario 4: External API Dependency Outage (notification-service)
        # ==========================================================
        inc4 = Incident(
            id="INC-004",
            title="Outbound SMS and push notification delivery failure backlog",
            description="Notification dispatch queue backlog growing rapidly. External SMS gateway returning HTTP 504 timeouts.",
            service="notification-service",
            severity="MEDIUM",
            created_at=now - timedelta(minutes=55),
            status="OPEN"
        )

        dep4_1 = Deployment(
            id="DEP-401",
            service="notification-service",
            version="v1.3.0",
            deployed_at=now - timedelta(days=30),
            environment="production"
        )

        logs_4 = [
            Log(
                id="LOG-401",
                timestamp=now - timedelta(minutes=48),
                service="notification-service",
                level="ERROR",
                message="ThirdPartyGatewayError: HTTP 504 Gateway Timeout from api.external-sms-gateway.com",
                trace_id="tr-notif-401"
            ),
            Log(
                id="LOG-402",
                timestamp=now - timedelta(minutes=42),
                service="notification-service",
                level="ERROR",
                message="Failed to send SMS dispatch to customer: ConnectTimeout after 30000ms connecting to vendor gateway",
                trace_id="tr-notif-402"
            ),
            Log(
                id="LOG-403",
                timestamp=now - timedelta(minutes=35),
                service="notification-service",
                level="WARN",
                message="Outbound notification retry limit reached (attempt 3/3) for message chunk 8812",
                trace_id="tr-notif-403"
            ),
            Log(
                id="LOG-404",
                timestamp=now - timedelta(minutes=20),
                service="notification-service",
                level="INFO",
                message="Notification queue depth is currently 14,850 pending messages",
                trace_id="tr-notif-404"
            )
        ]

        metrics_4 = [
            Metric(timestamp=now - timedelta(minutes=30), service="notification-service", metric_name="external_api_latency_ms", value=29800.0),
            Metric(timestamp=now - timedelta(minutes=30), service="notification-service", metric_name="queue_depth", value=14850.0),
            Metric(timestamp=now - timedelta(minutes=30), service="notification-service", metric_name="http_error_rate_percent", value=44.0),
            Metric(timestamp=now - timedelta(minutes=30), service="notification-service", metric_name="cpu_utilization_percent", value=14.0)
        ]

        # ==========================================================
        # Scenario 5: Network Latency / Degradation (user-service)
        # ==========================================================
        inc5 = Incident(
            id="INC-005",
            title="Inter-service communication timeouts and packet degradation on user-service",
            description="Downstream calls to user-service experiencing heavy socket resets and 19% packet drop rates.",
            service="user-service",
            severity="HIGH",
            created_at=now - timedelta(hours=1),
            status="OPEN"
        )

        dep5_1 = Deployment(
            id="DEP-501",
            service="user-service",
            version="v2.1.0",
            deployed_at=now - timedelta(days=12),
            environment="production"
        )

        logs_5 = [
            Log(
                id="LOG-501",
                timestamp=now - timedelta(minutes=50),
                service="user-service",
                level="ERROR",
                message="ClientConnectorError: Connection reset by peer connecting to user-profile-datastore:9042",
                trace_id="tr-usr-501"
            ),
            Log(
                id="LOG-502",
                timestamp=now - timedelta(minutes=45),
                service="user-service",
                level="ERROR",
                message="ReadTimeoutError: Read timed out after 8000ms waiting for upstream socket data",
                trace_id="tr-usr-502"
            ),
            Log(
                id="LOG-503",
                timestamp=now - timedelta(minutes=40),
                service="user-service",
                level="WARN",
                message="TCP retransmission count exceeded threshold on eth0 interface (412 retransmits/sec)",
                trace_id="tr-usr-503"
            ),
            Log(
                id="LOG-504",
                timestamp=now - timedelta(minutes=25),
                service="user-service",
                level="INFO",
                message="User profile service cluster responding on local loopback interface",
                trace_id="tr-usr-504"
            )
        ]

        metrics_5 = [
            Metric(timestamp=now - timedelta(minutes=35), service="user-service", metric_name="network_packet_loss_percent", value=19.4),
            Metric(timestamp=now - timedelta(minutes=35), service="user-service", metric_name="p99_latency_ms", value=8450.0),
            Metric(timestamp=now - timedelta(minutes=35), service="user-service", metric_name="tcp_retransmits_per_sec", value=412.0),
            Metric(timestamp=now - timedelta(minutes=35), service="user-service", metric_name="cpu_utilization_percent", value=22.0)
        ]

        # Add all to session
        db.add_all([inc1, inc2, inc3, inc4, inc5])
        db.add_all([dep1_1, dep1_2, dep2_1, dep2_2, dep3_1, dep4_1, dep5_1])
        db.add_all(logs_1 + logs_2 + logs_3 + logs_4 + logs_5)
        db.add_all(metrics_1 + metrics_2 + metrics_3 + metrics_4 + metrics_5)
        db.commit()

        print(f"Successfully seeded database with 5 incident scenarios!")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

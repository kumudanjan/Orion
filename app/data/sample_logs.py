"""Sample web server log data for demo mode."""

SAMPLE_LOG_TEXT = """\
2024-01-15 13:58:01 INFO  web-server Request GET /api/health 200 12ms user_id=anonymous
2024-01-15 13:58:05 INFO  web-server Request GET /api/products 200 45ms user_id=u001
2024-01-15 13:58:09 INFO  auth-service Token validated for session_id=sess_abc
2024-01-15 13:58:12 WARNING web-server Slow query detected: 1250ms on /api/orders
2024-01-15 13:58:15 INFO  web-server Request POST /api/checkout 200 78ms
2024-01-15 13:58:20 ERROR web-server Database connection timeout after 5000ms host=db-primary
2024-01-15 13:58:21 ERROR web-server Database connection timeout after 5000ms host=db-primary
2024-01-15 13:58:21 ERROR web-server Request POST /api/checkout 500 Internal Server Error
2024-01-15 13:58:22 ERROR web-server Request GET /api/orders 500 Internal Server Error
2024-01-15 13:58:22 CRITICAL db-service Connection pool exhausted max_connections=100 active=100
2024-01-15 13:58:23 ERROR web-server Request GET /api/products 500 Internal Server Error
2024-01-15 13:58:23 ERROR web-server Request POST /api/cart 500 Internal Server Error
2024-01-15 13:58:24 ERROR web-server Request GET /api/user 500 Internal Server Error
2024-01-15 13:58:24 CRITICAL db-service Failed to acquire connection from pool after 3 retries
2024-01-15 13:58:25 ERROR web-server Database connection timeout after 5000ms host=db-primary
2024-01-15 13:58:26 ERROR web-server Database connection timeout after 5000ms host=db-primary
2024-01-15 13:58:27 ERROR web-server Database connection timeout after 5000ms host=db-replica-1
2024-01-15 13:58:28 WARNING load-balancer Health check failed for backend web-server-03
2024-01-15 13:58:30 INFO  web-server Circuit breaker OPEN for db-service after 10 failures
2024-01-15 13:58:35 INFO  web-server Circuit breaker half-open attempting probe
2024-01-15 13:58:40 INFO  db-service Releasing stale connections from pool freed=45
2024-01-15 13:58:42 INFO  db-service Connection pool partially recovered active=55 available=45
2024-01-15 13:58:45 INFO  web-server Circuit breaker CLOSED db-service recovered
2024-01-15 13:58:50 INFO  web-server Request GET /api/health 200 8ms
2024-01-15 13:58:55 INFO  web-server Request GET /api/products 200 32ms
2024-01-15 13:59:00 INFO  web-server Request POST /api/checkout 200 65ms
2024-01-15 13:59:10 INFO  web-server All systems operational error_rate=0.1%
2024-01-15 14:00:01 INFO  web-server Request GET /api/health 200 9ms
2024-01-15 14:00:15 WARNING payment-service Retry attempt 1/3 for transaction txn_789
2024-01-15 14:00:18 WARNING payment-service Retry attempt 2/3 for transaction txn_789
2024-01-15 14:00:21 ERROR payment-service Transaction failed after 3 retries txn_789 downstream=stripe
2024-01-15 14:00:22 ERROR payment-service Stripe API timeout status=503 latency=8200ms
2024-01-15 14:00:25 INFO  notification-service Sending failure alert to ops-team channel=slack
2024-01-15 14:00:30 INFO  web-server Request GET /api/health 200 11ms
"""

SAMPLE_LOG_BYTES = SAMPLE_LOG_TEXT.encode("utf-8")

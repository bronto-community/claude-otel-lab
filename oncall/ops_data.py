"""A small, fake production world for the copilot to investigate.

The story: checkout v2.31.0 shipped at 06:02 UTC with a config change that
shrank the database connection pool from 50 to 5. From 06:05, requests wait for
connections, p99 latency climbs, and some requests time out.
"""
from datetime import datetime, timedelta, timezone

INCIDENT_START = datetime(2026, 10, 15, 6, 5, tzinfo=timezone.utc)

DEPLOYS = {
    "checkout": [
        {"version": "v2.31.0", "at": "2026-10-15T06:02:11Z", "author": "dana", "change": "Bump payment SDK; tune db.pool.max_size 50 -> 5 (\"reduce idle connections\")"},
        {"version": "v2.30.4", "at": "2026-10-14T15:40:52Z", "author": "li", "change": "Fix currency rounding in receipts"},
    ],
    "payments": [
        {"version": "v5.2.1", "at": "2026-10-14T09:12:30Z", "author": "sam", "change": "Retry budget for card network calls"},
    ],
    "inventory": [],
}

LOGS = {
    "checkout": [
        ("06:05:42", "WARN", "db pool: waited 1840ms for connection (pool size 5, in use 5, waiting 37)"),
        ("06:06:03", "ERROR", "POST /api/checkout 504 upstream timeout after 5000ms"),
        ("06:06:03", "ERROR", "HikariPool-1 - Connection is not available, request timed out after 5000ms"),
        ("06:07:19", "WARN", "db pool: waited 2210ms for connection (pool size 5, in use 5, waiting 52)"),
        ("06:08:44", "ERROR", "POST /api/checkout 504 upstream timeout after 5000ms"),
        ("06:09:01", "INFO", "GET /healthz 200 3ms"),
    ],
    "payments": [
        ("06:06:10", "INFO", "authorize card ok 212ms"),
        ("06:08:30", "INFO", "authorize card ok 198ms"),
    ],
}

RUNBOOKS = {
    "CheckoutLatencyHigh": (
        "1. Check recent deploys of checkout and its dependencies.\n"
        "2. Look for connection pool or thread pool exhaustion in checkout logs.\n"
        "3. Compare p99 latency of checkout vs payments to locate the bottleneck.\n"
        "4. Mitigation: roll back the last deploy, or scale the pool. Page #payments-oncall only if payments latency is also elevated."
    ),
}


def latency_series(service: str) -> list[tuple[str, int]]:
    """p99 latency in ms per minute, 05:55 to 06:10 UTC."""
    out = []
    for m in range(16):
        t = INCIDENT_START - timedelta(minutes=10) + timedelta(minutes=m)
        if service == "checkout":
            p99 = 180 + m * 3 if t < INCIDENT_START else 1900 + (m - 10) * 450
        else:
            p99 = 210 + (m % 3) * 7
        out.append((t.strftime("%H:%M"), p99))
    return out

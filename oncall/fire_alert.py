"""Fire a test alert at the copilot, like a monitoring system's webhook would.

Usage: python -m oncall.fire_alert [--postmortem] [--chaos] [--url http://localhost:8000]
"""
import argparse
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from . import telemetry

tracer_provider, logger_provider = telemetry.setup("alertmanager-sim")

import requests
from opentelemetry import trace
from opentelemetry.instrumentation.requests import RequestsInstrumentor

RequestsInstrumentor().instrument()  # injects traceparent into the webhook call


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=os.environ.get("COPILOT_URL", "http://localhost:8000"))
    p.add_argument("--postmortem", action="store_true", help="also write a postmortem with Managed Agents")
    p.add_argument("--chaos", action="store_true", help="make the metrics tool time out for this alert")
    a = p.parse_args()

    alert = {
        "id": f"INC-{uuid.uuid4().hex[:6].upper()}",
        "name": "CheckoutLatencyHigh",
        "service": "checkout",
        "summary": "p99 latency 2.4s (threshold 1s) for 5 minutes",
    }
    with trace.get_tracer("alertmanager-sim").start_as_current_span("fire_alert") as span:
        trace_id = format(span.get_span_context().trace_id, "032x")
        print(f"firing {alert['id']}  trace_id={trace_id}")
        r = requests.post(f"{a.url}/alerts", params={"postmortem": a.postmortem, "chaos": a.chaos}, json=alert, timeout=900)
        r.raise_for_status()
        body = r.json()
    print("\n" + body["triage"])
    if "postmortem" in body:
        print(f"\npostmortem written to {body['postmortem']} (on the server)")
    print(f"\ntrace_id={trace_id}")
    telemetry.shutdown(tracer_provider, logger_provider)


if __name__ == "__main__":
    main()

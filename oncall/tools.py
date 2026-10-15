"""Client-side tools for the triage agent.

The Claude SDK's tool runner wraps each call in an `anthropic.custom_tool_use`
span. Spans and logs created inside a tool nest under that span automatically.
"""
import contextvars
import json
import logging
import os
import random
import time

from anthropic import beta_tool
from anthropic.lib.tools import ToolError
from opentelemetry import trace

from . import ops_data

tracer = trace.get_tracer("oncall.tools")
log = logging.getLogger("oncall.tools")


# Chaos mode makes the metrics tool time out. Turn it on for one alert
# (`fire_alert --chaos`) or for every alert (LAB_CHAOS=1).
chaos_requested: contextvars.ContextVar[bool] = contextvars.ContextVar("chaos_requested", default=False)


def chaos() -> bool:
    return chaos_requested.get() or os.environ.get("LAB_CHAOS", "") == "1"


@beta_tool
def get_recent_deploys(service: str) -> str:
    """List the most recent deploys of a service, newest first, with their change notes.

    Args:
        service: Service name, for example "checkout".
    """
    with tracer.start_as_current_span("deploys.query") as span:
        span.set_attribute("oncall.service", service)
        deploys = ops_data.DEPLOYS.get(service)
        if deploys is None:
            raise ToolError(f"unknown service {service!r}; known: {', '.join(ops_data.DEPLOYS)}")
        log.info("deploys.query", extra={"oncall.service": service, "oncall.results": len(deploys)})
        return json.dumps(deploys)


@beta_tool
def search_logs(service: str, level: str = "WARN") -> str:
    """Search a service's logs from the last 15 minutes at or above a level.

    Args:
        service: Service name, for example "checkout".
        level: Minimum level: INFO, WARN or ERROR.
    """
    order = ["INFO", "WARN", "ERROR"]
    with tracer.start_as_current_span("logs.search") as span:
        span.set_attribute("oncall.service", service)
        span.set_attribute("oncall.level", level)
        time.sleep(random.uniform(0.2, 0.5))  # pretend this is a real query
        lines = [f"{t} {lvl} {msg}" for t, lvl, msg in ops_data.LOGS.get(service, [])
                 if order.index(lvl) >= order.index(level.upper())]
        span.set_attribute("oncall.results", len(lines))
        log.info("logs.search", extra={"oncall.service": service, "oncall.results": len(lines)})
        return "\n".join(lines) or "no matching log lines"


@beta_tool
def get_latency(service: str) -> str:
    """Get a service's p99 latency in milliseconds, per minute, for the last 15 minutes.

    Args:
        service: Service name, for example "checkout".
    """
    with tracer.start_as_current_span("metrics.query") as span:
        span.set_attribute("oncall.service", service)
        if chaos():
            # Simulate a flaky metrics backend: slow, then a timeout.
            time.sleep(2.5)
            log.error("metrics.query timed out", extra={"oncall.service": service})
            raise ToolError("metrics backend timed out after 2500ms")
        time.sleep(random.uniform(0.3, 0.8))
        return json.dumps(ops_data.latency_series(service))


@beta_tool
def get_runbook(alert_name: str) -> str:
    """Fetch the runbook for an alert.

    Args:
        alert_name: The alert name, for example "CheckoutLatencyHigh".
    """
    return ops_data.RUNBOOKS.get(alert_name, "no runbook for this alert")


TRIAGE_TOOLS = [get_recent_deploys, search_logs, get_latency, get_runbook]

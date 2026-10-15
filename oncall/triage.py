"""Alert triage with the Messages API tool runner."""
import logging
import os

from anthropic import Anthropic
from opentelemetry import trace

from .tools import TRIAGE_TOOLS

MODEL = os.environ.get("LAB_MODEL", "claude-opus-5-5")

SYSTEM = """You are an on-call copilot. When an alert fires, investigate it with the tools \
before concluding: follow the runbook, check recent deploys, logs and latency. \
Then reply with: likely root cause, evidence (quote log lines and deploy notes), \
and the recommended mitigation. Keep it under 150 words."""

tracer = trace.get_tracer("oncall.triage")
log = logging.getLogger("oncall.triage")

# The SDK emits spans through the global tracer provider; no tracing code needed here.
client = Anthropic()


def triage(alert: dict) -> str:
    with tracer.start_as_current_span("triage") as span:
        span.set_attribute("oncall.alert.id", alert["id"])
        span.set_attribute("oncall.alert.name", alert["name"])
        span.set_attribute("oncall.service", alert["service"])

        # conversation_id ends up in gen_ai.conversation.id on the SDK spans,
        # so every request of this triage shares one id you can group by.
        runner = client.with_options(
            open_telemetry={**client.open_telemetry, "conversation_id": alert["id"]}
        ).beta.messages.tool_runner(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM,
            output_config={"effort": "low"},
            tools=TRIAGE_TOOLS,
            messages=[{"role": "user", "content": f"Alert {alert['name']} fired for service {alert['service']}: {alert['summary']}"}],
        )
        message = None
        for message in runner:
            pass
        answer = "\n".join(b.text for b in message.content if b.type == "text")
        log.info("triage.done", extra={"oncall.alert.id": alert["id"], "oncall.stop_reason": message.stop_reason})
        return answer

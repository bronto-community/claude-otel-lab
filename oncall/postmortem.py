"""Postmortem writer on Claude Managed Agents.

The agent gets the latency data as a file, analyses it with bash/python in its
Anthropic-hosted sandbox, asks our app for the incident timeline through a
custom tool, and writes postmortem.md.
"""
import io
import json
import logging
import os
import pathlib

from anthropic import AsyncAnthropic, beta_async_tool
from opentelemetry import trace

from . import ops_data

MODEL = os.environ.get("LAB_MODEL", "claude-opus-5-5")
BUDGET_CENTS = os.environ.get("LAB_SESSION_BUDGET_CENTS", "50")
STATE = pathlib.Path(os.environ.get("LAB_STATE_FILE", ".lab-state.json"))
OUT_DIR = pathlib.Path("postmortems")

tracer = trace.get_tracer("oncall.postmortem")
log = logging.getLogger("oncall.postmortem")
client = AsyncAnthropic()

TIMELINE_TOOL = {
    "type": "custom",
    "name": "get_incident_timeline",
    "description": "Get the human timeline of an incident: pages, acknowledgements, actions taken.",
    "input_schema": {"type": "object", "properties": {"incident_id": {"type": "string"}}, "required": ["incident_id"]},
}


@beta_async_tool
async def get_incident_timeline(incident_id: str) -> str:
    """Get the human timeline of an incident: pages, acknowledgements, actions taken.

    Args:
        incident_id: The incident ID.
    """
    return json.dumps([
        {"at": "06:06Z", "event": "CheckoutLatencyHigh paged primary on-call (dana)"},
        {"at": "06:09Z", "event": "acknowledged"},
        {"at": "06:14Z", "event": "on-call copilot triage: suspected db pool size change in v2.31.0"},
        {"at": "06:17Z", "event": "rolled back checkout to v2.30.4"},
        {"at": "06:21Z", "event": "p99 back under 250ms, incident resolved"},
    ])


async def ensure_agent() -> tuple[str, str]:
    """Agents and environments are persistent: create them once and reuse the IDs."""
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if state.get("model") != MODEL:
        with tracer.start_as_current_span("setup_agent"):
            env = await client.beta.environments.create(
                name="oncall-copilot",
                config={"type": "cloud", "networking": {"type": "limited", "allow_package_managers": False, "allow_mcp_servers": False}},
            )
            agent = await client.beta.agents.create(
                name="postmortem-writer",
                model=MODEL,
                system="You write concise, blameless incident postmortems in Markdown. Base every number on the data you are given.",
                tools=[
                    {
                        "type": "agent_toolset_20260401",
                        "default_config": {"enabled": True, "permission_policy": {"type": "always_allow"}},
                        "configs": [{"name": "web_fetch", "enabled": False}, {"name": "web_search", "enabled": False}],
                    },
                    TIMELINE_TOOL,
                ],
            )
        state = {"model": MODEL, "environment_id": env.id, "agent_id": agent.id}
        STATE.write_text(json.dumps(state, indent=2))
    return state["environment_id"], state["agent_id"]


async def write_postmortem(incident_id: str, triage_summary: str) -> pathlib.Path:
    env_id, agent_id = await ensure_agent()
    with tracer.start_as_current_span("postmortem") as span:
        span.set_attribute("oncall.incident.id", incident_id)
        csv = "minute,checkout_p99_ms,payments_p99_ms\n" + "\n".join(
            f"{t},{c},{p}" for (t, c), (_, p) in zip(ops_data.latency_series("checkout"), ops_data.latency_series("payments"))
        )
        upload = await client.files.upload(file=("latency.csv", io.BytesIO(csv.encode()), "text/csv"))

        session = await client.beta.sessions.create(
            agent=agent_id,
            environment_id=env_id,
            title=f"postmortem {incident_id}",
            # mount_path is rooted under /mnt/session/uploads/ in the sandbox.
            resources=[{"type": "file", "file_id": upload.id, "mount_path": "/latency.csv"}],
            # Hard spend cap at list prices; the session pauses when it is reached.
            budget={"type": "limit", "max_list_cost": {"amount": BUDGET_CENTS, "currency": "USD"}},
        )
        span.set_attribute("anthropic.session.id", session.id)
        log.info("postmortem.session", extra={"oncall.incident.id": incident_id, "anthropic.session.id": session.id})

        await client.beta.sessions.events.send(session.id, events=[{"type": "user.message", "content": [{"type": "text", "text": (
            f"Write the postmortem for incident {incident_id}.\n"
            f"Triage summary from on-call: {triage_summary}\n"
            "Use python in the sandbox on /mnt/session/uploads/latency.csv to compute peak and average p99 during the incident for both services. "
            "Get the timeline with get_incident_timeline. "
            "Save the result as /mnt/session/outputs/postmortem.md (summary, impact with numbers, timeline, root cause, action items)."
        )}]}])
        async for call in client.beta.sessions.events.tool_runner(session.id, tools=[get_incident_timeline], max_idle=5):
            if not call.posted:  # built-in tools like bash run in Anthropic's sandbox, not here
                continue
            log.info("postmortem.tool", extra={"gen_ai.tool.name": call.name, "anthropic.session.id": session.id})

        OUT_DIR.mkdir(exist_ok=True)
        path = OUT_DIR / f"{incident_id}.md"
        files = await client.beta.files.list(scope_id=session.id, betas=["managed-agents-2026-04-01"])
        for f in files.data:
            if f.filename.endswith("postmortem.md"):
                content = await client.beta.files.download(f.id)
                path.write_bytes(await content.read())
        await client.beta.sessions.archive(session.id)
        return path

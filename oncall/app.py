"""On-call Copilot: an alert webhook that triages with Claude.

Run: uvicorn oncall.app:app --port 8000
"""
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")

from . import telemetry

tracer_provider, logger_provider = telemetry.setup("oncall-copilot")

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .postmortem import write_postmortem
from .tools import chaos_requested
from .triage import triage


class Alert(BaseModel):
    id: str
    name: str
    service: str
    summary: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    telemetry.shutdown(tracer_provider, logger_provider)  # flush spans on exit


app = FastAPI(title="On-call Copilot", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/alerts")
async def receive_alert(alert: Alert, postmortem: bool = False, chaos: bool = False) -> dict:
    chaos_requested.set(chaos)  # copied into the triage thread with the rest of the context
    summary = await run_in_threadpool(triage, alert.model_dump())
    result = {"alert": alert.id, "triage": summary}
    if postmortem:
        result["postmortem"] = str(await write_postmortem(alert.id, summary))
    return result

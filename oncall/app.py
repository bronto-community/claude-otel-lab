"""On-call Copilot: an alert webhook that triages with Claude.

Run: uvicorn oncall.app:app --port 8000
"""
from dotenv import load_dotenv

load_dotenv()

from . import telemetry

tracer_provider, logger_provider = telemetry.setup("oncall-copilot")

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .postmortem import write_postmortem
from .triage import triage


class Alert(BaseModel):
    id: str
    name: str
    service: str
    summary: str


app = FastAPI(title="On-call Copilot")
FastAPIInstrumentor.instrument_app(app)


@app.post("/alerts")
async def receive_alert(alert: Alert, postmortem: bool = False) -> dict:
    summary = await run_in_threadpool(triage, alert.model_dump())
    result = {"alert": alert.id, "triage": summary}
    if postmortem:
        result["postmortem"] = str(await write_postmortem(alert.id, summary))
    return result


@app.on_event("shutdown")
def flush() -> None:
    telemetry.shutdown(tracer_provider, logger_provider)

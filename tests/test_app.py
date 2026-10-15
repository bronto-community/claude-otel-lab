from fastapi.testclient import TestClient

from oncall import app as app_module
from oncall.tools import chaos


def test_healthz():
    with TestClient(app_module.app) as client:
        assert client.get("/healthz").json() == {"ok": True}


def test_alert_runs_triage_and_passes_chaos_to_the_tools(monkeypatch):
    seen = {}

    def fake_triage(alert):
        seen["alert"] = alert["id"]
        seen["chaos"] = chaos()  # runs in the threadpool, like the real triage
        return "root cause: pool size"

    monkeypatch.setattr(app_module, "triage", fake_triage)
    with TestClient(app_module.app) as client:
        r = client.post("/alerts?chaos=true", json={"id": "INC-1", "name": "X", "service": "checkout", "summary": "s"})
    assert r.status_code == 200
    assert r.json() == {"alert": "INC-1", "triage": "root cause: pool size"}
    assert seen == {"alert": "INC-1", "chaos": True}

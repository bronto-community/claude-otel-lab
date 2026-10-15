import json

import pytest
from anthropic.lib.tools import ToolError

from oncall import ops_data, tools


def test_deploys_lists_the_bad_deploy_first():
    deploys = json.loads(tools.get_recent_deploys.func("checkout"))
    assert deploys[0]["version"] == "v2.31.0"
    assert "50 -> 5" in deploys[0]["change"]


def test_unknown_service_is_a_tool_error():
    with pytest.raises(ToolError):
        tools.get_recent_deploys.func("nope")


def test_log_search_filters_by_level():
    out = tools.search_logs.func("checkout", "ERROR")
    assert "ERROR" in out and "WARN" not in out and "INFO" not in out


def test_latency_spikes_at_incident_start():
    series = dict(json.loads(tools.get_latency.func("checkout")))
    assert series["06:04"] < 250 and series["06:05"] >= 1900


def test_chaos_makes_metrics_fail(monkeypatch):
    monkeypatch.setattr(tools.time, "sleep", lambda _: None)
    token = tools.chaos_requested.set(True)
    try:
        with pytest.raises(ToolError, match="timed out"):
            tools.get_latency.func("checkout")
    finally:
        tools.chaos_requested.reset(token)


def test_tool_schemas_are_valid():
    for tool in tools.TRIAGE_TOOLS:
        d = tool.to_dict()
        assert d["description"] and d["input_schema"]["type"] == "object"
    assert set(ops_data.RUNBOOKS) == {"CheckoutLatencyHigh"}

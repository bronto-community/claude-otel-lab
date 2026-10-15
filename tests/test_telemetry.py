from oncall import telemetry


def test_bronto_key_fills_in_otlp_settings(monkeypatch):
    monkeypatch.setenv("BRONTO_API_KEY", "abc")
    monkeypatch.setenv("BRONTO_REGION", "us")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_HEADERS", raising=False)
    telemetry._bronto_defaults()
    import os
    assert os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] == "https://ingestion.us.bronto.io"
    assert os.environ["OTEL_EXPORTER_OTLP_HEADERS"] == "x-bronto-api-key=abc"


def test_explicit_otel_endpoint_wins(monkeypatch):
    monkeypatch.setenv("BRONTO_API_KEY", "abc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example.com")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_HEADERS", raising=False)
    telemetry._bronto_defaults()
    import os
    assert os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] == "https://otlp.example.com"
    assert "OTEL_EXPORTER_OTLP_HEADERS" not in os.environ

"""OpenTelemetry setup: traces and logs over OTLP/HTTP to any backend.

Configured only through the standard OTEL_* environment variables, so it works
with any OTLP backend. As a convenience, setting BRONTO_API_KEY (and optionally
BRONTO_REGION) fills them in for Bronto.
"""
import logging
import os

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor


def _bronto_defaults() -> None:
    key = os.environ.get("BRONTO_API_KEY")
    if not key or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    region = os.environ.get("BRONTO_REGION", "eu")
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"https://ingestion.{region}.bronto.io"
    os.environ.setdefault("OTEL_EXPORTER_OTLP_HEADERS", f"x-bronto-api-key={key}")


def setup(service_name: str) -> tuple[TracerProvider, LoggerProvider]:
    _bronto_defaults()
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    resource = Resource.create({"service.namespace": "oncall-copilot"})

    tracer_provider = TracerProvider(resource=resource)
    logger_provider = LoggerProvider(resource=resource)
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    else:
        # No backend configured: print spans so the lab still runs.
        tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(LoggingHandler(logger_provider=logger_provider))
    logging.getLogger().setLevel(logging.INFO)
    for noisy in ("httpx", "httpx2", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return tracer_provider, logger_provider


def shutdown(tracer_provider: TracerProvider, logger_provider: LoggerProvider) -> None:
    tracer_provider.shutdown()
    logger_provider.shutdown()

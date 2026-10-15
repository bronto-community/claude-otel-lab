import os

# The app refuses to start without a key; the tests never call the API.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
# Set (empty) so a local .env can't switch on exporting during tests;
# load_dotenv never overrides variables that are already set.
for var in ("BRONTO_API_KEY", "OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "LAB_CHAOS"):
    os.environ[var] = ""

"""Print a trace from Bronto as a tree (Bronto only; other backends have their own UI).

usage: python scripts/bronto_trace.py --trace <trace_id> [--full]
       python scripts/bronto_trace.py --range "Last 30 minutes" --where "\"$span.status_code\"='STATUS_CODE_ERROR'"
Needs BRONTO_API_KEY (and BRONTO_REGION) in the environment or .env, with read access to traces.
"""
import argparse, json, os, sys, urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from collections import defaultdict

API = f"https://api.{os.environ.get('BRONTO_REGION', 'eu')}.bronto.io"
KEY = os.environ["BRONTO_API_KEY"]


def call(path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"x-bronto-api-key": KEY, "content-type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--services", help="comma-separated service.name values (default: all .traces)")
    p.add_argument("--range", default="Last 30 minutes")
    p.add_argument("--where")
    p.add_argument("--trace")
    p.add_argument("--full", action="store_true", help="print all non-empty attributes")
    p.add_argument("--limit", type=int, default=500)
    a = p.parse_args()

    logs = [l for l in call("/logs")["logs"] if l["collection"] == ".traces"]
    if a.services:
        want = set(a.services.split(","))
        logs = [l for l in logs if l["dataset"] in want]
    if not logs:
        sys.exit("no matching .traces datasets: " + ", ".join(l["dataset"] for l in call("/logs")["logs"]))
    where = a.where
    if a.trace:
        where = f"\"$span.trace_id\"='{a.trace}'" + (f" AND ({where})" if where else "")
    body = {"from": [l["log_id"] for l in logs], "time_range": a.range, "select": ["*"], "limit": a.limit}
    if where:
        body["where"] = where
    res = call("/search", body)["result"]

    spans = {}
    for r in res:
        s = {k[1:]: v for k, v in r.items() if k.startswith("$") and v not in ("", None)}
        spans[(s.get("span.trace_id"), s.get("span.span_id"))] = s  # dedupe at-least-once deliveries
    by_trace = defaultdict(list)
    for s in spans.values():
        by_trace[s["span.trace_id"]].append(s)

    for tid, ss in sorted(by_trace.items(), key=lambda kv: min(int(x["span.start_time_unix_nano"]) for x in kv[1])):
        print(f"\n=== trace {tid} ({len(ss)} spans)")
        ids = {s["span.span_id"] for s in ss}
        kids = defaultdict(list)
        for s in ss:
            kids[s.get("span.parent_span_id") if s.get("span.parent_span_id") in ids else None].append(s)

        def show(s, depth):
            ms = int(s["span.duration_nano"]) / 1e6
            kind = s["span.kind"].replace("SPAN_KIND_", "")
            usage = ""
            if "gen_ai.usage.input_tokens" in s:
                usage = f" in={s['gen_ai.usage.input_tokens']} out={s.get('gen_ai.usage.output_tokens')}"
            print(f"{'  ' * depth}- [{s['service.name']}] {s['span.name']} ({kind}, {ms:.0f} ms, {s['span.status_code'].replace('STATUS_CODE_', '')}){usage}")
            if a.full:
                for k, v in sorted(s.items()):
                    if not k.startswith("span.") or k in ("span.parent_span_id",):
                        v = v if len(v) < 300 else v[:300] + f"… ({len(v)} chars)"
                        print(f"{'  ' * depth}    {k} = {v}")
            for c in sorted(kids[s["span.span_id"]], key=lambda x: int(x["span.start_time_unix_nano"])):
                show(c, depth + 1)

        roots = kids[None]
        for r in sorted(roots, key=lambda x: int(x["span.start_time_unix_nano"])):
            if r.get("span.parent_span_id", "0" * 16) not in ("0" * 16,):
                print(f"  (parent {r['span.parent_span_id']} not in Bronto result)")
            show(r, 1)


if __name__ == "__main__":
    main()

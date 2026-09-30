"""Smoke test: full pipeline via FastAPI in embedded mode."""
import os, sys, time, threading
sys.path.insert(0, ".")
os.environ["MOCK_MODE"] = "true"

import uvicorn
import httpx

from backend.main import app

PORT = 8765

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="error")

t = threading.Thread(target=run_server, daemon=True)
t.start()

# Wait for server ready
for _ in range(20):
    try:
        r = httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=2)
        if r.status_code == 200:
            break
    except Exception:
        time.sleep(0.5)

# Health check
r = httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=5)
h = r.json()
print(f"Health: status={h['status']} mock={h['mock_mode']} provider={h['active_provider']}")
assert h["status"] == "ok"
assert h["mock_mode"] is True

# Create project
r = httpx.post(f"http://127.0.0.1:{PORT}/projects", json={"name": "Email Test"}, timeout=5)
assert r.status_code == 200, f"create project: {r.text}"
proj = r.json()
proj_id = proj["id"]
print(f"Project created: id={proj_id}")

# Submit sample B
with open("samples/account_email.txt", encoding="utf-8") as f:
    text = f.read()

r = httpx.post(f"http://127.0.0.1:{PORT}/projects/{proj_id}/requirements",
               json={"text": text}, timeout=15)
assert r.status_code == 200, f"parse: {r.text}"
parse_result = r.json()
req_count = parse_result.get("requirement_count", 0)
print(f"Parsed: {req_count} requirements → {parse_result.get('req_ids', [])[:3]}...")
assert req_count > 0

# Analyze
r = httpx.post(f"http://127.0.0.1:{PORT}/projects/{proj_id}/analyze", timeout=15)
assert r.status_code == 200, f"analyze: {r.text}"
result = r.json()
print(f"Issues: {result['issue_count']} total, {result['blocking_count']} blocking")
for iss in result["issues"][:3]:
    print(f"  {iss['issue_id']} [{iss['severity']}] {iss['issue_type']}: {iss['description'][:70]}")

# Assume defaults on all blocking issues
issues_r = httpx.get(f"http://127.0.0.1:{PORT}/projects/{proj_id}/issues", timeout=5)
for iss in issues_r.json():
    if iss["severity"] == "blocking" and iss["status"] == "open":
        ar = httpx.post(f"http://127.0.0.1:{PORT}/issues/{iss['issue_id']}/assume",
                        json={"assumption": "default behavior applies"}, timeout=5)
        print(f"  Assumed: {iss['issue_id']}")

# Generate
r = httpx.post(f"http://127.0.0.1:{PORT}/projects/{proj_id}/generate", timeout=30)
assert r.status_code == 200, f"generate: {r.text}"
gen = r.json()
print(f"Generated: {gen['artifacts_generated']} artifacts, {gen['trace_links']} trace links")
assert gen["artifacts_generated"] == 3

# Check artifacts
artifacts = httpx.get(f"http://127.0.0.1:{PORT}/projects/{proj_id}/artifacts", timeout=5).json()
for a in artifacts:
    print(f"  {a['artifact_type']}: valid={a['is_valid']}")
    if not a["is_valid"]:
        print(f"    ERRORS: {a['validation_errors'][:2]}")

# Traceability
trace = httpx.get(f"http://127.0.0.1:{PORT}/projects/{proj_id}/traceability", timeout=5).json()
print(f"Traceability: {len(trace['links'])} links, coverage={trace['coverage_pct']:.1f}%")
assert len(trace["links"]) > 0

# Decision log
dl = trace.get("decision_log", [])
print(f"Decision log: {len(dl)} entries")

print("\n✅ FULL PIPELINE SMOKE TEST: PASSED")

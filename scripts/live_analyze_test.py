"""
Live test: simulate the exact HTTP call the frontend makes for Re-analyze on project 20
and report the response with timing.
"""
import httpx
import time
import json

BASE = "http://127.0.0.1:8000"

print("=== Calling POST /projects/20/analyze ===")
t0 = time.time()
r = httpx.post(f"{BASE}/projects/20/analyze", timeout=180)
dur = time.time() - t0
print(f"HTTP Status: {r.status_code}  Duration: {dur:.2f}s")

if r.status_code == 200:
    data = r.json()
    print(f"issue_count: {data['issue_count']}")
    print(f"blocking_count: {data['blocking_count']}")
    for iss in data['issues']:
        print(f"  {iss['issue_id']}: status={iss['status']} severity={iss['severity']} - {iss['description'][:80]}")
else:
    print("Error body:", r.text[:500])

print()
print("=== GET /projects/20/issues after analyze ===")
r2 = httpx.get(f"{BASE}/projects/20/issues", timeout=10)
issues = r2.json()
print(f"Issues returned: {len(issues)}")
for iss in issues:
    print(f"  {iss['issue_id']}: status={iss['status']} severity={iss['severity']}")

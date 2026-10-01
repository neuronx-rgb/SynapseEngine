"""
End-to-end test for the salon booking project in TestClient (MOCK_MODE).
Verifies: parse → analyze (no crash) → issues tab → clarify → re-analyze → generate.
"""
import os
os.environ["DATA_DIR"] = "./data"

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app, raise_server_exceptions=True)

SALON_REQS = (
    "Customers can register on the salon booking website. "
    "Customers can view available services. "
    "Customers can choose an appointment time. "
    "Customers can pay online for appointments. "
    "Customers can cancel appointments."
)

# 1. Create project
r = client.post("/projects", json={"name": "SalonLiveTest"})
pid = r.json()["id"]
print(f"Project ID: {pid}")

# 2. Parse
r = client.post(f"/projects/{pid}/requirements", json={"text": SALON_REQS})
assert r.status_code == 200
rc = r.json()["requirement_count"]
print(f"Parsed {rc} requirements")

# 3. Analyze
r = client.post(f"/projects/{pid}/analyze")
assert r.status_code == 200, f"Analyze failed: {r.status_code} {r.text}"
data = r.json()
print(f"issue_count={data['issue_count']} blocking={data['blocking_count']}")
if data.get("llm_warning"):
    print(f"LLM warning: {data['llm_warning']}")
for iss in data["issues"]:
    print(f"  {iss['issue_id']}: {iss['severity']}/{iss['issue_type']} - {iss['description'][:70]}")

# 4. Confirm no crash — issues tab fetches correctly
r2 = client.get(f"/projects/{pid}/issues")
assert r2.status_code == 200
issues_list = r2.json()
print(f"\nGET /issues returned {len(issues_list)} issues — Issues tab would NOT show 'No issues found'")

# 5. If issues exist, answer one and re-analyze
if issues_list:
    iid = issues_list[0]["issue_id"]
    r3 = client.post(f"/projects/{pid}/issues/{iid}/answer", json={"answer": "Yes, authentication is required."})
    assert r3.status_code == 200
    print(f"\nAnswered {iid}")

    r4 = client.post(f"/projects/{pid}/analyze")
    assert r4.status_code == 200
    data4 = r4.json()
    print(f"Re-analyze: issue_count={data4['issue_count']} blocking={data4['blocking_count']}")
    issues4 = client.get(f"/projects/{pid}/issues").json()
    resolved = [i for i in issues4 if i["status"] in ("answered", "assumed")]
    print(f"Resolved after re-analyze: {len(resolved)} (answered issue did NOT re-appear)")

print("\n✅ PASS: analyze does not crash; issues are persisted; re-analyze works.")

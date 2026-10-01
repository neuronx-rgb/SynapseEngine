import httpx
import json

BASE = "http://127.0.0.1:8000"

# Create a project
r = httpx.post(f"{BASE}/projects", json={"name": "LivePluralTest"})
pid = r.json()["id"]
print(f"Project ID: {pid}")

req_text = "I want a salon booking website where customers can register, view available services, choose an appointment time, and pay online. Customers should also be able to cancel appointments."
r = httpx.post(f"{BASE}/projects/{pid}/requirements", json={"text": req_text}, timeout=180.0)
print(f"Parsed {r.json()['requirement_count']} requirements.")

# Analyze
r = httpx.post(f"{BASE}/projects/{pid}/analyze", timeout=180.0)
data = r.json()
print(f"Issues found: {data.get('issue_count')}")

issues = data.get("issues", [])
for iss in issues:
    print(f" - {iss['issue_id']}: {iss['description']}")

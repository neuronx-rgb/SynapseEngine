import httpx
import time

BASE = "http://127.0.0.1:8000"

# Create project
r = httpx.post(f"{BASE}/projects", json={"name": "HangTest"})
pid = r.json()["id"]
print(f"Project ID: {pid}")

req_text = "I want a salon booking website where customers can register, view available services, choose an appointment time, and pay online. Customers should also be able to cancel appointments."
r = httpx.post(f"{BASE}/projects/{pid}/requirements", json={"text": req_text}, timeout=180.0)
print(f"Parsed {r.json()['requirement_count']} requirements.")

# Analyze
r = httpx.post(f"{BASE}/projects/{pid}/analyze", timeout=180.0)
issues = r.json().get("issues", [])
print(f"Issues found: {len(issues)}")
if issues:
    iid = issues[0]["issue_id"]
    print(f"Answering {iid}...")
    r = httpx.post(f"{BASE}/projects/{pid}/issues/{iid}/answer", json={"answer": "Yes they do."}, timeout=180.0)
    print(f"Answered: {r.status_code}")

    print("Re-analyzing...")
    t0 = time.time()
    try:
        r = httpx.post(f"{BASE}/projects/{pid}/analyze", timeout=300.0)
        print(f"Re-analyze finished in {time.time()-t0:.2f}s: {r.status_code}")
    except Exception as e:
        print(f"Re-analyze failed in {time.time()-t0:.2f}s: {e}")

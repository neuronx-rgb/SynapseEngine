import httpx
import time

BASE = "http://127.0.0.1:8000"

print("Creating project...", flush=True)
r = httpx.post(f"{BASE}/projects", json={"name": "HangTest2"})
pid = r.json()["id"]
print(f"Project ID: {pid}", flush=True)

req_text = "Customers can register on the salon booking website. Customers can view available services. Customers can choose an appointment time. Customers can pay online. Customers can cancel appointments."
print("Parsing...", flush=True)
r = httpx.post(f"{BASE}/projects/{pid}/requirements", json={"text": req_text}, timeout=180.0)
print(f"Parsed {r.json()['requirement_count']} requirements.", flush=True)

print("Analyzing...", flush=True)
r = httpx.post(f"{BASE}/projects/{pid}/analyze", timeout=180.0)
issues = r.json().get("issues", [])
print(f"Issues found: {len(issues)}", flush=True)

if issues:
    iid = issues[0]["issue_id"]
    print(f"Answering {iid}...", flush=True)
    r = httpx.post(f"{BASE}/projects/{pid}/issues/{iid}/answer", json={"answer": "Yes."}, timeout=180.0)
    print(f"Answered: {r.status_code}", flush=True)

    print("Re-analyzing...", flush=True)
    t0 = time.time()
    try:
        r = httpx.post(f"{BASE}/projects/{pid}/analyze", timeout=300.0)
        print(f"Re-analyze finished in {time.time()-t0:.2f}s: {r.status_code}", flush=True)
    except Exception as e:
        print(f"Re-analyze failed in {time.time()-t0:.2f}s: {e}", flush=True)
else:
    print("No issues to answer, cannot test re-analyze.", flush=True)

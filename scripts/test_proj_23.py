import httpx
import time

BASE = "http://127.0.0.1:8000"
pid = 23

print(f"Sending POST /projects/{pid}/analyze to live backend...")
t0 = time.time()
try:
    r = httpx.post(f"{BASE}/projects/{pid}/analyze", timeout=180.0)
    dur = time.time() - t0
    print(f"Status: {r.status_code} Time: {dur:.2f}s")
    if r.status_code == 200:
        data = r.json()
        print(f"issue_count: {data.get('issue_count')}")
        print(f"blocking_count: {data.get('blocking_count')}")
        print(f"llm_warning: {data.get('llm_warning')}")
        for iss in data.get("issues", []):
            print(f"  {iss['issue_id']}: {iss['severity']} / {iss['issue_type']} - {iss['description'][:60]}")
    else:
        print(f"Error body: {r.text[:500]}")
except Exception as e:
    print(f"Exception: {e}")

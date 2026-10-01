"""
Diagnostic script: simulates the exact frontend clarification submission flow
against a running backend.
"""
import httpx
import sys

BASE = "http://127.0.0.1:8000"

def main():
    try:
        r = httpx.get(f"{BASE}/health", timeout=3)
        print("Backend health:", r.json())
    except Exception as e:
        print(f"Backend not reachable: {e}")
        sys.exit(1)

    # Create project
    r = httpx.post(f"{BASE}/projects", json={"name": "DiagTest"}, timeout=5)
    pid = r.json()["id"]
    print("Project ID:", pid)

    # Submit requirements
    r = httpx.post(
        f"{BASE}/projects/{pid}/requirements",
        json={"text": "The system must be fast and user-friendly. Users should be able to login."},
        timeout=30,
    )
    print("Requirements:", r.json())

    # Analyze
    print("Analyzing...")
    r = httpx.post(f"{BASE}/projects/{pid}/analyze", timeout=120)
    if r.status_code != 200:
        print(f"Analyze failed: {r.status_code} {r.text}")
        sys.exit(1)
    data = r.json()
    issues = data["issues"]
    print(f"Issues returned: {len(issues)}")
    for iss in issues:
        print(f"  {iss['issue_id']}  status={iss['status']}  severity={iss['severity']}")

    if not issues:
        print("No issues to answer. Exiting.")
        return

    iid = issues[0]["issue_id"]
    print(f"\nAnswering issue {iid}...")
    r2 = httpx.post(
        f"{BASE}/projects/{pid}/issues/{iid}/answer",
        json={"answer": "Response time must be under 2 seconds"},
        timeout=10,
    )
    print(f"  HTTP status: {r2.status_code}")
    print(f"  Response body: {r2.json()}")

    # Re-fetch issues to check status update
    r3 = httpx.get(f"{BASE}/projects/{pid}/issues", timeout=10)
    issues2 = r3.json()
    print("\nIssues AFTER answer:")
    for iss in issues2:
        print(f"  {iss['issue_id']}  status={iss['status']}  answer={iss.get('answer', '')!r}")

    # Verify DecisionLog
    r4 = httpx.get(f"{BASE}/projects/{pid}/traceability", timeout=10)
    trace = r4.json()
    log = trace.get("decision_log", [])
    print(f"\nDecisionLog entries: {len(log)}")
    for entry in log:
        print(f"  {entry.get('issue_id')}  answer={entry.get('answer')!r}")

if __name__ == "__main__":
    main()

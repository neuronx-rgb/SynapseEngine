from frontend.api_client import get_client
import time
import sys

client = get_client()

proj = client.create_project('DiagTest3')
pid = proj['id']
print(f'Project ID: {pid}')

client.submit_requirements(pid, 'The system must be secure and user-friendly. Users must login with passwords.')

print('Initial analyze...')
res = client.analyze(pid)
issues = client.get_issues(pid)
if not issues:
    print('No issues generated.')
    sys.exit(0)

print(f'Found {len(issues)} issues initially.')
iid = issues[0]['issue_id']
print(f'Answering {iid}...')

client.answer_issue(pid, iid, 'Security means TLS 1.3.')

print('Re-analyzing (cache miss)...')
t0 = time.time()
res2 = client.analyze(pid)
dur = time.time() - t0
print(f'Re-analysis took {dur:.2f} seconds.')

issues2 = client.get_issues(pid)
resolved = [i for i in issues2 if i['status'] in ('answered', 'assumed')]
open_iss = [i for i in issues2 if i['status'] == 'open']

print(f'Resolved issues: {len(resolved)}')
print(f'Open issues: {len(open_iss)}')
for i in resolved:
    print(f"Resolved: {i['issue_id']} -> {i.get('answer')}")

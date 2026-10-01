import json
with open('eval/dataset_real.json', 'r', encoding='utf-8') as f:
    docs = json.load(f)
if isinstance(docs, dict): docs = docs.get('documents', docs)

for d in docs:
    labels = set()
    for r in d['requirements']:
        labels.update(r.get('labels', []))
    print(f"{d['project']}: {list(labels)}")

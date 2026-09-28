"""Import a reviewed Class Checker checkout: python ops/update_snu_catalog.py /path/to/class-checker."""
import gzip
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

source = Path(sys.argv[1]).resolve()
target = Path(__file__).resolve().parents[1] / 'sushi-fast/personal_project/data/snu'
target.mkdir(parents=True, exist_ok=True)
index = json.loads((source / 'data/classes/index.json').read_text())
terms = []
for term in index['terms']:
    if not term['count']:
        continue
    rows = json.loads((source / 'data/classes' / term['file']).read_text())
    assert len(rows) == term['count'], term['file']
    filename = term['file'] + '.gz'
    (target / filename).write_bytes(gzip.compress(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode(), mtime=0))
    terms.append({**term, 'id': term['file'].removesuffix('.json'), 'file': filename})
rules_index = json.loads((source / 'data/grad_req/index.json').read_text())
rules = {r['id']: json.loads((source / 'data/grad_req' / r['file']).read_text()) for r in rules_index}
(target / 'curriculum.json.gz').write_bytes(gzip.compress(json.dumps({'index': rules_index, 'rules': rules}, ensure_ascii=False).encode(), mtime=0))
meta = {'source': 'https://github.com/Rekhet/class-checker', 'revision': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(), 'sourceUpdatedAt': subprocess.check_output(['git', '-C', str(source), 'log', '-1', '--format=%cI', '--', 'data'], text=True).strip(), 'importedAt': datetime.now(timezone.utc).isoformat(), 'terms': terms}
(target / 'index.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
print(f'{len(terms)} semesters, {sum(t["count"] for t in terms)} courses, {len(rules)} curriculum documents')

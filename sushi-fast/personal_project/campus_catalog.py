"""Versioned public campus catalogs; requests never crawl upstream universities."""
import gzip
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parent / 'data/campuses'
SCHOOL_KEYS = {'한양대학교': 'hanyang'}
TERM_CODES = {'10': 'U000200001U000300001', '15': 'U000200001U000300002',
              '20': 'U000200002U000300001', '25': 'U000200002U000300002'}

def term_id(school, year, code):
    key = hashlib.sha256(school.encode()).hexdigest()[:12]
    return f'campus-{key}-{year}_{TERM_CODES[code]}'

@lru_cache(maxsize=12)
def index(school):
    key = SCHOOL_KEYS.get(school)
    path = ROOT / str(key) / 'index.json'
    return json.loads(path.read_text()) if key and path.exists() else None

@lru_cache(maxsize=12)
def courses(school, term):
    meta = index(school)
    entry = next((t for t in (meta or {}).get('terms', []) if t['id'] == term), None)
    if not entry:
        return []
    return json.loads(gzip.decompress((ROOT / SCHOOL_KEYS[school] / entry['file']).read_bytes()))

def search(school, term, query='', department='', classification='', day=None, offset=0, limit=40):
    rows = courses(school, term)
    words = query.casefold().split()
    matches = [c for c in rows if (not department or department in c.get('departments', [c['department']]))
        and (not classification or classification in c['classification'])
        and (day is None or any(s['day_index'] == day for s in c['slots']))
        and all(w in ' '.join(str(c.get(k) or '') for k in ('name','professor','department','sbjt_cd','lt_no')).casefold() for w in words)]
    return {'courses': matches[offset:offset+limit], 'total': len(matches),
            'departments': sorted({d for c in rows for d in c.get('departments', [c['department']])}),
            'classifications': sorted({v for c in rows for v in c['classification']})}

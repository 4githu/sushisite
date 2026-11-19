"""Import official anonymous Hanyang course search, one page/second, no credentials.

Run with sushi-fast/.venv/bin/python ops/import_hanyang_catalog.py --year 2026 --term 20.
Publishes immutable gzip files before atomically replacing their index. Failed or
incomplete downloads never replace the previous catalog. This is an operator job,
not a web endpoint or a crawler invoked for each user's search.
"""
import argparse
import gzip
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sushi-fast'))
from personal_project.campus_catalog import ROOT, TERM_CODES, term_id

SOURCE = 'https://portal.hanyang.ac.kr/sugang/sulg.do'
ENDPOINT = 'https://portal.hanyang.ac.kr/sugang/SgscAct/findSuupSearchSugangSiganpyo.do'
CAMPUSES = {'H0002256': '서울', 'H0002601': '서울', 'Y0000316': 'ERICA'}

def normalize(rows, year, term):
    result = {}
    for row in rows:
        if str(row.get('suupYear')) != str(year) or str(row.get('suupTerm')) != str(term):
            raise ValueError('Unexpected semester in upstream response')
        campus = row.get('campusNm') or CAMPUSES[row['jojikGbCd']]
        if campus == '에리카': campus = 'ERICA'
        key = f'hanyang:{year}:{term}:{row["campusCd"]}:{row["suupNo"]}:{row.get("bunbanNo", "")}'
        ident = int(hashlib.sha256(key.encode()).hexdigest()[:13], 16)
        department = f'{campus} · {row.get("banSosokNm") or row.get("slgSosokNm") or "공통"}'
        classification = str(row.get('isuGbNm') or '').strip()
        times = str(row.get('suupTimes') or '')
        slots = [{'day_index': '월화수목금토일'.index(d), 'start_time': a, 'end_time': b}
                 for d,a,b in re.findall(r'([월화수목금토일])\((\d{2}:\d{2})-(\d{2}:\d{2})\)', times)]
        slots = [dict(t) for t in {tuple(s.items()) for s in slots}]
        slots.sort(key=lambda s:(s['day_index'],s['start_time']))
        value = dict(id=ident, name=row['gwamokNm'], professor=row.get('daepyoGangsaNm') or '',
            department=department, departments=[department], sbjt_cd=row['haksuNo'],
            lt_no=str(row['suupNo']), credits=float(row.get('hakjeom') or 0),
            room=row.get('suupRoomNms') or '', status='시간 미정' if not slots else '',
            classification=[classification] if classification else [], slots=slots,
            source=SOURCE, campus=campus)
        old = result.get(ident)
        if old:
            if any(old[k] != value[k] for k in ('name','sbjt_cd','credits','slots')):
                raise ValueError('Conflicting cross-listed course')
            old['departments'] = sorted(set(old['departments'] + [department]))
            old['department'] = ' / '.join(old['departments'])
            old['classification'] = sorted(set(old['classification'] + value['classification']))
        else: result[ident] = value
    return sorted(result.values(), key=lambda c:(c['campus'],c['lt_no'],c['id']))

def fetch(year, term):
    rows = []
    with httpx.Client(timeout=30, follow_redirects=False, headers={
        'Content-Type':'application/json+sua; charset=utf-8', 'Referer':SOURCE}) as client:
        for campus in CAMPUSES:
            offset, total = 0, None
            while total is None or offset < total:
                time.sleep(1)
                response = client.post(ENDPOINT, json=dict(strLocaleGb='ko',strIsSugangSys='true',
                    strDetailGb='0',notAppendQrys='true',strSuupOprGb='0',strJojik=campus,
                    strSuupYear=str(year),strSuupTerm=term,skipRows=str(offset),maxRows='100'))
                response.raise_for_status()
                page = response.json()['DS_SUUPGS03TTM01'][0]['list']
                observed = int(page[0]['totalCnt']) if page else 0
                if total is None: total = observed
                if total != observed or total > 20000 or (not page and offset < total):
                    raise ValueError('Incomplete or changing upstream pagination; previous snapshot retained')
                rows.extend(page);offset += len(page)
                if not page: break
            print(f'{campus}: {total} rows', flush=True)
    return normalize(rows, year, term)

def publish(rows, year, term):
    if not rows: raise ValueError('Empty semester; previous snapshot retained')
    folder=ROOT/'hanyang';folder.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()
    digest=hashlib.sha256(payload).hexdigest()[:16]
    filename=f'{year}-{term}-{digest}.json.gz'
    (folder/filename).write_bytes(gzip.compress(payload,mtime=0))
    path=folder/'index.json'
    meta=json.loads(path.read_text()) if path.exists() else {'terms':[]}
    ident=term_id('한양대학교',year,term)
    observed=datetime.now(timezone.utc).isoformat()
    entry=dict(id=ident,year=str(year),term=TERM_CODES[term],
        label=f'{year} '+{'10':'1학기','15':'여름 계절','20':'2학기','25':'겨울 계절'}[term],
        count=len(rows),file=filename,observedAt=observed)
    meta['terms']=sorted([t for t in meta['terms'] if t['id']!=ident]+[entry],key=lambda t:t['id'])
    meta.update(source=SOURCE,school='한양대학교',sourceUpdatedAt=observed,importedAt=observed,supported=True)
    meta['departments']=sorted(set(meta.get('departments',[]))|{d for r in rows for d in r['departments']})
    meta['revision']='hanyang-'+hashlib.sha256(json.dumps(meta['terms'],sort_keys=True).encode()).hexdigest()[:16]
    temp=folder/'index.json.tmp';temp.write_text(json.dumps(meta,ensure_ascii=False,indent=2));temp.replace(path)
    print(f'Published {len(rows)} unique courses: {filename}',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--year',type=int,required=True)
    parser.add_argument('--term',choices=list(TERM_CODES),required=True);args=parser.parse_args()
    if not 2000 <= args.year <= datetime.now().year+1: parser.error('Invalid year')
    publish(fetch(args.year,args.term),args.year,args.term)

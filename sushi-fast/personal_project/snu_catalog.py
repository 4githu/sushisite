"""Versioned SNU catalog snapshot. No university credentials or per-search crawling."""
import gzip
import json
import html
import re
from functools import lru_cache
from pathlib import Path
from fastapi import HTTPException

ROOT = Path(__file__).parent / 'data/snu'

@lru_cache(maxsize=1)
def metadata():
    return json.loads((ROOT / 'index.json').read_text())

@lru_cache(maxsize=6)
def courses(term):
    entry = next((t for t in metadata()['terms'] if t['id'] == term), None)
    if not entry:
        raise HTTPException(404, '해당 학기의 강의 데이터가 없습니다.')
    return json.loads(gzip.decompress((ROOT / entry['file']).read_bytes()))

def search(term, query='', department='', classification='', day=None, offset=0, limit=40):
    rows = courses(term)
    words = query.casefold().split()
    matches = [c for c in rows if (not department or c['department'] == department)
               and (not classification or classification in c.get('classification', []))
               and (day is None or any(s.get('day_index') == day for s in c.get('slots', [])))
               and all(w in ' '.join(str(c.get(k) or '') for k in ('name','professor','department','sbjt_cd','lt_no')).casefold() for w in words)]
    return {'courses': matches[offset:offset+limit], 'total': len(matches),
            'departments': sorted({c['department'] for c in rows if c.get('department')}),
            'classifications': sorted({v for c in rows for v in c.get('classification', [])})}

@lru_cache(maxsize=1)
def curricula():
    return json.loads(gzip.decompress((ROOT / 'curriculum.json.gz').read_bytes()))

def curriculum(rule_id):
    result = curricula()['rules'].get(rule_id)
    if result is None:
        raise HTTPException(404, '해당 학번의 이수규정 자료가 없습니다.')
    # Keep the versioned source intact; decode entities as text, never as HTML.
    def decode(value):
        if isinstance(value,str): return html.unescape(html.unescape(value)).replace('\xa0',' ')
        if isinstance(value,list): return [decode(v) for v in value]
        if isinstance(value,dict): return {k:decode(v) for k,v in value.items()}
        return value
    result = decode(result)
    result['raw_notes'] = list(result.get('notes',[]))
    result['needs_verification'] = bool(re.search(r'가정|근사|미확인|미검증|BASELINE-ASSUMED',json.dumps(result,ensure_ascii=False)))
    notes = []
    for note in result.get('notes',[]):
        if '후속: Claude_Preview' in note:
            notes.append('정확한 전공 학점과 필수 과목은 학과 사무실 또는 학교 학사규정에서 확인해주세요.')
            continue
        if '철학과 홈페이지' in note and 'SPA-blocked' in note:
            notes.append('철학과의 정확한 전공 학점과 필수 과목을 확인하지 못했습니다. 현재 단일전공 60학점, 다전공 주전공·복수전공 39학점, 부전공 21학점을 임시 기준으로 표시합니다. 필수 과목 목록은 제공되지 않으며, 학과 확인이 필요합니다.')
            continue
        note = re.sub(r'교양 = \w+ 어댑터', '교양 이수 기준', note)
        note = re.sub(r'\(hum_\d+\)', '', note)
        note = re.sub(r'\b[\w/]+\.md', '원본 자료', note)
        for old,new in [('frameset/JS 게이트(euc-kr) SPA-blocked','공식 페이지 확인 불가'),('SPA-blocked','공식 페이지 확인 불가'),('BASELINE-ASSUMED(전항목)','전체 수치 임시 기준'),('인문대 standard','인문대 공통 기준'),('required.all 미생성','필수 과목 목록 미제공'),('required.all 비움','필수 과목 목록 미제공'),('required.all에서 제외','필수 과목 목록에서 제외'),('required_credits=','필수 학점 '),('major_required_known','확인된 필수 과목'),('og:description meta(본문은 Elementor SPA 스텁)','검색용 요약 정보(본문 확인 불가)')]:
            note=note.replace(old,new)
        notes.append(note)
    result['notes']=notes
    from .curriculum_display import present, source_links
    links=source_links(result['source']) if result.get('source') else []
    result.pop('raw_notes',None)
    result=present(result)
    result['source']='Class Checker 가공 자료 · 학과별 공식 안내를 함께 확인해주세요.'
    result['source_links']=links
    return result

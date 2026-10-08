"""Curated school names, official department sources and integration capability."""
import json
import re
from pathlib import Path

SCHOOLS = ('서울대학교','KAIST','포항공과대학교','연세대학교','고려대학교','서강대학교',
           '성균관대학교','한양대학교','GIST','DGIST','UNIST')
ALIASES = {'서울대':'서울대학교','snu':'서울대학교','카이스트':'KAIST','kaist':'KAIST','한국과학기술원':'KAIST',
    '포스텍':'포항공과대학교','포항공대':'포항공과대학교','postech':'포항공과대학교',
    '연세대':'연세대학교','연대':'연세대학교','고려대':'고려대학교','고대':'고려대학교',
    '서강대':'서강대학교','성균관대':'성균관대학교','성대':'성균관대학교','한양대':'한양대학교',
    '지스트':'GIST','gist':'GIST','광주과학기술원':'GIST','디지스트':'DGIST','디지트스':'DGIST',
    'dgist':'DGIST','대구경북과학기술원':'DGIST','유니스트':'UNIST','unist':'UNIST','울산과학기술원':'UNIST'}
DATA_PATH = Path(__file__).parent/'data/campuses/directory.json'

def data():
    return json.loads(DATA_PATH.read_text()) if DATA_PATH.exists() else {}

def departments(name):
    from . import campus_catalog
    names = set(data().get(name,{}).get('departments',[]))
    if name == '서울대학교':
        from .snu_catalog import curricula
        names.update(r['major'] for r in curricula()['index'])
    names.update((campus_catalog.index(name) or {}).get('departments',[]))
    return sorted(names)

def normalize_department(name, value):
    key = re.sub(r'\s+', '', value).casefold()
    matches = [d for d in departments(name) if re.sub(r'\s+', '', d).casefold() == key]
    return matches[0] if len(matches)==1 else value.strip()

def capabilities(name):
    from .campus_catalog import index
    meta = index(name)
    return {'catalog': name=='서울대학교' or bool(meta and meta['terms']),
            'meals':name=='서울대학교','rules':name=='서울대학교',
            'catalogTerms': [t['label'] for t in (meta or {}).get('terms',[])],
            'catalogUpdatedAt':(meta or {}).get('sourceUpdatedAt',''),
            'officialLinks':data().get(name,{}).get('links',[])}

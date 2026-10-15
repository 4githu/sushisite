"""Conditional, background-only public snapshot refresh. Search never waits on the source."""
import gzip,json,threading,os
from datetime import datetime,timezone
from pathlib import Path
import httpx
from fastapi import HTTPException
from .snu_catalog import ROOT,metadata
from .db import DB_PATH
CACHE=DB_PATH.parent/'trend-cache'
SOURCE='https://rekhet.github.io/class-checker/data/'
stop=threading.Event()
status={'lastSuccess':None,'error':None}

def refresh():
    CACHE.mkdir(parents=True,exist_ok=True)
    with httpx.Client(timeout=20,follow_redirects=True) as client:
        index=client.get(SOURCE+'classes/index.json');index.raise_for_status()
        for term in index.json()['terms']:
            if not term.get('trend'):continue
            name=term['trend']
            if Path(name).name!=name or not name.endswith('.json'):continue
            names=[name]+[name.replace('.json',f'_w{i:03}.json') for i in range(int(term.get('trendArchives',0)))]
            for filename in names:
                target=CACHE/filename
                if filename!=name and (target.exists() or (ROOT/'trend'/f'{filename}.gz').exists()):continue
                tag=target.with_suffix('.etag');headers={'If-None-Match':tag.read_text()} if tag.exists() else {}
                r=client.get(SOURCE+'trend/'+filename,headers=headers)
                if r.status_code==304:continue
                r.raise_for_status();payload=r.json()
                if not isinstance(payload.get('t'),list) or not isinstance(payload.get('series'),dict):raise ValueError('인원 추이 자료 형식이 변경되었습니다.')
                tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(payload));tmp.replace(target)
                if r.headers.get('etag'):tag.write_text(r.headers['etag'])
    status.update(lastSuccess=datetime.now(timezone.utc).isoformat(),error=None)

def loop():
    while not stop.is_set():
        try:refresh()
        except Exception:status['error']='공개 데이터 갱신에 실패했습니다. 마지막 관측 자료를 표시합니다.'
        stop.wait(600)
def start():
    if os.getenv('DISABLE_TREND_REFRESH')=='1':return
    stop.clear();threading.Thread(target=loop,daemon=True,name='course-trends').start()

def read(term,code,section,window='live'):
    if not any(t['id']==term for t in metadata()['terms']):raise HTTPException(404,'학기를 찾을 수 없습니다.')
    base=f'trend_{term}'
    available=set(p.name.removesuffix('.gz').removeprefix(base+'_').removesuffix('.json') for root in [ROOT/'trend',CACHE] for p in root.glob(base+'_w*.json*') if p.name.endswith(('.json','.json.gz')))
    if window!='live' and window not in available:raise HTTPException(404,'해당 구간의 자료가 없습니다.')
    filename=base+('' if window=='live' else '_'+window)+'.json'
    if (CACHE/filename).exists():data=json.loads((CACHE/filename).read_text())
    elif (ROOT/'trend'/f'{filename}.gz').exists():data=json.loads(gzip.decompress((ROOT/'trend'/f'{filename}.gz').read_bytes()))
    else:return {'points':[],'windows':[],'observedAt':None,'error':'이 학기는 수집된 인원 추이 자료가 없습니다.'}
    series=data['series'].get(f'{code}({section})',{})
    def values(encoded):
        if not isinstance(encoded,list):return [encoded]*len(data['t'])
        changes=dict(zip(encoded[::2],encoded[1::2]));current=None;result=[]
        for i in range(len(data['t'])):
            current=changes.get(i,current);result.append(current)
        return result
    metrics={k:values(series.get(k)) for k in ('a','e','c','q')}
    points=[{'time':t,'applied':metrics['a'][i],'enrolled':metrics['e'][i],'cart':metrics['c'][i],'capacity':metrics['q'][i]} for i,t in enumerate(data['t'])] if series else []
    observed=data.get('updated')
    from zoneinfo import ZoneInfo
    stale=not data['t'] or datetime.now(timezone.utc).timestamp()-data['t'][-1]>1800
    return {'points':points,'windows':sorted(available)+['live'],'observedAt':observed,'stale':stale,'lastSuccess':status['lastSuccess'],'error':status['error'],'source':SOURCE+'trend/'+filename}

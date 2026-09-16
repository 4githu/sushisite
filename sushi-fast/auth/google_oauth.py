"""Server-side Google authorization, bound to a browser nonce and one-use state."""
import base64
import hashlib
import os
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from auth import JMT, userdb, sushihash
from personal_project.db import connection
from personal_project import workspace  # additive tables

router = APIRouter(prefix='/auth/google', tags=['google'])
HOSTS = {'chobab.app','aura.chobab.app','rehear.chobab.app','calender.chobab.app','calendar.chobab.app','localhost','127.0.0.1'}


def credentials(kind):
    prefix='REHEAR' if kind=='rehear' else 'CALANDER'
    client=os.getenv(f'{prefix}_OATHID') or os.getenv('GOOGLE_CLIENT_ID')
    secret=os.getenv('REHEAR_OATHKEY' if kind=='rehear' else 'CLADNDER_OATHKEY') or os.getenv('CALANDER_OATHKEY') or os.getenv('GOOGLE_CLIENT_SECRET')
    if not client or not secret: raise HTTPException(503,'구글 OAuth Client ID와 Secret 설정이 필요합니다.')
    return client.strip(),secret.strip()


def cipher():
    key=os.getenv('GOOGLE_TOKEN_ENCRYPTION_KEY') or os.getenv('JWT_SECRET_KEY')
    if not key: raise HTTPException(503,'서버 토큰 암호화 키가 필요합니다.')
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('google-tokens-v1:'+key).encode()).digest()))


def origin(request):
    host=request.url.hostname
    if host not in HOSTS: raise HTTPException(400,'등록되지 않은 서비스 주소입니다.')
    if host in ('localhost','127.0.0.1'):
        return f'http://{request.headers.get("host")}'
    return f'https://{host}'


def safe_return(path):
    if not path.startswith('/') or path.startswith('//') or '\\' in path or any(ord(c)<32 for c in path):
        raise HTTPException(400,'잘못된 복귀 주소입니다.')
    return path


@router.get('/start')
def start(request: Request, purpose: str='login', return_to: str='/personal-project/calendar'):
    if purpose not in ('login','calendar'): raise HTTPException(400,'잘못된 연결 방식입니다.')
    base=origin(request)
    kind='rehear' if request.url.hostname=='rehear.chobab.app' or return_to.startswith('/odi') else 'calendar'
    client,_=credentials(kind)
    user_id=None
    if purpose=='calendar': user_id=int(JMT.check_jwt(request,'mainauth')['sub'])
    nonce=secrets.token_urlsafe(32); state=secrets.token_urlsafe(32); verifier=secrets.token_urlsafe(48)
    callback=base+'/auth/google/callback'
    with connection() as db:
        db.execute('DELETE FROM google_oauth_states WHERE expires<?',(int(time.time()),))
        db.execute('INSERT INTO google_oauth_states VALUES(?,?,?,?,?,?,?,?,?)',(state,verifier,hashlib.sha256(nonce.encode()).hexdigest(),user_id,purpose,kind,callback,safe_return(return_to),int(time.time())+600))
        db.commit()
    scopes='openid email profile'
    if purpose=='calendar': scopes+=' https://www.googleapis.com/auth/calendar.calendarlist.readonly https://www.googleapis.com/auth/calendar.events'
    query=dict(client_id=client,redirect_uri=callback,response_type='code',scope=scopes,state=state,
        code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode(),code_challenge_method='S256',prompt='select_account')
    if purpose=='calendar': query.update(access_type='offline',prompt='consent select_account')
    response=RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(query))
    response.set_cookie('google_oauth_nonce',nonce,max_age=600,httponly=True,secure=base.startswith('https:'),samesite='lax',path='/auth/google')
    return response


def google_identity(info):
    if not info.get('email_verified') or not info.get('sub') or not info.get('email'):
        raise HTTPException(400,'인증된 구글 이메일을 확인할 수 없습니다.')
    email=info['email'].strip().lower()
    with userdb.get_connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS google_identities(subject TEXT PRIMARY KEY,user_id INTEGER NOT NULL UNIQUE)')
        found=db.execute('SELECT user_id FROM google_identities WHERE subject=?',(info['sub'],)).fetchone()
        if found: return dict(db.execute('SELECT * FROM users WHERE id=?',(found['user_id'],)).fetchone())
        existing=db.execute('SELECT * FROM users WHERE lower(email)=?',(email,)).fetchone()
        if existing:
            # Google is authoritative for Gmail and hosted Workspace email. Other domains need explicit linking.
            if not email.endswith('@gmail.com') and not info.get('hd'):
                raise HTTPException(409,'기존 계정과의 안전한 연결이 필요합니다. 기존 이메일 로그인을 사용해주세요.')
            user_id=existing['id']
        else:
            password=sushihash.make_hash(secrets.token_urlsafe(16))
            cur=db.execute('INSERT INTO users(email,password_hash,name,created_at,email_verified) VALUES(?,?,?,?,1)',(email,password,info.get('name') or email.split('@')[0],datetime.now(timezone.utc).isoformat()))
            user_id=cur.lastrowid
        db.execute('INSERT INTO google_identities VALUES(?,?)',(info['sub'],user_id)); db.commit()
        return dict(db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone())


@router.get('/callback')
def callback(request: Request, state: str='', code: str='', error: str=''):
    base=origin(request)
    nonce=request.cookies.get('google_oauth_nonce','')
    with connection() as db:
        row=db.execute('SELECT * FROM google_oauth_states WHERE state=?',(state,)).fetchone()
        if not row or row['expires']<time.time() or not secrets.compare_digest(row['browser_hash'],hashlib.sha256(nonce.encode()).hexdigest()) or row['redirect_uri']!=base+'/auth/google/callback':
            raise HTTPException(400,'구글 연결 요청이 만료되었습니다. 다시 시작해주세요.')
        db.execute('DELETE FROM google_oauth_states WHERE state=?',(state,)); db.commit()
    return_to=row['return_to']
    def result(query):
        response=RedirectResponse(base+return_to+('&' if '?' in return_to else '?')+urlencode(query),status_code=303)
        response.delete_cookie('google_oauth_nonce',path='/auth/google')
        return response
    if error or not code: return result({'google_error':'cancelled'})
    client,secret=credentials(row['client_kind'])
    try:
        with httpx.Client(timeout=25) as http:
            token=http.post('https://oauth2.googleapis.com/token',data=dict(client_id=client,client_secret=secret,code=code,redirect_uri=row['redirect_uri'],grant_type='authorization_code',code_verifier=row['verifier']))
            token.raise_for_status(); tokens=token.json()
            profile=http.get('https://openidconnect.googleapis.com/v1/userinfo',headers={'Authorization':'Bearer '+tokens['access_token']})
            profile.raise_for_status(); info=profile.json()
    except (httpx.HTTPError,KeyError,ValueError): return result({'google_error':'exchange_failed'})
    if not info.get('email_verified') or not info.get('sub'): return result({'google_error':'unverified_email'})
    if row['purpose']=='calendar':
        # The callback remains tied to the same app user, never to the newly selected Google account.
        try: current=int(JMT.check_jwt(request,'mainauth')['sub'])
        except HTTPException: return result({'google_error':'session_expired'})
        if current!=row['user_id']: return result({'google_error':'session_changed'})
        scopes=tokens.get('scope','')
        required={'https://www.googleapis.com/auth/calendar.events','https://www.googleapis.com/auth/calendar.calendarlist.readonly'}
        if not required.issubset(set(scopes.split())): return result({'google_error':'calendar_permission'})
        with connection() as db:
            old=db.execute('SELECT * FROM google_accounts WHERE user_id=? AND subject=?',(current,info['sub'])).fetchone()
            refresh=cipher().encrypt(tokens['refresh_token'].encode()).decode() if tokens.get('refresh_token') else old['refresh_token'] if old else None
            if not refresh: return result({'google_error':'refresh_missing'})
            db.execute('''INSERT INTO google_accounts(user_id,subject,email,client_kind,refresh_token,scopes) VALUES(?,?,?,?,?,?)
                ON CONFLICT(user_id,subject) DO UPDATE SET email=excluded.email,client_kind=excluded.client_kind,refresh_token=excluded.refresh_token,scopes=excluded.scopes,error=NULL''',
                (current,info['sub'],info['email'],row['client_kind'],refresh,scopes)); db.commit()
        return result({'google':'connected'})
    try: user=google_identity(info)
    except HTTPException: return result({'google_error':'account_link_required'})
    response=result({'google':'signed_in'})
    response.set_cookie('mainauth',JMT.make_jwt(user['id'],user,['id','name','email']),httponly=True,secure=base.startswith('https:'),samesite='lax',path='/',max_age=3600)
    if row['client_kind']=='rehear':
        from odi.db import odidb
        odi=odidb.get_user_by_auth_id(str(user['id']))
        if not odi:
            odidb.create_user(str(user['id']),{
                'owner_id':str(user['id']),
                'profile':{'nickname':user['name'],'level':'새싹 보이스','current_exp':0,'next_level_exp':300},
                'statistics':{'session_count':0,'practice_minutes':0,'current_streak':0,'best_streak':0},
                'preferences':{'report_view_version':'v3','show_timeline_video':True},
                'favorite_templates':[], 'recent_sessions':[], 'evc_trend':[]
            },auth_id=str(user['id']))
            odi=odidb.get_user_by_auth_id(str(user['id']))
        response.set_cookie('odi_token',JMT.make_jwt(odi['user_id'],odi,['user_id','auth_id']),httponly=True,secure=base.startswith('https:'),samesite='lax',path='/',max_age=3600)
    return response


def access_token(account):
    client,secret=credentials(account['client_kind'])
    response=httpx.post('https://oauth2.googleapis.com/token',data={'client_id':client,'client_secret':secret,'grant_type':'refresh_token','refresh_token':cipher().decrypt(account['refresh_token'].encode()).decode()},timeout=20)
    if response.status_code!=200: raise HTTPException(409,'Google 계정 연결이 만료되었습니다. 계정을 다시 연결해주세요.')
    return response.json()['access_token']

"""Owner-approved, PKCE OAuth for the private MCP connection.

All durable authorization state is encrypted in Postgres. Access/refresh/code
lookups use hashes. Rotations and one-time code consumption are transactional.
No process-local OAuth state is needed on the free, cold-starting API host.
"""
import json
import os
import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlsplit, urlencode
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from mcp.server.auth.provider import AuthorizationCode, AccessToken, RefreshToken, AuthorizationParams, TokenError, RegistrationError, AuthorizeError, construct_redirect_uri
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from . import schema as s
from .db import engine
from .security import cipher, digest, owner

BASE=os.getenv('ASSISTANT_PUBLIC_URL','https://life-os-api-six.vercel.app').rstrip('/')
RESOURCE=BASE+'/mcp'
SCOPES=['lifeos:read','lifeos:write']
router=APIRouter(prefix='/api/assistant')


def save(conn,key,kind,data,seconds):
    conn.execute(sa.insert(s.assistant_oauth).values(key=key,kind=kind,ciphertext=cipher().encrypt(json.dumps(data).encode()).decode(),expires_at=s.now()+timedelta(seconds=seconds)))


def get(conn,key,lock=False):
    q=sa.select(s.assistant_oauth).where(s.assistant_oauth.c.key==key,s.assistant_oauth.c.expires_at>s.now())
    row=conn.execute(q.with_for_update() if lock else q).mappings().first()
    return json.loads(cipher().decrypt(row['ciphertext']).decode()) if row else None


def remove(conn,key): conn.execute(sa.delete(s.assistant_oauth).where(s.assistant_oauth.c.key==key))


def issue(conn,client_id,scopes,resource,family=None):
    family=family or secrets.token_urlsafe(24)
    access=secrets.token_urlsafe(48); refresh=secrets.token_urlsafe(48)
    common={'client_id':client_id,'scopes':scopes,'resource':resource,'family':family}
    access_data={**common,'token':access,'expires_at':int(s.now().timestamp())+3600}
    refresh_data={**common,'token':refresh,'expires_at':int(s.now().timestamp())+30*86400,'access_key':'access/'+digest(access)}
    save(conn,'access/'+digest(access),'access',access_data,3600)
    save(conn,'refresh/'+digest(refresh),'refresh',refresh_data,30*86400)
    # A family record is the revocation authority checked on each access-token use.
    if not get(conn,'family/'+family): save(conn,'family/'+family,'family',{'client_id':client_id},365*86400)
    return OAuthToken(access_token=access,refresh_token=refresh,expires_in=3600,scope=' '.join(scopes))


class LifeOSOAuth:
    async def get_client(self,client_id):
        with engine.connect() as conn: data=get(conn,'client/'+client_id)
        return OAuthClientInformationFull.model_validate(data) if data else None

    async def register_client(self,client_info):
        # Only ChatGPT may receive authorization redirects. The SDK additionally
        # requires exact equality with the URI registered by this client.
        for uri in client_info.redirect_uris or []:
            u=urlsplit(str(uri))
            if u.scheme!='https' or u.hostname not in {'chatgpt.com','chat.openai.com'} or u.port not in (None,443) or u.username or u.password or u.fragment:
                raise RegistrationError(error='invalid_redirect_uri',error_description='This private connection only supports ChatGPT HTTPS callbacks')
        if len(client_info.model_dump_json())>20000: raise RegistrationError(error='invalid_client_metadata',error_description='Client metadata is too large')
        with engine.begin() as conn:
            conn.execute(sa.delete(s.assistant_oauth).where(s.assistant_oauth.c.expires_at<s.now()))
            # Bound unauthenticated registration storage without exposing account data.
            if conn.execute(sa.select(sa.func.count()).select_from(s.assistant_oauth).where(s.assistant_oauth.c.kind=='client',s.assistant_oauth.c.created_at>s.now()-timedelta(hours=1))).scalar_one()>=20:
                raise RegistrationError(error='invalid_client_metadata',error_description='Please try registration later')
            save(conn,'client/'+client_info.client_id,'client',client_info.model_dump(mode='json'),365*86400)

    async def authorize(self,client,params:AuthorizationParams):
        if params.resource and params.resource.rstrip('/')!=RESOURCE:
            raise AuthorizeError(error='invalid_request',error_description='Incorrect Life OS resource')
        if not params.code_challenge:
            raise AuthorizeError(error='invalid_request',error_description='PKCE is required')
        nonce=secrets.token_urlsafe(32)
        with engine.begin() as conn:
            count=conn.execute(sa.select(sa.func.count()).select_from(s.assistant_oauth).where(s.assistant_oauth.c.kind=='pending',s.assistant_oauth.c.expires_at>s.now())).scalar_one()
            if count>=100: raise AuthorizeError(error='server_error',error_description='Please try again later')
            save(conn,'pending/'+digest(nonce),'pending',{'client_id':client.client_id,'params':params.model_dump(mode='json')},600)
        return BASE+'/api/assistant/connect?'+urlencode({'request':nonce})

    async def load_authorization_code(self,client,authorization_code):
        with engine.connect() as conn: data=get(conn,'code/'+digest(authorization_code))
        if not data or data['client_id']!=client.client_id: return None
        return AuthorizationCode.model_validate(data)

    async def exchange_authorization_code(self,client,authorization_code):
        key='code/'+digest(authorization_code.code)
        with engine.begin() as conn:
            data=get(conn,key,True)
            if not data or data['client_id']!=client.client_id: raise TokenError(error='invalid_grant',error_description='Authorization code expired or already used')
            remove(conn,key)
            return issue(conn,client.client_id,data['scopes'],RESOURCE)

    async def load_refresh_token(self,client,refresh_token):
        with engine.connect() as conn:
            data=get(conn,'refresh/'+digest(refresh_token))
            if not data or data['client_id']!=client.client_id or not get(conn,'family/'+data['family']): return None
        return RefreshToken.model_validate(data)

    async def exchange_refresh_token(self,client,refresh_token,scopes):
        key='refresh/'+digest(refresh_token.token)
        with engine.begin() as conn:
            data=get(conn,key,True)
            if not data or data['client_id']!=client.client_id or not get(conn,'family/'+data['family']): raise TokenError(error='invalid_grant',error_description='Refresh token expired or already used')
            if not set(scopes)<=set(data['scopes']): raise TokenError(error='invalid_scope',error_description='Cannot increase permissions during refresh')
            remove(conn,key); remove(conn,data['access_key'])
            return issue(conn,client.client_id,scopes,data['resource'],data['family'])

    async def load_access_token(self,token):
        with engine.connect() as conn:
            data=get(conn,'access/'+digest(token))
            if not data or data['resource']!=RESOURCE or not get(conn,'family/'+data['family']): return None
        return AccessToken.model_validate(data)

    async def revoke_token(self,token):
        prefix='access/' if isinstance(token,AccessToken) else 'refresh/'
        with engine.begin() as conn:
            data=get(conn,prefix+digest(token.token),True)
            if data: remove(conn,'family/'+data['family'])
            remove(conn,prefix+digest(token.token))


@router.get('/connect', response_class=HTMLResponse)
def connection_page(request:str):
    with engine.connect() as conn: pending=get(conn,'pending/'+digest(request))
    if not pending: raise HTTPException(400,'This connection request expired. Start again from ChatGPT.')
    # The nonce never appears in inline JS/HTML. It is read from the current URL.
    return HTMLResponse('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Connect Life OS to ChatGPT</title>
<style>body{background:#f3f4ef;color:#222e27;font:16px system-ui;display:grid;min-height:95vh;place-items:center}main{max-width:430px;padding:36px;background:white;border:1px solid #ddd;border-radius:20px}label{display:block;margin:18px 0 6px}input,button{box-sizing:border-box;padding:13px;width:100%;border:1px solid #ccc;border-radius:8px;font:inherit}button{margin-top:22px;background:#243d30;color:white;cursor:pointer}small{color:#536158}#error{color:#9e2929}</style>
<main><small>LIFE OS · PRIVATE CONNECTION</small><h1>Continue with ChatGPT</h1><p>Allow ChatGPT to read your saved health metrics, journal summaries, plans and learning records, and save the updates you request.</p><p>Chats in your Life OS project opt in. In other chats, call Life OS when you want it involved. You can revoke this connection in Life OS Settings.</p><form><label for="user">Life OS username</label><input id="user" autocomplete="username" value="owner" required><label for="password">Life OS password</label><input id="password" type="password" autocomplete="current-password" required><button>Connect Life OS</button><p id="error" role="alert"></p></form></main>
<script>document.querySelector('form').onsubmit=async e=>{e.preventDefault();let b=document.querySelector('button');b.disabled=true;document.querySelector('#error').textContent='';try{let r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.querySelector('#user').value,password:document.querySelector('#password').value})});let d=await r.json();if(!r.ok)throw Error(d.detail||'Sign-in failed');document.querySelector('#password').value='';r=await fetch('/api/assistant/approve',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+d.token},body:JSON.stringify({request:new URLSearchParams(location.search).get('request')})});d=await r.json();if(!r.ok)throw Error(d.detail||'Connection failed');location.assign(d.redirect);}catch(e){document.querySelector('#error').textContent=e.message;b.disabled=false}};</script></html>''',headers={'Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})


@router.post('/approve',dependencies=[Depends(owner)])
def approve(payload:dict):
    key='pending/'+digest(str(payload.get('request','')))
    with engine.begin() as conn:
        pending=get(conn,key,True)
        if not pending: raise HTTPException(400,'Connection request expired or already used')
        remove(conn,key)
        params=AuthorizationParams.model_validate(pending['params'])
        code=secrets.token_urlsafe(40)
        auth=AuthorizationCode(code=code,scopes=params.scopes or SCOPES,expires_at=s.now().timestamp()+120,client_id=pending['client_id'],code_challenge=params.code_challenge,redirect_uri=params.redirect_uri,redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,resource=RESOURCE)
        save(conn,'code/'+digest(code),'code',auth.model_dump(mode='json'),120)
        return {'redirect':construct_redirect_uri(str(params.redirect_uri),code=code,**({'state':params.state} if params.state else {}))}


@router.get('/connection',dependencies=[Depends(owner)])
def connection_status():
    with engine.connect() as conn:
        count=conn.execute(sa.select(sa.func.count()).select_from(s.assistant_oauth).where(s.assistant_oauth.c.kind=='family',s.assistant_oauth.c.expires_at>s.now())).scalar_one()
    return {'authorized_connections':count,'mcp_url':RESOURCE,'morning_time':'09:00','timezone':'Asia/Kolkata','schedule_verified':False}


@router.post('/disconnect',dependencies=[Depends(owner)])
def disconnect():
    with engine.begin() as conn:
        conn.execute(sa.delete(s.assistant_oauth).where(s.assistant_oauth.c.kind.in_(['family','access','refresh','code','pending'])))
    return {'disconnected':True}

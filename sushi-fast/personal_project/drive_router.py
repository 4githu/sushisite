"""Authenticated personal drive HTTP endpoints."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
import tempfile

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.requests import ClientDisconnect
from starlette.concurrency import run_in_threadpool

from . import drive
from . import drive_library as library
from .router import current_user_id

router=APIRouter(prefix='/api/personal/drive',tags=['personal-drive'])


class Note(BaseModel):
    title: str=Field(default='',max_length=120)
    text: str=Field(min_length=1,max_length=200000)
    bucket: str='transfer'
    provider: str='local'
    account_id: int | None=None


class Move(BaseModel):
    bucket: str


class UploadStart(BaseModel):
    name: str=Field(min_length=1,max_length=200)
    bucket: str='transfer'
    provider: str='local'
    account_id: int | None=None
    total_bytes: int=Field(gt=0,le=drive.MAX_UPLOAD)
    replace_item_id: str | None=None


class TextWrite(BaseModel):
    text: str=Field(max_length=1_000_000)

class FolderCreate(BaseModel):
    name: str=Field(min_length=1,max_length=120)
    bucket: str='archive'
    parent_id: str | None=None

class Organize(BaseModel):
    name: str=Field(min_length=1,max_length=200)
    folder_id: str | None=None

class ShareCreate(BaseModel):
    days: int=Field(default=7,ge=1,le=30)

@router.get('/library')
def folder_library(bucket: str='archive',folder_id: str | None=None,user_id: int=Depends(current_user_id)):
    return library.library(user_id,bucket,folder_id)

@router.post('/folders',status_code=201)
def create_folder(data: FolderCreate,user_id: int=Depends(current_user_id)):
    return library.create_folder(user_id,data.name,data.bucket,data.parent_id)

@router.delete('/folders/{folder_id}',status_code=204)
def delete_folder(folder_id: str,user_id: int=Depends(current_user_id)):
    library.delete_folder(user_id,folder_id)
    return Response(status_code=204)

@router.put('/items/{item_id}/organization')
def organize(item_id: str,data: Organize,user_id: int=Depends(current_user_id)):
    library.organize(user_id,item_id,data.name,data.folder_id)
    return {'ok':True}

@router.post('/items/{item_id}/share')
def create_share(item_id: str,data: ShareCreate,user_id: int=Depends(current_user_id)):
    return library.share(user_id,item_id,data.days)

@router.delete('/items/{item_id}/share',status_code=204)
def revoke_share(item_id: str,user_id: int=Depends(current_user_id)):
    library.revoke(user_id,item_id)
    return Response(status_code=204)

@router.get('/shared/{token}')
def shared_info(token: str,response: Response):
    item=library.shared_item(token)
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    return {'name':item['name'],'byteSize':item['byte_size'],'mimeType':item['mime_type']}

@router.get('/shared/{token}/content')
def shared_content(token: str):
    item=library.shared_item(token)
    result=content(item['id'],False,item['user_id'])
    result.headers['Referrer-Policy']='no-referrer'
    return result


@router.get('/status')
def status(user_id: int=Depends(current_user_id)):
    return drive.status(user_id)


@router.get('/items')
def items(bucket: str='transfer',user_id: int=Depends(current_user_id)):
    return drive.items(user_id,bucket)


@router.post('/upload/sessions',status_code=201)
def start_upload(data: UploadStart,user_id: int=Depends(current_user_id)):
    return drive.start_upload(user_id,data.name,data.bucket,data.provider,data.account_id,data.total_bytes,data.replace_item_id)


@router.put('/upload/sessions/{upload_id}/chunk')
async def chunk(upload_id: str,request: Request,offset: int,user_id: int=Depends(current_user_id)):
    chunks=[]; size=0
    try:
        async for piece in request.stream():
            size+=len(piece)
            if size>drive.MAX_CHUNK: raise HTTPException(413,'업로드 조각은 8MB 이하여야 합니다.')
            chunks.append(piece)
    except ClientDisconnect:
        drive.cancel_upload(user_id,upload_id)
        raise HTTPException(400,'파일 전송이 중간에 끊겼습니다. 연결을 확인한 뒤 다시 올려주세요.')
    return await run_in_threadpool(drive.append_chunk,user_id,upload_id,offset,b''.join(chunks))


@router.post('/upload/sessions/{upload_id}/finish',status_code=201)
async def finish(upload_id: str,user_id: int=Depends(current_user_id)):
    return await run_in_threadpool(drive.finish_upload,user_id,upload_id)


@router.delete('/upload/sessions/{upload_id}',status_code=204)
def cancel(upload_id: str,user_id: int=Depends(current_user_id)):
    drive.cancel_upload(user_id,upload_id)
    return Response(status_code=204)


@router.post('/notes',status_code=201)
def note(data: Note,user_id: int=Depends(current_user_id)):
    payload=data.text.encode('utf-8')
    if len(payload)>1024*1024: raise HTTPException(413,'텍스트는 1MB 이하로 저장해주세요.')
    drive.ROOT.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=drive.ROOT,delete=False) as file:
        file.write(payload)
        path=Path(file.name)
    try:
        title=data.title.strip().replace('/','_').replace('\\','_') or f"메모-{drive.now().strftime('%Y%m%d-%H%M%S')}"
        if not title.lower().endswith('.md'): title+='.md'
        return drive.store(user_id,path,title,'text/markdown',data.bucket,data.provider,data.account_id,len(payload))
    finally:
        path.unlink(missing_ok=True)


@router.put('/items/{item_id}/text')
def update_text(item_id: str,data: TextWrite,user_id: int=Depends(current_user_id)):
    return drive.update_text(user_id,item_id,data.text)


@router.get('/items/{item_id}/preview')
def preview(item_id: str,user_id: int=Depends(current_user_id)):
    item=drive.item_for(user_id,item_id)
    suffix=Path(item['name']).suffix.lower()
    if suffix=='.docx': return {'kind':'text','text':drive.word_preview(item)}
    if suffix not in ('.txt','.md','.markdown','.csv','.json','.log'):
        raise HTTPException(415,'이 파일은 다운로드해서 확인해주세요.')
    try: text=drive.content(item,2*1024*1024).decode('utf-8-sig')
    except UnicodeError: raise HTTPException(422,'UTF-8 텍스트로 읽을 수 없습니다.')
    return {'kind':'text','text':text}


@router.get('/items/{item_id}/content')
def content(item_id: str,inline: bool=False,user_id: int=Depends(current_user_id)):
    item=drive.item_for(user_id,item_id)
    suffix=Path(item['name']).suffix.lower()
    previewable=suffix in ('.pdf','.png','.jpg','.jpeg','.webp','.gif')
    disposition='inline' if inline and previewable else 'attachment'
    headers={'Content-Disposition':f"{disposition}; filename*=UTF-8''{quote(item['name'],safe='')}",
             'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'}
    mime=item['mime_type'] if previewable else 'application/octet-stream'
    if item['provider']=='local':
        path=drive.local_path(user_id,item_id)
        if not path.is_file(): raise HTTPException(404,'파일 데이터를 찾을 수 없습니다.')
        return FileResponse(path,media_type=mime,headers=headers)
    account=drive.google_account(user_id,item['account_id'])
    def stream():
        with httpx.Client(timeout=180) as client:
            with client.stream('GET',drive.DRIVE_API+'/'+quote(item['remote_id'],safe=''),
                               params={'alt':'media'},headers=drive.google_headers(account)) as response:
                if response.status_code>=400: drive.google_checked(response)
                yield from response.iter_bytes()
    return StreamingResponse(stream(),media_type=mime,headers=headers)


@router.patch('/items/{item_id}')
def move(item_id: str,data: Move,user_id: int=Depends(current_user_id)):
    drive.move(user_id,item_id,data.bucket)
    return {'ok':True}


@router.delete('/items/{item_id}',status_code=204)
def delete(item_id: str,user_id: int=Depends(current_user_id)):
    drive.delete(user_id,item_id)
    return Response(status_code=204)

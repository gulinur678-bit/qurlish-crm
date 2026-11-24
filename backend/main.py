"""Single-company construction CRM API. Production inventory is NEVER automatically seeded."""
import os
import re
import hmac
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, DateTime, select, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, sessionmaker
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parent.parent
DB_URL = os.getenv('DATABASE_URL', 'sqlite:///./local-dev.db')
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql+psycopg://', 1)
engine = create_engine(DB_URL, connect_args={'check_same_thread': False} if DB_URL.startswith('sqlite') else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
SECRET = os.getenv('JWT_SECRET', '')
STAGES = ('new', 'contacted', 'qualified', 'closed_lost')

class Base(DeclarativeBase): pass
class Unit(Base):
    __tablename__ = 'units'
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    building: Mapped[str] = mapped_column(String(4))
    floor: Mapped[int] = mapped_column(Integer)
    number: Mapped[int] = mapped_column(Integer)
    rooms: Mapped[int] = mapped_column(Integer)
    area: Mapped[float] = mapped_column(Float)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='available')
class Staff(Base):
    __tablename__ = 'staff'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default='manager')
class Lead(Base):
    __tablename__ = 'leads'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[str] = mapped_column(ForeignKey('units.id'))
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(24))
    stage: Mapped[str] = mapped_column(String(20), default='new')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    unit: Mapped[Unit] = relationship()
class LeadEvent(Base):
    __tablename__ = 'lead_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey('leads.id'))
    actor: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    value: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
class Idempotency(Base):
    __tablename__ = 'idempotency'
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    lead_id: Mapped[int] = mapped_column(ForeignKey('leads.id'))

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title='Qurlish CRM API', lifespan=lifespan)

def db():
    with SessionLocal() as session: yield session

def unit_json(u):
    return {'id':u.id,'building':u.building,'floor':u.floor,'unit':u.number,'rooms':u.rooms,'area':u.area,'price':u.price,'status':u.status}

class LeadIn(BaseModel):
    unit_id: str
    name: str = Field(min_length=2,max_length=100)
    phone: str = Field(min_length=9,max_length=24)
    @field_validator('phone')
    @classmethod
    def valid_phone(cls,v):
        if not re.fullmatch(r'\+?[0-9 ()-]{9,24}',v) or len(re.sub(r'\D','',v)) < 9:
            raise ValueError('Telefon raqamini tekshiring')
        return v.strip()

class LoginIn(BaseModel):
    email: str
    password: str

class StageIn(BaseModel):
    stage: Literal['new','contacted','qualified','closed_lost']

class NoteIn(BaseModel):
    note: str = Field(min_length=1,max_length=1000)

class UnitStatusIn(BaseModel):
    status: Literal['available','reserved','sold']

# Argon2id with unique salt; constant-time verification via argon2-cffi.
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
_hasher = PasswordHasher()
def hash_password(password: str) -> str: return _hasher.hash(password)
def verify_password(password: str, hashed: str) -> bool:
    try: return _hasher.verify(hashed,password)
    except (VerifyMismatchError,VerificationError): return False

def staff(request:Request, session:Session=Depends(db)):
    token=request.cookies.get('crm_session')
    if not token or not SECRET: raise HTTPException(401,'Login talab qilinadi')
    try:
        payload=jwt.decode(token,SECRET,algorithms=['HS256'],options={'require':['exp','sub']})
        user=session.get(Staff,int(payload['sub']))
        if not user: raise ValueError()
        return user
    except (jwt.InvalidTokenError,ValueError,TypeError): raise HTTPException(401,'Sessiya tugagan')

def admin(user=Depends(staff)):
    if user.role!='admin': raise HTTPException(403,'Admin huquqi kerak')
    return user

# Cookie + same-origin enforcement: forbid cross-site state-changing requests.
@app.middleware('http')
async def origin_guard(request:Request,call_next):
    if request.url.path.startswith('/api/') and request.method in ('POST','PATCH','PUT','DELETE'):
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            return Response('Forbidden origin',status_code=403)
        if request.cookies.get('crm_session') and request.headers.get('sec-fetch-site') == 'cross-site':
            return Response('Forbidden cross-site request',status_code=403)
    return await call_next(request)

@app.get('/api/health')
def health(): return {'status':'ok'}

@app.get('/api/public/units')
def public_units(session:Session=Depends(db)):
    return {'units':[unit_json(u) for u in session.scalars(select(Unit).order_by(Unit.building,Unit.floor,Unit.number)).all()]}

@app.post('/api/public/leads',status_code=201)
def create_lead(payload:LeadIn,request:Request,session:Session=Depends(db)):
    key=request.headers.get('Idempotency-Key','')
    if not re.fullmatch(r'[a-zA-Z0-9-]{16,128}',key): raise HTTPException(400,'Idempotency-Key talab qilinadi')
    fingerprint=hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    with session.begin():
        previous=session.get(Idempotency,key)
        if previous:
            if not hmac.compare_digest(previous.payload_hash,fingerprint): raise HTTPException(409,'Kalit boshqa so‘rov uchun ishlatilgan')
            return {'id':previous.lead_id,'duplicate':True}
        unit=session.get(Unit,payload.unit_id,with_for_update=True)
        if not unit: raise HTTPException(404,'Xonadon topilmadi')
        if unit.status!='available':raise HTTPException(409,'Xonadon mavjud emas')
        lead=Lead(unit_id=unit.id,name=payload.name.strip(),phone=payload.phone)
        session.add(lead);session.flush()
        session.add(Idempotency(key=key,payload_hash=fingerprint,lead_id=lead.id))
        session.add(LeadEvent(lead_id=lead.id,actor='public',kind='created',value='Murojaat kelib tushdi'))
        lid=lead.id
    return {'id':lid,'duplicate':False}

@app.post('/api/auth/login')
def login(payload:LoginIn,response:Response,session:Session=Depends(db)):
    if not SECRET or len(SECRET)<32: raise HTTPException(503,'Server JWT_SECRET sozlanmagan')
    user=session.scalar(select(Staff).where(Staff.email==payload.email.strip().lower()))
    if not user or not verify_password(payload.password,user.password_hash):raise HTTPException(401,'Email yoki parol noto‘g‘ri')
    token=jwt.encode({'sub':str(user.id),'exp':datetime.now(timezone.utc)+timedelta(hours=8)},SECRET,algorithm='HS256')
    response.set_cookie('crm_session',token,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE','0')=='1',max_age=28800,path='/')
    return {'email':user.email,'role':user.role}

@app.post('/api/auth/logout')
def logout(response:Response,user=Depends(staff)):
    response.delete_cookie('crm_session',path='/');return {'ok':True}

@app.get('/api/crm/me')
def me(user=Depends(staff)): return {'email':user.email,'role':user.role}

def lead_json(l): return {'id':l.id,'unit_id':l.unit_id,'name':l.name,'phone':l.phone,'stage':l.stage,'created_at':l.created_at.isoformat()}

@app.get('/api/crm/leads')
def leads(days:int=30,session:Session=Depends(db),user=Depends(staff)):
    if days not in (7,30,90): raise HTTPException(422,'Davr 7, 30 yoki 90 kun')
    since=datetime.now(timezone.utc)-timedelta(days=days)
    ls=session.scalars(select(Lead).where(Lead.created_at>=since).order_by(Lead.created_at.desc())).all()
    return {'days':days,'leads':[lead_json(l) for l in ls]}

@app.get('/api/crm/metrics')
def metrics(days:int=30,session:Session=Depends(db),user=Depends(staff)):
    if days not in (7,30,90):raise HTTPException(422,'Davr 7, 30 yoki 90 kun')
    now=datetime.now(timezone.utc);since=now-timedelta(days=days)
    ls=session.scalars(select(Lead).where(Lead.created_at>=since)).all()
    counts={s:sum(l.stage==s for l in ls) for s in STAGES}
    bins=[0]*7
    for l in ls:
        elapsed=(l.created_at.replace(tzinfo=timezone.utc) if l.created_at.tzinfo is None else l.created_at)-since
        n=min(6,max(0,int(elapsed.total_seconds()/max(1,(now-since).total_seconds())*7)))
        bins[n]+=1
    statuses={s:session.scalar(select(func.count()).select_from(Unit).where(Unit.status==s)) for s in ('available','reserved','sold')}
    return {'days':days,'count':len(ls),'stages':counts,'bins':bins,'unit_statuses':statuses,'as_of':now.isoformat()}

@app.patch('/api/crm/leads/{lead_id}/stage')
def change_stage(lead_id:int,payload:StageIn,session:Session=Depends(db),user=Depends(staff)):
    l=session.get(Lead,lead_id)
    if not l:raise HTTPException(404,'Murojaat topilmadi')
    # Closing as successful sale is deliberately NOT a Kanban transition.
    if payload.stage not in STAGES:raise HTTPException(422,'Bosqich ruxsat etilmagan')
    old=l.stage;l.stage=payload.stage
    session.add(LeadEvent(lead_id=l.id,actor=user.email,kind='stage',value=f'{old} -> {l.stage}'))
    session.commit();return lead_json(l)

@app.get('/api/crm/leads/{lead_id}/events')
def get_events(lead_id:int,session:Session=Depends(db),user=Depends(staff)):
    if not session.get(Lead,lead_id):raise HTTPException(404,'Murojaat topilmadi')
    events=session.scalars(select(LeadEvent).where(LeadEvent.lead_id==lead_id).order_by(LeadEvent.created_at)).all()
    return [{'kind':e.kind,'actor':e.actor,'value':e.value,'created_at':e.created_at.isoformat()} for e in events]

@app.post('/api/crm/leads/{lead_id}/notes',status_code=201)
def add_note(lead_id:int,payload:NoteIn,session:Session=Depends(db),user=Depends(staff)):
    if not session.get(Lead,lead_id):raise HTTPException(404,'Murojaat topilmadi')
    session.add(LeadEvent(lead_id=lead_id,actor=user.email,kind='internal_note',value=payload.note))
    session.commit();return {'ok':True}

@app.patch('/api/crm/units/{unit_id}')
def change_unit(unit_id:str,payload:UnitStatusIn,session:Session=Depends(db),user=Depends(admin)):
    u=session.get(Unit,unit_id)
    if not u:raise HTTPException(404,'Xonadon topilmadi')
    # Sale confirmation requires a dedicated business-approved workflow; never silently sell.
    if payload.status=='sold' or u.status=='sold': raise HTTPException(409,'Sotuvni tasdiqlash jarayoni hali ishlab chiqilmagan')
    u.status=payload.status;session.commit();return unit_json(u)

@app.get('/staff')
def staff_page(): return FileResponse(ROOT/'staff.html')
app.mount('/',StaticFiles(directory=ROOT,html=True),name='web')

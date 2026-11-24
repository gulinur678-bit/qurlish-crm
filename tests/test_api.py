import os
import sys
from pathlib import Path
os.environ['DATABASE_URL']='sqlite://'
os.environ['JWT_SECRET']='test-secret-at-least-32-characters-long-123'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy.pool import StaticPool
import main
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

main.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
main.SessionLocal=sessionmaker(main.engine,expire_on_commit=False)
main.Base.metadata.create_all(main.engine)
with main.SessionLocal.begin() as s:
    s.add_all([main.Unit(id='A-101',building='A',floor=1,number=1,rooms=2,area=55.5,price=1000000,status='available'),main.Unit(id='A-102',building='A',floor=1,number=2,rooms=3,area=75.2,price=2000000,status='sold'),main.Staff(email='admin@test.local',password_hash=main.hash_password('safe-test-password-123'),role='admin'),main.Staff(email='manager@test.local',password_hash=main.hash_password('safe-test-password-123'),role='manager')])
client=TestClient(main.app)

def test_inventory_and_auth():
    assert client.get('/api/public/units').status_code==200
    assert client.get('/api/crm/leads').status_code==401
    assert client.post('/api/auth/login',json={'email':'admin@test.local','password':'wrong'}).status_code==401

def test_create_idempotency_sold_and_metrics():
    k='12345678-1234-1234-1234-123456789012'
    data={'unit_id':'A-101','name':'Sinov xaridor','phone':'+998901234567'}
    r=client.post('/api/public/leads',json=data,headers={'Idempotency-Key':k});assert r.status_code==201,r.text
    r2=client.post('/api/public/leads',json=data,headers={'Idempotency-Key':k});assert r2.json()['id']==r.json()['id']
    assert r2.json()['duplicate'] is True
    assert client.post('/api/public/leads',json={**data,'name':'Boshqa'},headers={'Idempotency-Key':k}).status_code==409
    assert client.post('/api/public/leads',json={**data,'unit_id':'A-102'},headers={'Idempotency-Key':'abcdefab-1234-1234-1234-123456789012'}).status_code==409
    assert client.post('/api/public/leads',json=data).status_code==400
    assert client.post('/api/auth/login',json={'email':'admin@test.local','password':'safe-test-password-123'}).status_code==200
    metrics=client.get('/api/crm/metrics?days=30').json();assert metrics['count']==1
    assert sum(metrics['bins'])==metrics['count']
    assert sum(metrics['stages'].values())==metrics['count']
    assert metrics['unit_statuses']['sold']==1
    assert client.patch('/api/crm/units/A-101',json={'status':'sold'}).status_code==409
    assert client.patch('/api/crm/leads/1/stage',json={'stage':'qualified'}).status_code==200
    assert client.post('/api/crm/leads/1/notes',json={'note':'Ichki xabar'}).status_code==201
    assert len(client.get('/api/crm/leads/1/events').json())==3

def test_staff_role_boundary():
    assert client.post('/api/auth/login',json={'email':'manager@test.local','password':'safe-test-password-123'}).status_code==200
    assert client.patch('/api/crm/units/A-101',json={'status':'reserved'}).status_code==403
    assert client.get('/api/crm/leads').status_code==200
    assert client.post('/api/auth/logout').status_code==200
    assert client.get('/api/crm/leads').status_code==401

def test_cross_origin():
    assert client.post('/api/public/leads',json={'unit_id':'A-101','name':'Test User','phone':'+998901234567'},headers={'Origin':'https://malicious.example','Idempotency-Key':'12345678-aaaa-bbbb-cccc-123456789012'}).status_code==403

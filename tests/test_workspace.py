from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.identity import AuditLog, Lead, LeadEvent, Unit
from backend.main import app
from test_api import _client, _login


def test_paginated_workspace_and_role_boundaries(tmp_path):
    client, factory, ids, engine = _client(tmp_path)
    try:
        admin = _login(client, 'admin@test.local')
        seller = _login(client, 'seller@test.local')
        viewer = _login(client, 'viewer@test.local')
        for headers in (admin, seller, viewer):
            units = client.get('/api/crm/units?page_size=1', headers=headers).json()
            assert units['total'] == 2
            assert len(units['units']) == 1
            assert units['filters']['buildings'] == ['A']
            leads = client.get('/api/crm/leads?days=30&page=1&page_size=1', headers=headers).json()
            assert leads['total'] == 1
            assert len(leads['leads']) == 1
            assert client.get(f'/api/crm/leads/{ids[1]}/detail', headers=headers).status_code == 404
            detail = client.get(f'/api/crm/leads/{ids[0]}/detail', headers=headers).json()
            assert detail['unit']['id'] == 'A-101'
        assert client.get('/api/crm/units?status=sold', headers=admin).json()['total'] == 1
        assert client.get('/api/crm/units?page_size=101', headers=admin).status_code == 422
        assert client.get('/api/crm/leads?days=10', headers=admin).status_code == 422
        assert client.get('/api/crm/leads?q=nomatch&page=1', headers=admin).json()['total'] == 0
        assert client.get('/api/admin/audit', headers=seller).status_code == 403
        assert client.get('/api/admin/users', headers=viewer).status_code == 403
        for headers in (seller, viewer):
            assert client.patch('/api/crm/units/A-101', headers=headers, json={'status':'reserved'}).status_code == 403
        assert client.patch('/api/crm/units/A-102', headers=admin, json={'status':'available'}).status_code == 409
        assert client.patch('/api/crm/units/B-101', headers=admin, json={'status':'reserved'}).status_code == 404
        assert client.patch('/api/crm/units/A-101', headers=admin, json={'status':'reserved'}).status_code == 200
        with factory() as session:
            assert session.get(Unit, 'A-101').status == 'reserved'
            session.add(AuditLog(company_id='other-co', action='private-other-company', resource_type='user'))
            session.commit()
        audit = client.get('/api/admin/audit?page_size=100', headers=admin).json()
        assert all(a['action'] != 'private-other-company' for a in audit['items'])
        assert all(set(a) == {'id','user_id','action','resource_type','resource_id','created_at'} for a in audit['items'])
        users = client.get('/api/admin/users?page=1&page_size=1&q=admin', headers=admin).json()
        assert users['total'] == 1
        assert 'password_hash' not in users['users'][0]
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()


def test_period_metrics_notes_and_persistence(tmp_path):
    client, factory, ids, engine = _client(tmp_path)
    try:
        seller = _login(client, 'seller@test.local')
        metrics = client.get('/api/crm/metrics?days=30', headers=seller).json()
        leads = client.get('/api/crm/leads', params={'days':30,'as_of':metrics['as_of'],'page':1}, headers=seller).json()
        assert sum(metrics['bins']) == metrics['count'] == sum(metrics['stages'].values()) == leads['total']
        assert sum(metrics['unit_statuses'].values()) == 2
        assert client.patch(f'/api/crm/leads/{ids[0]}/stage', headers=seller, json={'stage':'qualified'}).status_code == 200
        assert client.post(f'/api/crm/leads/{ids[0]}/notes', headers=seller, json={'note':'Uchrashuv rejalashtirildi'}).status_code == 201
        with factory() as session:
            assert session.get(Lead, ids[0]).stage == 'qualified'
            assert session.scalar(select(LeadEvent).where(LeadEvent.value == 'Uchrashuv rejalashtirildi')) is not None
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.parametrize('days', [7, 30, 90])
@pytest.mark.parametrize('offset_hours', [0, 5])
def test_period_boundaries_match_chart_and_lead_totals(tmp_path, days, offset_hours):
    client, factory, _, engine = _client(tmp_path)
    end = datetime(2030, 6, 1, 12, tzinfo=timezone.utc)
    start = end - timedelta(days=days)
    try:
        with factory.begin() as session:
            for created_at in (start - timedelta(microseconds=1), start, end, end + timedelta(microseconds=1)):
                session.add(Lead(unit_id='A-101', name='Boundary lead', phone='+998900000001',
                                 stage='new', company_id='qurlish', created_at=created_at))
            session.add(Lead(unit_id='B-101', name='Other company', phone='+998900000002',
                             stage='new', company_id='other-co', created_at=end))
        headers = _login(client, 'seller@test.local')
        params = {'days': days, 'as_of': end.astimezone(timezone(timedelta(hours=offset_hours))).isoformat()}
        response = client.get('/api/crm/metrics', params=params, headers=headers)
        assert response.status_code == 200
        metrics = response.json()
        leads = client.get('/api/crm/leads', params={**params, 'page': 1}, headers=headers).json()
        assert metrics['count'] == sum(metrics['stages'].values()) == leads['total'] == 2
        assert metrics['bins'] == [1, 0, 0, 0, 0, 0, 1]
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()

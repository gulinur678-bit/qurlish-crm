import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('contents,override,expected', [
    ('JWT_SECRET="file-secret-with-dollar-${UNCHANGED}"\n', None, 'file-secret-with-dollar-${UNCHANGED}'),
    ('JWT_SECRET=file-secret\n', 'process-secret', 'process-secret'),
    ('JWT_SECRET=file-secret\n', '', ''),
    ('# no secret\n', None, ''),
    (None, None, ''),
])
def test_local_env_from_another_working_directory(tmp_path, contents, override, expected):
    package = tmp_path / 'project' / 'backend'
    package.mkdir(parents=True)
    for filename in ('__init__.py', 'config.py', 'environment.py'):
        shutil.copyfile(ROOT / 'backend' / filename, package / filename)
    if contents is not None:
        (package.parent / '.env').write_text(contents)
    env = os.environ.copy()
    env.pop('JWT_SECRET', None)
    env['PYTHONPATH'] = str(package.parent)
    env['EXPECTED_SECRET'] = expected
    if override is not None:
        env['JWT_SECRET'] = override
    result = subprocess.run([sys.executable, '-c',
        'import os; from backend.config import settings; '
        'assert settings.jwt_secret == os.environ["EXPECTED_SECRET"]'],
        cwd=tmp_path, env=env, capture_output=True)
    assert result.returncode == 0, 'Isolated configuration check failed (values suppressed).'


def test_login_and_refresh_survive_backend_restart(tmp_path):
    import secrets
    import socket
    import time

    import httpx
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.auth import hash_password
    from backend.identity import Base, Company, User

    project = tmp_path / 'restart-project'
    shutil.copytree(ROOT / 'backend', project / 'backend', ignore=shutil.ignore_patterns('__pycache__'))
    database = project / 'restart.db'
    password = secrets.token_urlsafe(24)
    engine = create_engine('sqlite:///' + str(database))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Company(id='qurlish', name='Restart test'))
        session.add(User(email='restart@example.test', password_hash=hash_password(password),
                         role='admin', company_id='qurlish'))
        session.commit()
    engine.dispose()
    (project / '.env').write_text(
        'JWT_SECRET=' + secrets.token_urlsafe(48) + '\n'
        'DATABASE_URL=sqlite:///' + str(database) + '\nCOOKIE_SECURE=0\nCOMPANY_ID=qurlish\n')
    env = os.environ.copy()
    for key in ('JWT_SECRET', 'DATABASE_URL', 'COOKIE_SECURE', 'COMPANY_ID'):
        env.pop(key, None)
    env['PYTHONPATH'] = str(project)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'

    def start():
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app',
            '--host', '127.0.0.1', '--port', str(port), '--no-access-log'],
            cwd=project, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and process.poll() is None:
            try:
                if httpx.get(base + '/api/health', timeout=.5).status_code == 200:
                    return process
            except httpx.RequestError:
                pass
            time.sleep(.05)
        process.terminate()
        process.wait(timeout=5)
        pytest.fail('Isolated backend failed to start; private output suppressed.')

    def stop(process):
        process.terminate()
        process.wait(timeout=5)

    process = start()
    try:
        with httpx.Client(base_url=base) as client:
            response = client.post('/api/auth/login', json={'email':'restart@example.test', 'password':password})
            assert response.status_code == 200
            token = response.json()['access_token']
            assert client.get('/.env').status_code == 404
            stop(process)
            process = start()
            assert client.get('/api/crm/me', headers={'Authorization':'Bearer ' + token}).status_code == 200
            assert client.post('/api/auth/refresh').status_code == 200
            assert client.post('/api/auth/login', json={'email':'restart@example.test', 'password':password}).status_code == 200
            assert client.post('/api/auth/logout').status_code == 200
    finally:
        if process.poll() is None:
            stop(process)

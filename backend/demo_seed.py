"""Explicit demo-only seed, never permitted with a PostgreSQL/production database."""
import os
from main import Base,engine,SessionLocal,Unit,Staff,hash_password
if os.getenv('DEMO_DATABASE_ONLY')!='1' or not str(engine.url).startswith('sqlite'):
    raise SystemExit('Refused: DEMO_DATABASE_ONLY=1 and SQLite DATABASE_URL required')
Base.metadata.create_all(engine)
with SessionLocal.begin() as s:
    if s.query(Unit).count():raise SystemExit('Existing inventory: refusing seed')
    for building in 'ABCD':
        for floor in range(1,8):
            for n in range(1,4):
                s.add(Unit(id=f'{building}-{floor}0{n}',building=building,floor=floor,number=n,rooms=n+1,area=round(41+n*16+floor*.7,1),price=(650+n*120+floor*10)*1000000,status='sold' if (ord(building)+floor+n)%13==0 else ('reserved' if (ord(building)+floor+n)%9==0 else 'available')))
    email=os.getenv('DEMO_ADMIN_EMAIL','admin@example.test').lower()
    password=os.getenv('DEMO_ADMIN_PASSWORD','')
    if len(password)<12:raise SystemExit('Set DEMO_ADMIN_PASSWORD (minimum 12 characters)')
    s.add(Staff(email=email,password_hash=hash_password(password),role='admin'))
print('Seeded 84 demo units and 1 admin (demo SQLite database only)')

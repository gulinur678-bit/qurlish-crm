# Qurlish CRM

Qurilish kompaniyasi uchun bitta kompaniyali CRM: ommaviy landing va xonadon tanlash sahifasi, FastAPI backend, hamda React xodimlar paneli. Demo va lokal foydalanish uchun mo‘ljallangan; real mijoz ma’lumotlari bilan ishlatishdan oldin operatsion muhit xavfsizligi alohida ko‘rib chiqilishi kerak.

## Tuzilma

- `backend/identity.py` — SQLAlchemy modellari va DB sessiyasi.
- `backend/config.py` — muhit sozlamalari; secretlar kodga yozilmaydi.
- `backend/auth.py` — login, access token, refresh rotation va role tekshiruvi.
- `backend/inventory.py` — login talab qilmaydigan xonadon katalogi va murojaat yuborish.
- `backend/crm_api.py` — murojaatlar, metrikalar, bosqich va tarix API’lari.
- `backend/catalog_admin.py` — admin uchun xodimlar va xonadon statusini boshqarish.
- `backend/bootstrap.py` — birinchi administratorni faqat bir marta yaratish.
- `backend/migrations/` — Alembic sxema migratsiyalari.
- `frontend/` — React + TypeScript + Vite interfeysi.

## Lokal ishga tushirish

Mavjud `demo_data/qurlish_demo.db` v0.4 ga migratsiya qilingan. Shu demoni xavfsiz ochish uchun root’dan `.venv/bin/python scripts/run_demo.py`, boshqa terminalda `cd frontend` va `npm run dev` bajaring. Launcher faqat shu demo faylni ochadi, revision’ni tekshiradi va secretni Git’dan chiqarilgan `backups/local-demo-runtime.json` faylida 600 ruxsat bilan saqlaydi. Mavjud admin paroli o‘zgartirilmaydi. Quyidagi umumiy sozlash buyruqlari boshqa, alohida muhit yaratish uchun.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

`DATABASE_URL` ni lokal SQLite fayliga yoki PostgreSQL’ga sozlang. Har bir muhitda kamida 32 belgili tasodifiy `JWT_SECRET` bering. `COOKIE_SECURE=1` ni HTTPS ortidagi muhitda ishlating.

Mavjud v0.3 bazasi bo‘lsa, migratsiyadan oldin uning zaxira nusxasini oling. Migratsiya ma’lumotlarni o‘chirmaydi: `staff` jadvali `users` ga ko‘chadi, xonadonlar va murojaatlarga `qurlish` kompaniya ID si backfill qilinadi.

```bash
export DATABASE_URL=sqlite:///./local-dev.db
export JWT_SECRET="$(openssl rand -hex 32)"
alembic upgrade head
```

Birinchi administratorni app startup vaqtida avtomatik yaratmaymiz. Bir martalik buyruq uchun secretlarni faqat process muhitiga bering:

```bash
export BOOTSTRAP_ADMIN_EMAIL=admin@example.test
export BOOTSTRAP_ADMIN_PASSWORD='kamida-16-belgili-maxfiy-parol'
python -m backend.bootstrap
unset BOOTSTRAP_ADMIN_PASSWORD
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend uchun boshqa terminalda:

```bash
cd frontend
npm install
npm run dev
```

React sahifalarini `http://127.0.0.1:5173/` dan oching. Landing `/` va xonadon tanlash `/apartments` login talab qilmaydi. Xodimlar CRM’i `/crm` manzilida.

## Demo bazasi

Demo seed faqat `DEMO_DATABASE_ONLY=1` va SQLite bilan ishlaydi. Bu buyruq mavjud inventory aniqlasa to‘xtaydi.

```bash
export DATABASE_URL=sqlite:///./demo-only.db
export JWT_SECRET="$(openssl rand -hex 32)"
alembic upgrade head
export DEMO_DATABASE_ONLY=1
export DEMO_ADMIN_EMAIL=admin@example.test
export DEMO_ADMIN_PASSWORD='demo-uchun-uzun-maxfiy-parol'
python -m backend.demo_seed
```

## Autentifikatsiya va ruxsatlar

Login javobida qisqa muddatli access JWT qaytadi; React uni faqat tab xotirasida saqlaydi. Refresh token `HttpOnly`, `SameSite=Strict` cookie’da turadi va bazada faqat SHA-256 xeshi saqlanadi. Har refreshda token aylantiriladi; eski token qayta yuborilsa sessiya oilasi bekor qilinadi. Har CRM so‘rovida foydalanuvchi holati va sessiya oilasi bazadan tekshiriladi. Auth va CRM javoblari `Cache-Control: no-store` bilan qaytadi.

**Sessiya oilasi** — bitta login va undan keyingi refreshlar zanjiri. Masalan, sotuvchi bir tokenni ikki marta yuborsa, server shu zanjirni yopadi; boshqa qurilmadagi alohida login ishlashda davom etadi. Account deaktivatsiyasi esa xodimning barcha zanjirlarini yopadi. Qayta aktivatsiya eski tokenlarni tiklamaydi.

**Tranzaksiya qulfi** — parallel amallarni bazada navbatlash. SQLite’da `BEGIN IMMEDIATE`, PostgreSQL’da company qatori qulfi login, refresh, logout, rol/deaktivatsiya va bootstrap yozishlarini muvofiqlashtiradi. Refresh token shartli UPDATE orqali bir marta ishlatiladi. Bir token bilan ikkita parallel refresh natijasi `200` va `401`; reuse aniqlangach ikkala access ham yaroqsiz. Frontend bir tabda promise, bir origin’dagi tablar orasida Web Locks bilan refreshni navbatlaydi; BroadcastChannel logoutni boshqa tablardagi interfeysga yetkazadi. Kechikkan javob logoutni bekor qila olmaydi.

| Rol | Ko‘rish | Murojaat bosqichi/eslatma | Xodim va katalog boshqaruvi |
|---|---:|---:|---:|
| Admin | Ha | Ha | Ha |
| Seller | Ha | Ha | Yo‘q |
| Viewer | Ha | Yo‘q | Yo‘q |

Eski `admin` hisobi admin bo‘lib qoladi, `manager` Seller bo‘ladi. Tanilmagan rollar Viewer qilib deaktivatsiya qilinadi. Admin API orqali hisobni deaktivatsiya qilish barcha uning refresh sessiyalarini bekor qiladi; access token ham keyingi so‘rovda ishlamaydi.

Muhim endpointlar:

- `POST /api/auth/login` — access token va refresh cookie beradi.
- `POST /api/auth/refresh` — refresh tokenni aylantirib yangi access token beradi.
- `POST /api/auth/logout` — server sessiyasini bekor qiladi va cookie’ni o‘chiradi.
- `GET /api/crm/me`, `/api/crm/leads`, `/api/crm/metrics` — Bearer access token talab qiladi.
- `/api/admin/users` — Admin uchun xodim yaratish, ko‘rish va deaktivatsiya.
- `GET /api/public/units`, `POST /api/public/leads` — public; login talab qilmaydi.

Kompaniya hozir bitta (`COMPANY_ID=qurlish`). Server inventory, lead, event, user va idempotency so‘rovlarini shu kompaniyaga scope qiladi. Boshqa company ID dagi resurslar mavjud emasdek 404 qaytariladi. Root static server faqat public HTML/JS/CSS fayllar ro‘yxatini beradi; repository, `.env` va backend fayllari static orqali ochilmaydi.

## Tekshiruv

Backend testlari har bir test uchun alohida vaqtinchalik SQLite bazasidan foydalanadi. Migratsiya testi eski sxemani vaqtinchalik faylda ko‘tarib, xonadonlar, murojaatlar va hisoblarni tekshiradi.

```bash
.venv/bin/python -m pytest -q tests
cd frontend
npm run typecheck
npm run build
# E2E_PYTHON: loyiha interpreterining to‘liq yo‘li; Chrome o‘rnatilgan bo‘lishi kerak.
E2E_PYTHON='/absolute/path/to/project/.venv/bin/python' npm run test:e2e
```

Playwright 8000/5173 portlarida test serverlarini ko‘taradi, band portdagi serverni ishlatmaydi. Python harness yangi vaqtinchalik SQLite bazani Alembic bilan yaratib, sintetik Admin/Seller/Viewer hisoblarini qo‘shadi. Parol va JWT secret har test run uchun tasodifiy; tokenlar log, trace va screenshotlarga yozilmaydi. macOS Node CA/Keychain muammosi bo‘lsa `NODE_OPTIONS=--use-bundled-ca` bilan bajaring.

`E2E_DEMO_COPY=1` qo‘shilsa testlar migratsiyalangan demo bazaning vaqtinchalik backup nusxasida ishlaydi. Manba read-only ochiladi; murojaat yuborish va Kanban tahriri faqat nusxani o‘zgartiradi. Test hisoblari ham faqat nusxaga qo‘shiladi.

## v0.4 yakuniy review va demo migratsiyasi

2026-11-24 foydalanuvchi tasdig‘idan so‘ng yangi backup olindi: `backups/v04-final-20261124T114514Z/demo-before-v04.db` (katalog 700, fayl 600). SQLite backup API nusxasi yaxlitlik tekshiruvidan o‘tdi; uning alohida ishchi nusxasida Alembic upgrade va takroriy upgrade sinab ko‘rildi.

**Asl `demo_data/qurlish_demo.db` ga `20261124_v04` migratsiyasi muvaffaqiyatli qo‘llandi.** 84 xonadon, 2 murojaat, 2 tarix, 2 idempotency yozuvi va 1 aktiv admin saqlandi. Barcha eski maydonlar va admin password hash ichkarida tengligi tekshirildi. `integrity_check` va `foreign_key_check` o‘tdi; backup va `local-dev.db` o‘zgarmadi. Manba fayl ruxsati 600. Secret, DB/WAL/SHM va backuplar Git’dan chiqarilgan.

Ishlayotgan asl demoni tekshirish:

```bash
.venv/bin/python scripts/check_demo.py
```

Bu tekshiruv asl demoda landing, 84 xonadon va tokensiz CRM 401 holatini tasdiqladi. Mavjud administrator bilan login foydalanuvchi tomonidan qo‘lda muvaffaqiyatli tekshirildi va tasdiqlandi; parol oshkor qilinmadi yoki almashtirilmadi. Test hisoblari bilan barcha auth oqimlari nusxada tekshirildi. Ixtiyoriy avtomatik tekshiruv uchun `backups/admin-login.json` faylida `password` maydoni berilishi mumkin; script login, dashboard, Kanban ko‘rinishi, refresh va logout/401 oqimini tekshiradi, biznes yozuvlarini o‘zgartirmaydi va parolni logga chiqarmaydi. Qo‘lda login tasdig‘i mavjud hisob bilan avtomatik E2E testi bajarilganini anglatmaydi.

`scripts/verify_demo_migration.py` migratsiyadan oldingi manba bilan teng backupni sinash uchun mo‘ljallangan; original allaqachon migratsiyalangani sabab eski manifest bilan qayta ishga tushirilsa ataylab to‘xtaydi. Batafsil: [v0.4 security review](docs/v0.4-security-review.md).

## Hozirgi cheklovlar

- 3D xonadon modeli, sale approval, real-time va fayl yuklash yo‘q.
- Demo seed sintetik inventar yaratadi; haqiqiy inventar sifatida ishlatmang.
- Rate limiting, monitoring, production backup/restore mashqlari va production operatsion ko‘rik ushbu lokal v0.4 o‘zgarishining tashqarisida. Company darajasidagi qulf kichik bitta kompaniya uchun tanlangan; yuqori yuklama testi bajarilmagan.
- `references/lesson-20/` topilmadi; darsga muvofiqlik tasdiqlanmagan. PostgreSQL uchun kod yo‘li bor, ammo haqiqiy PostgreSQL integratsion testi bajarilmagan.
- Avtomatik refresh Web Locks’ni qo‘llaydigan secure context (HTTPS yoki localhost) talab qiladi; qo‘llamasa qayta login kerak. Logoutning tarmoq xatosi server revocation tasdiqlanganini anglatmaydi; interfeys bu xatoni ko‘rsatadi.
- `app.js` eski, aniq belgilangan public demo; real staff ma’lumotlari backend ruxsat tekshiruvlari orqali beriladi.

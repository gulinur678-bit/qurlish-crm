# Qurlish CRM React frontend · v0.4

React + TypeScript + Vite. Public landing va xonadon tanlash hamda xodimlar CRM’i bir xil backend API’dan foydalanadi.

## Ishga tushirish

Backend root papkadan:

```bash
source .venv/bin/activate
python scripts/run_demo.py
```

Frontend alohida terminalda:

```bash
cd frontend
npm install
npm run dev
```

http://127.0.0.1:5173 ni oching. Vite /api so‘rovlarini backend’ga uzatadi. Landing / va xonadon tanlash /apartments public; xodimlar CRM’i /crm da.

Launcher faqat migratsiyalangan lokal demo bazani ochadi va private JWT sozlamasini Git’dan chiqarilgan faylda saqlaydi. Mavjud admin hisobini yaratmaydi yoki parolini almashtirmaydi.

## Auth oqimi

- Login POST /api/auth/login access token va foydalanuvchi qaytaradi; refresh token HttpOnly cookie sifatida o‘rnatiladi.
- Access token tab xotirasida turadi va API’ga Bearer header bilan boradi; localStorage ishlatilmaydi.
- Sahifa ochilganda va access token eskirganda POST /api/auth/refresh chaqiriladi. Bir tabda parallel refresh bitta promise’ga birlashadi; tablar orasida Web Locks navbatlaydi. Logout BroadcastChannel orqali boshqa tablarni ham tozalaydi; kechikkan refresh javobi sessiyani tiklamaydi. Web Locks uchun HTTPS yoki localhost kerak; qo‘llanmasa qayta login qilinadi.
- Logoutdagi tarmoq xatosi interfeysda ko‘rsatiladi; server revocation tasdiqlanmagan bo‘lishi mumkin. Vite proxy asl Origin’ni saqlaydi.
- Viewer uchun bosqich va eslatma kiritish boshqaruvlari o‘chirilgan. Server har bir yozish amalida rolni qayta tekshiradi.

## Tekshiruv

```bash
npm run typecheck
npm run build
E2E_PYTHON='/absolute/path/to/project/.venv/bin/python' npm run test:e2e
```

Backend acceptance, parallel security va migration tests: repository root’dan `.venv/bin/python -m pytest -q tests`. Playwright o‘rnatilgan Chrome’dan foydalanadi; yangi vaqtinchalik migrated DB va sintetik hisoblar bilan 8000/5173 portlarida test serverlari ochadi. Port band bo‘lsa to‘xtaydi. Trace, video va screenshot o‘chiq. macOS Node CA/Keychain xatosida `NODE_OPTIONS=--use-bundled-ca` ishlating.

`E2E_DEMO_COPY=1` bilan shu testlar 84 xonadonli demo bazaning vaqtinchalik nusxasida ishlaydi. Murojaat yuborish va Kanban tahriri ham tekshiriladi; asl 2 murojaat saqlanadi. Ishlayotgan demo uchun root’dan `.venv/bin/python scripts/check_demo.py` bor; haqiqiy admin login testi private password fayli mavjudligini talab qiladi.

## Mavjud imkoniyatlar va chegaralar

- /apartments real /api/public/units katalogidan o‘qiydi, /api/public/leads ga idempotent murojaat yuboradi va API ishlamasa synthetic inventory ko‘rsatmaydi.
- /crm dashboard, Kanban, mijozlar ro‘yxati, tarix va ichki eslatmalarni ko‘rsatadi.
- 3D/WebGL yoki texnik chizma yo‘q; xonadon tanlash 2D ko‘rinishda.
- Sotuvni tasdiqlash workflow’i yo‘q. Rasmlar illyustrativ.
- Responsive, accessibility va brauzer screenshot tekshiruvi alohida qo‘lda bajarilishi kerak.

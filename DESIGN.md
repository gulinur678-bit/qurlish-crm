# Qurlish CRM — v0.4 dizayn qarorlari

**Holat:** single-company prototip, auth va sessiya nazoratiga ega. Public landing/xonadon tanlash va CRM alohida oqimlarda qoladi.

## Foydalanuvchi oqimlari

1. Xaridor: landing → xonadon tanlash → xonadon → murojaat. Bu oqim login talab qilmaydi; API xonadon mavjudligini tekshiradi va idempotency kaliti bilan takroriy yuborishni xavfsiz qiladi.
2. Xodim: `/crm` → login yoki mavjud refresh cookie orqali sessiyani tiklash → dashboard / Kanban / mijoz kartasi.
3. Admin: mavjud CRM oqimlaridan tashqari `/api/admin/users` orqali xodim yaratadi, rolini o‘zgartiradi yoki hisobini deaktivatsiya qiladi.

Landing, selector, dashboard, Kanban, mijozlar jadvali va drawer’ning v0.3 visual system’i, responsive o‘lchamlari va rang rollari saqlanadi. Viewer uchun tahrirlash boshqaruvlari o‘chiriladi; serverdagi RBAC asosiy xavfsizlik chegarasi bo‘lib qoladi.

## Auth va API kontrakti

- `POST /api/auth/login` body: `{email, password}`. Javob: `{access_token, token_type, expires_in, user}`; refresh token javob body’siga kirmaydi.
- Access token — 15 daqiqa amal qiladigan JWT, React module xotirasida saqlanadi va `Authorization: Bearer` orqali yuboriladi.
- Refresh token — 14 kunlik, `HttpOnly`, `SameSite=Strict` cookie (`Secure` HTTPS muhitida). React startup’da `POST /api/auth/refresh` qilib yangi access token oladi.
- Har refresh bir martalik token yozuvini `RefreshSession` jadvaliga xesh bilan saqlaydi. Refresh token replay bo‘lsa butun family revoke qilinadi; access token ishlatilishida ham family, account active holati va kompaniya ID tekshiriladi.
- Logout server tomonda family’ni bekor qiladi. Admin account deaktivatsiyasi yoki rol o‘zgarishi xodimning barcha aktiv family sessiyalarini bekor qiladi.
- Logout refresh cookie va mavjud Bearer’dagi family’larni bekor qiladi; cookie yo‘q bo‘lsa ham valid access orqali ishlaydi. Takroriy logout idempotent.
- SQLite’da security yozishlari o‘qishdan oldin `BEGIN IMMEDIATE` oladi. PostgreSQL’da bitta kompaniyaning barqaror qatori `FOR UPDATE` bilan qulflanadi. Login, refresh, logout, account tahriri, bootstrap va CRM mutatsiyalari bir tartibda bajariladi; bu role tekshiruvi bilan yozish o‘rtasidagi poygani ham cheklaydi. Company darajasidagi qulf sodda, ammo autentifikatsiya yuklamasini navbatlaydi.
- Rotation `used_at IS NULL AND revoked_at IS NULL` shartli UPDATE bilan bitta voris yaratadi. Claim, voris va audit bitta tranzaksiyada; xatoda rollback. Parallel reuse natijasi bitta 200 va bitta 401; oxirida butun family bekor.
- Browser’da bir tab uchun refresh promise, tablar orasida `navigator.locks` ishlatiladi. Login/logout ham shu qulfni oladi. Logout xabari `BroadcastChannel` orqali tarqaladi; avlod hisoblagichi logoutdan oldin boshlangan javobni tashlab yuboradi. Tokenlar storage yoki kanalga yozilmaydi. Web Locks bo‘lmasa avtomatik refresh rad etiladi.
- Origin va `Sec-Fetch-Site` tekshiruvi state-changing API so‘rovlariga tatbiq etiladi.
- Vite proxy Origin’ni qayta yozmaydi va Host’ni saqlaydi; backend haqiqiy browser originini tekshiradi. Auth/CRM/admin javoblariga `Cache-Control: no-store` qo‘yiladi.

## Rollar va ma’lumotlar chegarasi

| Amal | Admin | Seller | Viewer |
|---|---:|---:|---:|
| CRM ma’lumotlarini ko‘rish | Ha | Ha | Ha |
| Murojaat bosqichi/eslatma | Ha | Ha | Yo‘q |
| Xonadon statusi | Ha | Yo‘q | Yo‘q |
| Xodim va rollarni boshqarish | Ha | Yo‘q | Yo‘q |

Mavjud `manager` rollari `seller` ga, `admin` rollari `admin` ga xaritalanadi. Noma’lum rol `viewer` qilinib deaktivatsiya qilinadi; parol xeshlari saqlanadi.

Faqat `qurlish` kompaniyasi sozlangan. Migration mavjud company, unit, lead, event va idempotency ma’lumotlarini bitta kompaniyaga bog‘laydi. CRM va admin ID qidiruvlari `company_id` bilan filterlanadi; boshqa kompaniya resursi 404 qaytaradi. Public xonadonlar va lead intake ham faqat sozlangan kompaniyaga scope qilinadi.

## Ma’lumotlar va migratsiya

- `User` eski `staff` yozuvlarini `users` jadvaliga ko‘chiradi; email, PK va password hash saqlanadi.
- `AuditLog` login, sessiya rotatsiyasi/replay, lead mutatsiyasi, xodim o‘zgarishi va unit status o‘zgarishini yozadi. Parol va raw token auditga kiritilmaydi.
- `RefreshSession` har bir refresh token uchun hash, family, expiration, ishlatilgan/bekor qilingan vaqt va almashtirgan token ID sini saqlaydi.
- Alembic app startup’da avtomatik ishlamaydi. Sxema faqat `alembic upgrade head` bilan yangilanadi; eski ma’lumotlarni backfill qiladi.
- Birinchi admin `python -m backend.bootstrap` orqali yaratiladi; env paroli kamida 16 belgi, admin mavjud bo‘lsa bootstrap rad etadi.

## Tekshiruv va chegaralar

- Backend acceptance tests vaqtinchalik SQLite DB’da auth, RBAC, replay detection, account/session revocation va company boundary’ni tekshiradi. Mustaqil DB connectionlar hamda Event/Barrier bilan boshqarilgan testlar refresh–refresh, refresh–logout, refresh–deaktivatsiya, oxirgi admin va bootstrap poygalarini tekshiradi; timing uchun sleep ishlatilmaydi.
- Alohida migration testi oldingi sxemadan upgrade qilib mavjud xonadon, lead, event, idempotency va password hash saqlanishini tasdiqlaydi.
- Yangi backup nusxasi tekshirilgach, foydalanuvchi tasdig‘i bilan asl demo ham `20261124_v04` revision’iga ko‘tarildi. 84 xonadon, 2 murojaat va 1 aktiv admin, jumladan password hash maydonlar darajasida saqlandi. Backup va `local-dev.db` o‘zgarmadi.
- Frontend `npm run typecheck`, `npm run build` va Playwright/Chrome’da tekshiriladi. Browser oqimlari public landing/katalog, login, logout, refresh, Viewer, tablar va kechikkan refreshni qamraydi. Kontrast/visual regression va real PostgreSQL operatsion tekshiruvi bajarilmagan.
- `E2E_DEMO_COPY=1` test serveri asl demoni read-only backup API bilan vaqtinchalik faylga nusxalaydi. Test hisoblari, yangi murojaat va Kanban tahriri faqat shu nusxada yaratiladi. Asl demoda 2 murojaat qoladi. Mavjud admin loginini foydalanuvchi qo‘lda muvaffaqiyatli tekshirganini tasdiqladi; parol oshkor qilinmadi yoki almashtirilmadi. Mavjud hisob bilan avtomatik E2E bajarilmadi.
- `references/lesson-20/` yo‘q; darsdagi implementatsiya bilan solishtirish ochiq.
- 3D interaktivlik, tasdiqlangan sotuv workflow’i, rate limiting, monitoring va production rollout ushbu bosqichda yo‘q.

## v0.5 — Premium Landing & Interactive 3D (2026-11-25)

Public sahifalar uchun yangi tizim `frontend/src/premium.css` da; CRM v0.4 uslubi saqlandi. Landing `PremiumLanding.tsx`, lazy yuklanadigan katalog `Explorer.tsx`, geometrik sahna `Scene.tsx` ga ajratildi. Mahalliy CSS arxitektura tasviri tashqi pullik servis talab qilmaydi. Xonadon detailidagi interyer suratlari illyustrativligicha qoladi.

### Oqim va wireframe

Xaridor: navbar → editorial hero va **Xonadon tanlash** → majmua → bino → qavat → API ID bilan xonadon → detail → idempotent murojaat → raqamli tasdiq.

Menejer: CRM login → dashboard → Kanban → mijoz kartasi → eslatma/bosqich. Ushbu oqimning professional redesigni v0.6 uchun qoldirildi.

Desktop landing: `[navbar] [matn/CTA | arxitektura] [tavsif | izoh] [3 afzallik] [aloqa/CTA] [footer]`.
Desktop katalog: `[sarlavha] [3D toolbar / sahna / kamera boshqaruvi] [bino-qavat | 2D xonadonlar | detail]`.
Mobil: bo‘limlar bir ustun; tanlangan xonadon tafsiloti pastdan ochiladigan, yopish tugmali non-modal bottom sheet. Dialog murojaat formasida focus trap mavjud; sheet ochilganda sarlavhaga focus, yopilganda tanlangan kartaga qaytish.

### Terminlar — loyiha misolida

- **Visual hierarchy** — axborotning muhimligiga mos kattalik: landingda avval katta sarlavha, so‘ng izoh, keyin asosiy CTA ko‘rinadi.
- **Editorial typography** — jurnalga xos shrift kompozitsiyasi: Georgia serif sarlavhalari bilan sodda sans-serif matn birlashadi.
- **Grid** — ustunlar tizimi: desktop hero ikki ustun, afzalliklar uch ustun; mobil bir ustun.
- **Whitespace** — bo‘sh joy: bo‘limlar orasidagi 72/112px oraliq matn va tasvirni ajratadi.
- **Design token** — qayta ishlatiladigan qiymat: `--surface`, `--text`, `--accent`, `--line`, status ranglari, spacing, radius, shadow va motion o‘zgaruvchilari.
- **CTA** — keyingi amal tugmasi: “Xonadon tanlash”.
- **Cutaway** — tomi olib tashlangan kesim: xonalar poliga bosilganda ajratib ko‘rsatiladi. Xonalar soni API’dan, shakli va mebeli taxminiy; texnik reja emas.
- **Progressive enhancement** — 2D katalogga qurilma qo‘llasa 3D imkoniyatini qo‘shish. 3D xatosida murojaat oqimi ishlashda davom etadi.
- **Reduced motion** — operatsion tizim sozlamasiga ko‘ra CSS animatsiya va silliq kamera o‘tishlarini o‘chirish.

Termin referensi: https://ux-ui-atlas-komiljon.komildjonxyz.chatgpt.site/ — Chrome orqali o‘qildi; maket ko‘chirilmagan.

### 3D kontrakti

React 19 bilan Fiber 9 va Drei 10 ishlatiladi. Rasmiy moslik: https://r3f.docs.pmnd.rs/getting-started/introduction . Binolar API building qiymatidan tuziladi; demo nusxasida 4 bino, har biri 7 qavat va jami 84 xonadon. Har bir mesh mavjud `Unit.id` bilan tanlanadi. Maydon, xona soni, narx va status API’dan olinadi; narx geometriyadan chiqarilmaydi. Bino/qavat izolyatsiyasi boshqa binolarning tanlovni to‘sishini oldini oladi. Majmuada tanlash, orbit, zoom, reset va xonadonlar orasida oldingi/keyingi tugmalari mavjud. Shu amallar HTML tugmalar bilan klaviaturada bajariladi; canvas alohida screen-reader interfeysi emas.

`frameloop="demand"`, DPR 1–1.5; faqat interaksiya/harakatda render. Model tashqi GLB yoki HDR yuklamaydi. 3D chunk faqat foydalanuvchi ochganda yuklanadi. WebGL2 yo‘qligi, context loss yoki lazy modul xatosi 2D katalogga qaytadi.

Public muted matn kontrasti: surface’da 5.84:1, afzallik fonida 5.33:1; uch status juftligi 6.31:1 yoki yuqori; to‘q contact fonida matn 9.53:1. Hisob sRGB nisbiy yorqinlik formulasiga asoslangan. CRM kontrast auditi bu bosqichga kirmaydi.

v0.5 tasdiqlangan test/performance dalillari: [UX review](docs/ux-review.md), [o‘lchovlar](docs/v05-measurements.json), [accessibility](docs/v05-accessibility.json). Cutaway xonalarini polga bosib yoki raqamli HTML tugmalar orqali klaviaturada tanlash mumkin. Kamera effekti faqat ko‘rinish/reset o‘zgarishiga bog‘langan; forma matnini tahrirlash kamerani qayta joylashtirmaydi.

# Qurlish CRM v0.6 review — 2026-11-26

Professional CRM ish maydoni `/crm` da. Public landing va xonadon/3D oqimlari bilan bir ilovada, alohida lazy modulda ishlaydi.

## Natija

| Oqim | Amal va ma’lumot manbasi |
|---|---|
| Dashboard | 7/30/90 kunlik jami/yangi murojaatlar, 7 vaqt oralig‘i grafigi, joriy bosqichlar va eng yangi 5 murojaat; SQL hisoblari |
| Kanban | 4 bosqich, drag/drop yoki klaviatura/touch select; muvaffaqiyatsiz yozuv oldingi holatga qaytadi |
| Mijozlar | Ism/telefon/xonadon qidiruvi, bosqich, saralash, 25 talik sahifalar |
| Mijoz kartasi | Xonadon, telefon havolasi, faoliyat tarixi, ichki eslatma; qayta ochilganda saqlangan tarix |
| Inventar | Bino/qavat/xonalar/status filtrlari, 25 talik sahifalar; Admin bo‘sh/bron holatini tahrirlaydi |
| Xodimlar | Admin yaratish, email qidiruvi, rol/aktivlik tahriri; sessiyalar bekor qilinadi, oxirgi faol admin himoyalangan |
| Audit | Admin uchun sahifalangan vaqt, amal, xodim va resurs; raw details/session identifikatorlari berilmaydi |

Admin barcha sahifalarni ko‘radi. Seller mijoz bosqichi/eslatmasini tahrirlaydi va inventarni ko‘radi. Viewer faqat ko‘radi. UI boshqaruvlariga qo‘shimcha ravishda server RBAC va kompaniya chegarasini tekshiradi.

## Hisoblar va API kontrakti

- Dashboard murojaatlar va eng yangi yozuvlar uchun umumiy `as_of` ishlatadi; ikkita so‘rov tranzaksion snapshot emas.
- Murojaat davri boshidan oxirigacha inklyuziv. `as_of` timezone offsetlari UTC ga keltiriladi. Oxirgi chart bucket aniq cutoff bilan tugaydi; 90 kunni 7 ga bo‘lishdagi mikrosekund yaxlitlash yozuvni yo‘qotmaydi.
- Bo‘sh/bron/sotilgan xonadonlar joriy inventar; tanlangan davrdagi sotuv yoki tushum hisoblari emas.
- Kanban sahifasi 100 yozuv; ustun sonlari shu sahifani bildiradi. Mijozlar, inventar, xodimlar va audit interfeyslari sahifalangan.
- Eski `/api/crm/leads` va `/api/admin/users` chaqiruvlari `page` berilmasa avvalgi to‘liq ro‘yxat xatti-harakatini saqlaydi. Yangi UI har doim `page` beradi. Barcha eski mijozlar uchun majburiy limit bu relizga kirmaydi.
- Sold holatini tahrirlash va sotuvni tasdiqlash serverda rad etiladi. Ichki eslatma mijozga yuborilmaydi; telefon havolasi qurilma telefon ilovasini ochadi.

## Tekshiruv dalillari

- Backend: **36 passed**. Auth, refresh rotation, parallel xavfsizlik amallari, migratsiya, `.env`, RBAC, company isolation, pagination va saqlash oqimlari.
- Yangi davr regressiyasi: 7/30/90 kun, UTC va UTC+05:00; boshlanish/oxirgi mikrosekundlar va boshqa kompaniya yozuvi. Fixdan oldin 4 holat yiqildi; fixdan keyin barcha 6 kombinatsiya o‘tdi.
- Ruff: `backend`, `tests`, `scripts` uchun **All checks passed**.
- Frontend production build TypeScript tekshiruvi bilan o‘tdi.
- Playwright/Chrome: **18 passed**. Public oqimlar, 3D fallback/idempotency, login/logout/refresh/tab sinxronlashuvi, Viewer, Kanban rollback, ichki eslatma, inventar va xodim/audit oqimlari, dashboard loading/error/empty holatlari.
- Backend va browser yozish sinovlari vaqtinchalik SQLite bazalar hamda sintetik hisoblarda bajarildi.
- `git diff --check` o‘tdi.

## Visual va klaviatura review

`screenshots/v06/before/` avvalgi ko‘rinishni saqlaydi. `screenshots/v06/after/` dashboard, Kanban, mijozlar, inventar, xodimlar, audit va mijoz kartasini 390/768/1440px da ko‘rsatadi. Screenshotlar sintetik fixture bilan olingan; ularning raqamlari biznes natijalari emas.

`frontend/scripts/capture-workspace-v06.mjs` 18 sahifa/viewport kombinatsiyasida document overflow, page error va tekshirilgan matn kontrastini qayd qiladi: **overflow false, page errors 0, 4.5:1 dan past juftliklar 0**. Xom natija: [v06-browser-review.json](v06-browser-review.json). Mijoz kartasi Escape bilan yopilgach focus `Batafsil` tugmasiga qaytishi uch viewportda tekshirildi. Desktop dashboard va mobil mijoz kartasi tasvirlari ham ko‘zdan kechirildi.

Yopiq mobil sidebar oldin faqat transform bilan ekrandan chiqarilgan edi. Endi `visibility:hidden` qo‘llanadi: 390px da Tab yashirin tugmalarga tushmasligi, menyu ochilishi, navigatsiyadan keyin yopilishi va 1440px da qayta ko‘rinishi Chrome’da tekshirildi.

Kontrast scripti opaque CSS fonidagi ko‘rinadigan matnlar uchun oddiy tekshiruv; barcha SVG, hover/focus holatlari, screen reader yoki to‘liq WCAG auditi emas. Jadval va Kanban konteynerlari ichki gorizontal scroll ishlatadi.

## Qolgan chegaralar

- Production builddagi katta lazy 3D chunk haqida Vite ogohlantirishi saqlanadi. CRM grafigi ham alohida chunkda; umumiy JS landingga birvarakay yuklanmaydi.
- Starlette/httpx test adapterining mavjud deprecation ogohlantirishi bor.
- Haqiqiy PostgreSQL, mobil qurilma, Safari/Firefox, katta ma’lumotlar hajmi va production yuklamasi bu review’da tekshirilmagan.
- Sotuv approval, to‘lovlar, daromad hisoboti, real-time yangilanish, fayl biriktirish, VoIP va mijozga xabar yuborish mavjud emas.
- Yangi sxema migratsiyasi talab qilinmaydi. Deployment yoki production tayyorligi ushbu lokal review natijasi emas.

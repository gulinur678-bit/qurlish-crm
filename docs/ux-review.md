# Qurlish CRM v0.5 UX review — 2026-11-25

Audit mavjud kod va 390/768/1440px Chrome before screenshotlariga asoslanadi; foydalanuvchilar bilan usability study o‘tkazilmadi.

## Journeylar

Xaridor: landingdagi taklif → xonadon tanlash → majmua/bino/qavat → mavjud variant → narx, status va konsept kesim → murojaat → tasdiq raqami.
Menejer: login → davr bo‘yicha dashboard → Kanban → mijoz tarixi/eslatma → bosqichni yangilash. CRM dizayni v0.6 ga qoldirilgan.

## Beshta muammo va tuzatish

| Muammo | Before dalili | v0.5 yechimi |
|---|---|---|
| Fazoviy tanlov yo‘q | Katalog faqat 2D kartalar va konsept plan ko‘rsatgan | API IDlari bilan 3D bino/qavat/xonadon tanlash, izolyatsiya va cutaway |
| Qavatlar statik | `Array.from({length:7})` inventardan qat’i nazar tugmalar yaratgan | 2D qavat tugmalari API’dagi tanlangan bino qavatlaridan olinadi |
| Mobil detail uzoqda | Tanlangan kartadan keyingi detail oddiy oqimda pastda qolgan | Yopiladigan bottom sheet, detail sarlavhasiga focus |
| Ochiq rangli mayda matnlar | Public muted/label/status ranglari alohida yozilgan | Markaziy tokenlar va to‘qroq public matn/status palitrasi |
| Texnik matn vazifani chalg‘itgan | “3D keyingi versiyada”, “API ma’lumotlari” kabi ko‘rsatmalar | Xaridorga tanlash ko‘rsatmasi; konsept belgisi va zarur xato holati saqlangan |

## Wireframe

Landing: navbar → split hero (taklif, izoh, CTA / mahalliy arxitektura tasviri) → majmua tavsifi → uch afzallik → aloqa CTA → footer.
Katalog: breadcrumb → sarlavha → ixtiyoriy lazy 3D → bino/qavat boshqaruvi + kartalar + detail. Mobil: bir ustun va pastki detail panel.

## Dalillar

- Before: `screenshots/v05/before/`; after: `screenshots/v05/after/`. Landing, katalog, dashboard 390/768/1440; Kanban va mijoz kartasi 1440. CRM screenshotlari sintetik fixture bilan, real mijoz ma’lumoti bilan emas.
- Landing/katalog uchun barcha uch viewportda gorizontal overflow yo‘q.
- Status faqat rang bilan emas, matn va ✓ / ◷ / × belgisi bilan ajratiladi.
- 3D konsept, planirovka tasdiqlangan texnik chizma emas; interyer surati illyustrativ.
- Backend kod, autentifikatsiya va migratsiya o‘zgartirilmadi. Test serveri demo bazaning vaqtinchalik SQLite nusxasida ishlaydi.

Test va performance yakuni quyida qayd qilinadi.

## Yakuniy tekshiruvlar

- Backend: **22 passed**, vaqtinchalik SQLite bazalar; bitta Starlette/httpx deprecation ogohlantirishi.
- Frontend: `npm run typecheck` va `npm run build` o‘tdi.
- Playwright: **14/14 o‘tdi**, 84 xonadonli asl demo bazaning vaqtinchalik backup nusxasida. 9 ta auth/CRM regressiyasi va 5 ta yangi katalog testi: WebGL yo‘qligi, API xatosi, sold/reserved bloklash, idempotency key saqlangan retry va double click, lazy 3D hamda idle render.
- Alohida accessibility script: 390/768/1440px da karta → detail → forma → Escape focus oqimi o‘tdi, reduced-motion transition `0s`. Public landing va katalogning tekshirilgan matnlarida 4.5:1 dan past juftlik **0**. Bu oddiy opaque CSS background auditidir; screen-reader sertifikatsiyasi yoki rasm ustidagi barcha holatlar auditi emas. Xom dalil: `v05-accessibility.json`.
- Before/after landing va katalogda uch viewportning hammasida overflow yo‘q. Yakuniy 3D screenshotlar: `after/complex-{390,768,1440}.jpg` va `after/cutaway-{390,768,1440}.jpg`.

### Performance

Lokal Vite development server, headless Chrome, **SwiftShader software WebGL**, network throttling yo‘q. Viewportlar real mobil hardware emas; bitta o‘lchov va kompyuterdagi yuklamaga bog‘liq.

| Viewport | Katalog ko‘rinishi | 3D ochilishidan birinchi kadrgacha | Kamera harakatida FPS | Tinch holatda 1 soniyadagi kadr |
|---|---:|---:|---:|---:|
| 390 | 724 ms | 2145 ms | 30.0 | 0 |
| 768 | 1946 ms | 558 ms | 30.0 | 0 |
| 1440 | 742 ms | 877 ms | 30.1 | 0 |

Xom natija: `v05-measurements.json`. Avvalgi run 30–60 FPS berdi; bu raqamlar telefon unumdorligi va production LCP kafolati emas. Barcha uch 3D o‘lchovda page error 0, overflow false.

Production build: asosiy JS 275.15 KB (gzip 83.77 KB); lazy 3D JS 987.33 KB (gzip 261.61 KB). Vite 500 KB chunk ogohlantirishi mavjud. 3D landingning dastlabki yuklanishiga kirmaydi. Real telefon, Safari/Firefox va sekin tarmoq performance sinovlari ochiq.

### Chegaralar

- Geometriya, xona o‘lchamlari, mebel va arxitektura konsept; haqiqiy texnik chizma yoki tasdiqlangan interyer emas.
- Xonadonlar va tijoriy atributlar API’dan; screenshotlar demo nusxa va sintetik CRM fixture bilan.
- CRM professional redesigni v0.6; ushbu UX auditida production deployment, merge va ZIP bajarilmadi.
- Mavjud auth, RBAC, company isolation, refresh rotation va migratsiya kodlariga o‘zgartirish kiritilmadi.

Yakuniy kamera effecti va klaviatura orqali xona tanlash o‘zgarishidan keyin tegishli 3D testi qayta bajarildi: **1/1 passed (12.9s)**. Typecheck va build yakuniy frontend kodida muvaffaqiyatli. `git diff --check` o‘tdi.

## Commit oldidan qayta tekshiruv — 2026-11-25

Foydalanuvchi v0.5 interfeysini qo‘lda ko‘rib chiqdi va dizaynni ma’qulladi. Backend regression: **22 passed (5.94s)**. Yakuniy Playwright: **14 passed (29.7s)**, demo bazaning vaqtinchalik nusxasida. Ishlayotgan lokal demo serverlarini to‘xtatmaslik uchun tekshiruv 18000/15173 portlarida bajarildi; faqat test konfiguratsiyalari `/tmp` da saqlandi. Legacy staff E2E manzili `E2E_API_URL` orqali sozlanadi, default 8000 saqlanadi.

Typecheck, production build va diff whitespace tekshiruvi o‘tdi. Oldindan qayd etilgan Starlette/httpx deprecation va Vite katta lazy chunk ogohlantirishlari saqlanadi. `demo_data/qurlish_demo.db` va `local-dev.db` ning tekshiruvdan oldingi/keyingi SHA-256 xeshlari teng. CRM komponenti, auth API va migratsiya kodi o‘zgarmagan. Runtime secret qiymatlari va keng tarqalgan credential belgilarining Git fayllaridagi tekshiruvida moslik topilmadi; private fayllar, bazalar, backuplar va lokal konfiguratsiyalar commit tarkibidan chiqarilgan.

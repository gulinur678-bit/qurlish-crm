# JWT_SECRET konfiguratsiyasi — 2026-11-25

Muammo tasdiqlandi: backend faqat process environment’ni o‘qigan, root `.env` mavjud bo‘lmagan. `run_demo.py` private runtime kalitini processga qo‘shgan, lekin oddiy Uvicorn starti bu launcher’ni ishlatmaydi.

Tuzatish: `backend/environment.py` python-dotenv orqali loyiha root’idagi `.env` ni yuklaydi. Process qiymatlari ustuvor; interpolation o‘chiq. `backend/config.py` sozlamalarni yaratishdan oldin loader’ni chaqiradi. Demo launcher ham shu manbani ishlatadi; mavjud private runtime fallback saqlangan. Auth protokoli, parol xeshlari va migratsiyalar o‘zgartirilmagan.

Lokal `.env`: 0600 ruxsat, Git tomonidan ignore qilinadi, avvalgi runtime secret saqlangan. DATABASE_URL mavjud demo faylining absolut manziliga yo‘naltirilgan. Secret qiymati hujjat, log yoki test natijasiga chiqarilmagan.

Tekshiruvlar:

- `pytest -q tests`: **28 passed (10.71s)**, bitta mavjud Starlette/httpx deprecation ogohlantirishi.
- 5 konfiguratsiya testi: boshqa working directory’dan yuklash, process override, ataylab bo‘sh override, secret yo‘q fayl, `.env` yo‘qligi. Dollar belgilarining literal saqlanishi tekshirildi.
- Yangi restart integration testi: vaqtinchalik SQLite va sintetik admin bilan haqiqiy Uvicorn processi start → login 200 → stop → start → oldingi access token 200 → refresh 200 → qayta login 200 → logout 200. `.env` HTTP orqali 404.
- Haqiqiy lokal konfiguratsiyada JWT kaliti avvalgi runtime kalitiga tengligi, uzunligi va mavjud demo DB manzili ichkarida tekshirildi; qiymatlar chiqarilmadi.
- Oddiy lokal Uvicorn processi to‘xtatilib qayta ochildi; restartdan keyingi `/api/health`: 200, status ok.
- Avtomatik sinovlardan keyin `demo_data/qurlish_demo.db` va `local-dev.db` SHA-256 xeshlari boshlang‘ich qiymatlarga teng. Admin paroli almashtirilmagan.
- Git fayllarida mavjud runtime secret qiymatiga moslik: **0**. `.env` tracked emas. Commit/push bajarilmadi.

Mavjud administrator paroli agentda yo‘q; yuqoridagi avtomatik login sinovi sintetik hisobda bajarilgan. Mavjud hisob bilan qo‘lda login natijasi foydalanuvchidan alohida so‘ralgan.

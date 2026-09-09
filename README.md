# AniNovaXBot

To'liq ishlaydigan Telegram anime bot: qidiruv (kod/nom/janr/rasm), tanga tizimi, kunlik bonus,
referral, VIP obuna (tanga yoki Payme/Click/Uzum orqali), majburiy kanal obunasi, yangi anime uchun
kanalga avtomatik post, reklama/broadcast va to'liq kuchli admin panel.

Bu **faqat Telegram bot** — hech qanday veb-sayt frontend yo'q.

## 1. Talablar

- Python 3.11+
- PostgreSQL 14+
- Docker (ixtiyoriy, lekin tavsiya etiladi)

## 2. Loyihani GitHub'ga joylash

```bash
git init
git add .
git commit -m "AniNovaXBot: initial commit"
git branch -M main
git remote add origin https://github.com/<username>/AniNovaXBot.git
git push -u origin main
```

## 3. BotFather'dan BOT_TOKEN olish

1. Telegramda @BotFather ga o'ting.
2. `/newbot` yuboring, botga nom va username bering (masalan `AniNovaXBot`).
3. Sizga beriladigan tokenni saqlab qo'ying — bu `BOT_TOKEN`.
4. `/setprivacy` orqali "Disable" qiling — bot barcha xabarlarni ko'rishi kerak.

## 4. PostgreSQL ulash

Lokal test uchun eng oson yo'l — Docker:

```bash
docker compose up -d db
```

Yoki tayyor bulutli baza (Render Postgres, Neon, Supabase va h.k.) dan `DATABASE_URL` oling.
Format: `postgresql+asyncpg://user:password@host:5432/dbname`

## 5. ENV sozlash

`.env.example` faylini nusxalab `.env` qiling va qiymatlarni to'ldiring:

```bash
cp .env.example .env
```

Minimal ishga tushirish uchun kerak: `BOT_TOKEN`, `BOT_USERNAME`, `ADMIN_IDS`, `DATABASE_URL`.
Qolgan hammasi (to'lov provayderlari) bo'sh qoldirilsa, bot **SANDBOX/TEST rejimida** ishlaydi —
ya'ni to'lovlar "(TEST) To'lovni tasdiqlash" tugmasi bilan simulyatsiya qilinadi.

`ADMIN_IDS` — vergul bilan ajratilgan Telegram ID'lar ro'yxati (o'z ID'ingizni bilish uchun
@userinfobot dan foydalaning).

## 6. Migratsiyalarni ishga tushirish

```bash
pip install -r requirements.txt --break-system-packages
alembic upgrade head
```

(Bot birinchi marta ishga tushganda ham jadvallarni avtomatik yaratadi, lekin production uchun
Alembic orqali boshqarish tavsiya etiladi — kelajakdagi o'zgarishlar uchun
`alembic revision --autogenerate -m "..."` dan foydalaning.)

## 7. Lokal ishga tushirish (polling rejimi)

`.env` faylida `USE_WEBHOOK=false` qoldiring va:

```bash
python -m app.main
```

Bot Telegramda darhol javob bera boshlaydi. To'lov gateway webhooklari
`http://localhost:10001/pay/payme` (va click/uzum) manzillarida ham ishlaydi — buni tashqi
dunyoga chiqarish uchun ngrok yoki shunga o'xshash vositadan foydalaning.

## 8. Render'ga deploy qilish

1. GitHub repo'ni Render'ga ulang, `render.yaml` avtomatik topiladi (Blueprint deploy).
2. Render konsolida quyidagi environment variable'larni to'ldiring: `BOT_TOKEN`, `BOT_USERNAME`,
   `ADMIN_IDS`, `WEBHOOK_URL` (masalan `https://aninovax-bot.onrender.com`), va agar kerak bo'lsa
   to'lov provayder credentiallarini.
3. `DATABASE_URL` Render Postgres orqali avtomatik ulanadi (`render.yaml` ichida sozlangan).
4. Deploy tugagach `USE_WEBHOOK=true` bo'lgani uchun bot avtomatik webhook o'rnatadi.

## 9. Webhook sozlash (qo'lda, agar kerak bo'lsa)

Bot ishga tushganda `bot.set_webhook()` avtomatik chaqiriladi. Qo'lda tekshirish uchun:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

## 10. Admin ID qo'shish

`.env` dagi `ADMIN_IDS` ga Telegram ID'ingizni qo'shing (vergul bilan bir nechtasini kiritish
mumkin), so'ng botga `/admin` yuboring — to'liq admin panel ochiladi.

## 11. To'lov provayderlarini sozlash

### Payme
1. Payme Business orqali merchant ID va secret key oling.
2. `PAYME_MERCHANT_ID`, `PAYME_SECRET_KEY` ni to'ldiring, test uchun `PAYME_TEST_MODE=true`.
3. Payme kabinetida webhook URL sifatida: `https://<domain>/pay/payme` ni ko'rsating.

### Click
1. Click Merchant Cabinet orqali `service_id`, `merchant_id`, `secret_key`, `merchant_user_id` oling.
2. Webhook (Prepare/Complete) URL: `https://<domain>/pay/click`

### Uzum Bank (FastPay)
1. Uzum Bank Developer portali orqali merchant credentiallarini oling.
2. Webhook URL: `https://<domain>/pay/uzum`

Hech biri sozlanmagan bo'lsa, bot avtomatik **SANDBOX rejimda** ishlaydi (haqiqiy pul harakati
bo'lmaydi, faqat tasdiqlash tugmasi orqali tanga/VIP beriladi) — shu tarzda to'liq oqimni oldindan
sinab ko'rish mumkin.

## 12. Majburiy kanal obunasi

`/admin` → `📢 Kanallar` → `➕ Majburiy kanal qo'shish` → kanal `@username`sini yuboring.
**Bot kanalda admin bo'lishi shart**, aks holda obunani tekshira olmaydi.

Yangi anime qo'shilganda avtomatik e'lon qilinadigan kanalni sozlash uchun:
`/admin` → `📢 Kanallar` → `📢 E'lon kanalini sozlash`.

## 13. Birinchi anime qo'shish

`/admin` → `📤 Anime yuklash` → savollarga ketma-ket javob bering (nom, poster, banner, tavsif,
yil, janrlar, reyting, sifat, kod) → keyin videolarni ketma-ket yuboring (avtomatik 1-qism,
2-qism... deb raqamlanadi) → `✅ Tugatish`.

---

## Arxitektura

```
app/
├── bot/            # foydalanuvchi handlerlari, keyboardlar, FSM holatlar
├── admin/          # admin panel handlerlari va keyboardlar
├── database/       # SQLAlchemy modellar, sozlamalar repository
├── services/        # biznes-mantiq: coin, vip, referral, bonus, anime, stats, channel, payments
├── middlewares/     # DB session, ban tekshiruvi, flood himoyasi, majburiy obuna
├── config.py         # pydantic-settings orqali ENV
└── main.py            # webhook/polling ishga tushirish nuqtasi
migrations/           # Alembic migratsiyalari
```

## Xavfsizlik

- SQL injection: barcha so'rovlar SQLAlchemy ORM orqali (parametrlashtirilgan).
- Admin authentication: faqat `ADMIN_IDS` da ko'rsatilgan Telegram ID'lar.
- To'lov webhooklari: Payme/Uzum — Basic auth + secret key; Click — MD5 sign tekshiruvi.
- Referral fraud: bitta user faqat bitta marta referral bo'la oladi, o'zini o'zi taklif qila olmaydi.
- Flood himoyasi: har bir user uchun minimal so'rov intervali (`ThrottlingMiddleware`).
- Barcha sirlar `.env` orqali — kodga qattiq yozilmagan.

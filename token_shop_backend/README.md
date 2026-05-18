# TeleShop Backend (FastAPI + PostgreSQL) — integrate TokenPay notify_url

## 1) Setup DB (PostgreSQL)
Create database `tele_shop` and set `DATABASE_URL` in `.env`.

Example:
`postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/tele_shop`

## 2) Configure .env
Copy `.env.example` -> `.env` and set:
- TOKENPAY_API_BASE (TokenPay service, default http://127.0.0.1:5001)
- TOKENPAY_API_TOKEN
- PUBLIC_BASE_URL (URL TokenPay can call back)

## 3) Run on Windows
Double click / run:
`powershell -ExecutionPolicy Bypass -File run.ps1`

## 4) Endpoints (bot is already compatible)
- GET  /public/products
- GET  /public/products/{id}
- POST /orders/quote
- POST /orders/checkout
- GET  /orders/history?telegram_id=...
- POST /topups/create
- GET  /topups/{topup_id}
- GET  /topups/history?telegram_id=...
- POST /pay/tokenpay/notify_url  (TokenPay calls this)
- GET  /users/me?telegram_id=...
- GET  /health

## 5) Admin endpoints (for future webadmin)
Use header: `X-Admin-Key: <ADMIN_API_KEY>`
- POST /admin/products
- POST /admin/coupons
- GET  /admin/users/{telegram_id}/balance


## 6) Manual approve topup (admin)
Header: `X-Admin-Key: <ADMIN_API_KEY>`
- POST /admin/topups/approve  body: { out_order_id | topup_id, amount?, note? }

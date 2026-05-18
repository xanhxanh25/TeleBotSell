# Docker Deployment Guide

This guide deploys:
- `postgres`
- `token_shop_backend`
- `adminweb`
- `apitele`
- `tokenpay`

All services run with Docker Compose, no `.venv`, `nohup`, `setsid`, PID files, or manual restart loops.

## 1) Prepare environment

```bash
cp .env.example .env
```

Update required values in `.env`:
- `BOT_TOKEN`
- `TOKENPAY_API_TOKEN`
- `ADMIN_API_KEY`
- `BOT_API_KEY`
- `BACKEND_BOT_API_KEY`
- `ADMIN_SECRET_KEY`
- `ADMIN_PASSWORD_HASH`
- `PUBLIC_BASE_URL`

TokenPay config file:
- `TokenPay/src/TokenPay/appsettings.json`
- Ensure `ApiToken` matches `.env` value `TOKENPAY_API_TOKEN`.
- SQLite path should stay persistent (recommended: `Data Source=/data/TokenPay.db;`).

## 2) Build and start

```bash
docker compose up -d --build
```

For production profile with no host port exposure:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 3) Stop

```bash
docker compose down
```

## 4) Logs

```bash
docker compose logs -f postgres
docker compose logs -f token_shop_backend
docker compose logs -f adminweb
docker compose logs -f apitele
docker compose logs -f tokenpay
```

## 5) Health checks

```bash
docker compose ps
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:5001/
```

## 6) Database audit and migration strategy

Current backend uses:
- SQLAlchemy models/session in `token_shop_backend/app/database.py`
- Runtime `Base.metadata.create_all()` in `token_shop_backend/app/main.py`
- Manual idempotent migration scripts:
  - `token_shop_backend/migrations/add_sort_order_to_products.py`
  - `token_shop_backend/migrations/add_coupon_product_user_columns.py`
  - `token_shop_backend/migrations/add_telegram_user_column.py`

There is no Alembic configured currently. For safety, this deployment keeps existing migration style and runs the three idempotent scripts after restore.

## 7) Backup old Postgres and restore into Docker Postgres

### 7.1 Backup old/external Postgres

```bash
OLD_DATABASE_URL="postgresql://postgres:postgres@OLD_HOST:5432/tele_shop" \
bash scripts/db_backup_old_postgres.sh
```

Output dump file is created under `backups/`.

### 7.2 Restore into Docker Postgres

```bash
DUMP_FILE=./backups/tele_shop_old_YYYYMMDD_HHMMSS.dump \
bash scripts/db_restore_to_docker_postgres.sh
```

### 7.3 Run backend migrations

```bash
bash scripts/db_run_backend_migrations.sh
```

## 8) If old source is plain SQL backup

If your old backup is `.sql` (plain text) instead of `.dump`:

```bash
docker compose up -d postgres
cat /path/to/old_backup.sql | docker compose exec -T postgres psql -U postgres -d tele_shop
```

Then run:

```bash
bash scripts/db_run_backend_migrations.sh
```

## 9) Rollback basics

### Rollback application only

```bash
docker compose down
docker compose up -d --build
```

### Rollback database from previous dump

```bash
DUMP_FILE=./backups/PREVIOUS.dump bash scripts/db_restore_to_docker_postgres.sh
bash scripts/db_run_backend_migrations.sh
```

## 10) Verify runtime wiring (must pass)

- `token_shop_backend` can connect DB at `postgres:5432`
- `apitele` calls:
  - `http://token_shop_backend:8000`
  - `http://adminweb:8001`
  - `http://tokenpay:5001`
- `token_shop_backend` calls `http://tokenpay:5001`
- `adminweb` healthy and login page accessible
- Telegram bot receives commands and can read products/orders

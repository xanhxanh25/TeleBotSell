-- Migration: create seller_api_keys table
-- Seller = User Telegram duoc admin cap API key
-- Chi 1 table, khong co SellerProduct/SellerOrder/SellerApiLog rieng

-- Drop old seller tables if they exist (no longer needed)
DROP TABLE IF EXISTS seller_api_logs CASCADE;
DROP TABLE IF EXISTS seller_orders CASCADE;
DROP TABLE IF EXISTS seller_products CASCADE;
DROP TABLE IF EXISTS sellers CASCADE;

-- Create new simplified table
CREATE TABLE IF NOT EXISTS seller_api_keys (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    api_key VARCHAR(64) NOT NULL,
    api_secret VARCHAR(128) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    note VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,

    CONSTRAINT uq_seller_api_keys_api_key UNIQUE (api_key)
);

CREATE INDEX IF NOT EXISTS ix_seller_api_keys_user_id ON seller_api_keys(user_id);
CREATE INDEX IF NOT EXISTS ix_seller_api_keys_api_key ON seller_api_keys(api_key);

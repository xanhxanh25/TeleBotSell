-- Migration: Add usage limits for coupons
-- Adds:
--   - max_uses_total: total number of uses across all users
--   - max_uses_per_user: max number of uses per user
--   - max_qty_per_order: max qty allowed in a single order when using coupon

ALTER TABLE coupons
ADD COLUMN IF NOT EXISTS max_uses_total BIGINT NULL;

ALTER TABLE coupons
ADD COLUMN IF NOT EXISTS max_uses_per_user BIGINT NULL;

ALTER TABLE coupons
ADD COLUMN IF NOT EXISTS max_qty_per_order BIGINT NULL;

-- Optional: sanity checks (run manually if desired)
-- SELECT code, max_uses_total, max_uses_per_user, max_qty_per_order FROM coupons ORDER BY id DESC;


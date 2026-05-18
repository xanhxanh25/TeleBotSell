-- Coupon redemptions: authoritative usage ledger (replaces counting orders.coupon_code for limits).
-- UNIQUE(coupon_id, user_id): one successful redemption per user per coupon (DB-enforced).

CREATE TABLE IF NOT EXISTS coupon_redemptions (
    id BIGSERIAL PRIMARY KEY,
    coupon_id BIGINT NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id VARCHAR(36) NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_coupon_redemptions_coupon_user UNIQUE (coupon_id, user_id),
    CONSTRAINT uq_coupon_redemptions_order UNIQUE (order_id)
);

CREATE INDEX IF NOT EXISTS ix_coupon_redemptions_coupon_id ON coupon_redemptions (coupon_id);

-- Backfill from historical PAID orders (best-effort; skip duplicates / bad codes)
INSERT INTO coupon_redemptions (coupon_id, user_id, order_id)
SELECT c.id, o.user_id, o.id
FROM orders o
INNER JOIN coupons c ON c.code = upper(trim(both from o.coupon_code))
WHERE o.coupon_code IS NOT NULL
  AND trim(both from o.coupon_code) <> ''
  AND o.status IN ('PAID', 'CONFIRMED')
ON CONFLICT (coupon_id, user_id) DO NOTHING;

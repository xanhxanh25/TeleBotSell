-- =============================================================================
-- COUPON SYSTEM V2 — production ledger + atomic global cap + per-user > 1
-- =============================================================================
-- BUSINESS (đồng bộ code Python):
--   - max_uses_per_user NULL  => không giới hạn số lần / user (chỉ max_uses_total + rule khác).
--   - max_uses_per_user = N    => tối đa N redemption COMMITTED / user / coupon.
--   - max_uses_total NULL     => không giới hạn global; không dùng committed_usage_count.
--   - max_uses_total = M      => atomic UPDATE coupons SET committed_usage_count += 1 WHERE count < M.
--   - Redemption COMMITTED mới tính quota; REVERSED sau cancel/refund hoàn usage (giảm counter nếu có cap).
--
-- LIMITATION backfill:
--   - Insert 1 dòng / order PAID|CONFIRMED có coupon; không tái tạo thứ tự thời gian nếu thiếu order.
--   - Nếu DB cũ mất order history, ledger không thể phục hồi 100%.
--
-- Idempotent: chạy lại an toàn (IF NOT EXISTS / IF EXISTS).
-- =============================================================================

-- 0) Bootstrap: nếu chưa từng chạy add_coupon_redemptions.sql thì tạo bảng (schema gần v2: không UNIQUE coupon+user).
CREATE TABLE IF NOT EXISTS coupon_redemptions (
    id BIGSERIAL PRIMARY KEY,
    coupon_id BIGINT NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id VARCHAR(36) NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    status VARCHAR(24) NOT NULL DEFAULT 'COMMITTED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_coupon_redemptions_order UNIQUE (order_id)
);

CREATE INDEX IF NOT EXISTS ix_coupon_redemptions_coupon_id ON coupon_redemptions (coupon_id);

-- 1) Cột mới
ALTER TABLE coupon_redemptions
    ADD COLUMN IF NOT EXISTS status VARCHAR(24) NOT NULL DEFAULT 'COMMITTED';

ALTER TABLE coupons
    ADD COLUMN IF NOT EXISTS committed_usage_count BIGINT NOT NULL DEFAULT 0;

UPDATE coupon_redemptions SET status = 'COMMITTED' WHERE status IS NULL OR status = '';

-- 2) Bỏ UNIQUE(coupon_id, user_id) — cho phép nhiều lần / user khi max_uses_per_user > 1
ALTER TABLE coupon_redemptions DROP CONSTRAINT IF EXISTS uq_coupon_redemptions_coupon_user;

-- 3) Index phục vụ COUNT / filter
CREATE INDEX IF NOT EXISTS ix_cr_coupon_status ON coupon_redemptions (coupon_id, status);
CREATE INDEX IF NOT EXISTS ix_cr_coupon_user_status ON coupon_redemptions (coupon_id, user_id, status);

-- 4) Chuẩn hoá mã coupon (tránh UPPER(code) trong WHERE)
UPDATE coupons SET code = upper(trim(both from code)) WHERE code IS NOT NULL;

-- 5) Backfill ledger: một dòng mỗi order (order_id unique), không gộp theo user
INSERT INTO coupon_redemptions (coupon_id, user_id, order_id, status)
SELECT c.id, o.user_id, o.id, 'COMMITTED'
FROM orders o
INNER JOIN coupons c ON c.code = upper(trim(both from o.coupon_code))
WHERE o.coupon_code IS NOT NULL
  AND trim(both from o.coupon_code) <> ''
  AND o.status IN ('PAID', 'CONFIRMED')
ON CONFLICT (order_id) DO NOTHING;

-- 6) Đồng bộ counter global từ ledger (sau backfill)
UPDATE coupons cp
SET committed_usage_count = sub.cnt
FROM (
    SELECT coupon_id, COUNT(*)::bigint AS cnt
    FROM coupon_redemptions
    WHERE status = 'COMMITTED'
    GROUP BY coupon_id
) sub
WHERE cp.id = sub.coupon_id;

-- Coupons chưa có redemption: counter = 0 (đã default)

-- =============================================================================
-- VALIDATION sau migrate (chạy tay, kỳ vọng 0 row lỗi global)
-- =============================================================================
-- SELECT cp.id, cp.code, cp.max_uses_total, cp.committed_usage_count,
--        (SELECT COUNT(*) FROM coupon_redemptions r
--         WHERE r.coupon_id = cp.id AND r.status = 'COMMITTED') AS ledger_cnt
-- FROM coupons cp
-- WHERE cp.max_uses_total IS NOT NULL
--   AND cp.committed_usage_count <>
--       (SELECT COUNT(*) FROM coupon_redemptions r2
--        WHERE r2.coupon_id = cp.id AND r2.status = 'COMMITTED');

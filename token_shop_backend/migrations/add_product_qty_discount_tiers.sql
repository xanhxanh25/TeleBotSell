-- Bậc giảm giá theo số lượng (nhiều mốc / sản phẩm). PostgreSQL.
CREATE TABLE IF NOT EXISTS product_qty_discount_tiers (
    id SERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    min_qty INTEGER NOT NULL CHECK (min_qty >= 1),
    percent NUMERIC(5, 2) NOT NULL CHECK (percent >= 0 AND percent <= 100),
    CONSTRAINT uq_pqdt_product_min_qty UNIQUE (product_id, min_qty)
);

CREATE INDEX IF NOT EXISTS ix_pqdt_product_id ON product_qty_discount_tiers(product_id);

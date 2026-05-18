-- Migration: Thêm product_id và user_id vào bảng coupons
-- Chạy script này để cập nhật database

-- Thêm cột product_id (nullable, foreign key đến products)
ALTER TABLE coupons 
ADD COLUMN IF NOT EXISTS product_id BIGINT NULL;

-- Thêm foreign key constraint cho product_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'coupons_product_id_fkey'
    ) THEN
        ALTER TABLE coupons 
        ADD CONSTRAINT coupons_product_id_fkey 
        FOREIGN KEY (product_id) 
        REFERENCES products(id) 
        ON DELETE CASCADE;
    END IF;
END $$;

-- Thêm index cho product_id để tăng tốc query
CREATE INDEX IF NOT EXISTS ix_coupons_product_id ON coupons(product_id);

-- Thêm cột user_id (nullable, foreign key đến users)
ALTER TABLE coupons 
ADD COLUMN IF NOT EXISTS user_id BIGINT NULL;

-- Thêm foreign key constraint cho user_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'coupons_user_id_fkey'
    ) THEN
        ALTER TABLE coupons 
        ADD CONSTRAINT coupons_user_id_fkey 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE;
    END IF;
END $$;

-- Thêm index cho user_id để tăng tốc query
CREATE INDEX IF NOT EXISTS ix_coupons_user_id ON coupons(user_id);

-- Kiểm tra kết quả
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'coupons' 
AND column_name IN ('product_id', 'user_id')
ORDER BY column_name;


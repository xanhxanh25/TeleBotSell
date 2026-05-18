-- Migration: Thêm sort_order vào bảng products
-- Chạy script này để cập nhật database

-- Thêm cột sort_order (nullable integer)
ALTER TABLE products 
ADD COLUMN IF NOT EXISTS sort_order INTEGER NULL;

-- Thêm index cho sort_order để tăng tốc query
CREATE INDEX IF NOT EXISTS ix_products_sort_order ON products(sort_order);

-- Kiểm tra kết quả
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'products' 
AND column_name = 'sort_order';


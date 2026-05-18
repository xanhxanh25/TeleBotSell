-- Migration: Thêm cột telegram_user vào bảng users
-- Chạy script này để thêm cột telegram_user (VARCHAR(255), nullable)

-- Kiểm tra và thêm cột nếu chưa tồn tại
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'telegram_user'
    ) THEN
        ALTER TABLE users 
        ADD COLUMN telegram_user VARCHAR(255) NULL;
        
        RAISE NOTICE '✅ Đã thêm cột telegram_user thành công!';
    ELSE
        RAISE NOTICE 'ℹ️ Cột telegram_user đã tồn tại, bỏ qua.';
    END IF;
END $$;


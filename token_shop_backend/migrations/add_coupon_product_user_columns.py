"""
Migration script: Thêm product_id và user_id vào bảng coupons
Chạy script này bằng: python migrations/add_coupon_product_user_columns.py
"""
import os
import sys

# Thêm project root vào path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load .env
backend_env_path = os.path.join(project_root, ".env")
if os.path.exists(backend_env_path):
    from dotenv import load_dotenv
    load_dotenv(backend_env_path)

from sqlalchemy import create_engine, text
from app.config import settings

def run_migration():
    """Chạy migration để thêm product_id và user_id vào bảng coupons"""
    engine = create_engine(settings.DATABASE_URL)
    
    print("🔄 Đang chạy migration: Thêm product_id và user_id vào bảng coupons...")
    
    with engine.connect() as conn:
        # Bắt đầu transaction
        trans = conn.begin()
        try:
            # Thêm cột product_id
            print("  ➕ Thêm cột product_id...")
            conn.execute(text("""
                ALTER TABLE coupons 
                ADD COLUMN IF NOT EXISTS product_id BIGINT NULL
            """))
            
            # Thêm foreign key cho product_id
            print("  🔗 Thêm foreign key cho product_id...")
            conn.execute(text("""
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
            """))
            
            # Thêm index cho product_id
            print("  📊 Thêm index cho product_id...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_coupons_product_id ON coupons(product_id)
            """))
            
            # Thêm cột user_id
            print("  ➕ Thêm cột user_id...")
            conn.execute(text("""
                ALTER TABLE coupons 
                ADD COLUMN IF NOT EXISTS user_id BIGINT NULL
            """))
            
            # Thêm foreign key cho user_id
            print("  🔗 Thêm foreign key cho user_id...")
            conn.execute(text("""
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
            """))
            
            # Thêm index cho user_id
            print("  📊 Thêm index cho user_id...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_coupons_user_id ON coupons(user_id)
            """))
            
            # Commit transaction
            trans.commit()
            print("✅ Migration hoàn thành!")
            
            # Kiểm tra kết quả
            result = conn.execute(text("""
                SELECT 
                    column_name, 
                    data_type, 
                    is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'coupons' 
                AND column_name IN ('product_id', 'user_id')
                ORDER BY column_name
            """))
            
            print("\n📋 Kết quả:")
            for row in result:
                print(f"  - {row.column_name}: {row.data_type} (nullable: {row.is_nullable})")
                
        except Exception as e:
            trans.rollback()
            print(f"❌ Lỗi khi chạy migration: {e}")
            raise

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n❌ Migration thất bại: {e}")
        sys.exit(1)


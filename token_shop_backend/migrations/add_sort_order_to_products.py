"""
Migration script: Thêm sort_order vào bảng products
Chạy script này bằng: python migrations/add_sort_order_to_products.py
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
    """Chạy migration để thêm sort_order vào bảng products"""
    engine = create_engine(settings.DATABASE_URL)
    
    print("🔄 Đang chạy migration: Thêm sort_order vào bảng products...")
    
    with engine.connect() as conn:
        # Bắt đầu transaction
        trans = conn.begin()
        try:
            # Thêm cột sort_order
            print("  ➕ Thêm cột sort_order...")
            conn.execute(text("""
                ALTER TABLE products 
                ADD COLUMN IF NOT EXISTS sort_order INTEGER NULL
            """))
            
            # Thêm index cho sort_order
            print("  📊 Thêm index cho sort_order...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_products_sort_order ON products(sort_order)
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
                WHERE table_name = 'products' 
                AND column_name = 'sort_order'
            """))
            
            print("\n📋 Kết quả:")
            rows = result.fetchall()
            if rows:
                for row in rows:
                    print(f"  - {row.column_name}: {row.data_type} (nullable: {row.is_nullable})")
            else:
                print("  ⚠️ Không tìm thấy cột sort_order")
                
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


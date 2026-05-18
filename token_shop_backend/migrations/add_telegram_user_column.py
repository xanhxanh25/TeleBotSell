"""
Migration: Thêm cột telegram_user vào bảng users
"""

import os
import sys
from pathlib import Path

# Thêm thư mục token_shop_backend vào path để import được app.*
# Resolve absolute path để tránh lỗi khi chạy từ thư mục khác
script_dir = Path(__file__).resolve().parent
base_dir = script_dir.parent  # token_shop_backend

# Thêm vào sys.path nếu chưa có
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

# Debug: in ra path để kiểm tra
print(f"🔍 Script dir: {script_dir}")
print(f"🔍 Base dir: {base_dir}")
print(f"🔍 Python path: {sys.path[:3]}")

try:
    from sqlalchemy import create_engine, text
    from app.config import settings
except ImportError as e:
    print(f"❌ Lỗi import: {e}")
    print(f"   Đang thử load .env từ: {base_dir / '.env'}")
    # Thử load .env nếu có
    from dotenv import load_dotenv
    env_path = base_dir / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Đã load .env từ: {env_path}")
    else:
        print(f"⚠️ Không tìm thấy .env tại: {env_path}")
    # Thử import lại
    from app.config import settings

def migrate():
    """Thêm cột telegram_user vào bảng users"""
    engine = create_engine(settings.DATABASE_URL)
    
    print("🔄 Đang thêm cột telegram_user vào bảng users...")
    
    with engine.connect() as conn:
        # Kiểm tra xem cột đã tồn tại chưa
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'telegram_user';
        """)
        result = conn.execute(check_query)
        exists = result.fetchone() is not None
        
        if exists:
            print("✅ Cột telegram_user đã tồn tại, bỏ qua.")
            return
        
        # Thêm cột
        alter_query = text("""
            ALTER TABLE users 
            ADD COLUMN telegram_user VARCHAR(255) NULL;
        """)
        conn.execute(alter_query)
        conn.commit()
        
        print("✅ Đã thêm cột telegram_user thành công!")
        print("   Cột này sẽ lưu Telegram username (ví dụ: @username)")

if __name__ == "__main__":
    migrate()


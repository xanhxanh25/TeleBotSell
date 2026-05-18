#!/usr/bin/env python3
"""
Script chạy bot Telegram với error handling tốt hơn
Sử dụng: python run.py
"""
import sys
import os
import asyncio
import logging
from pathlib import Path

# Fix encoding cho Windows console
if sys.platform == "win32":
    try:
        # Set UTF-8 encoding cho stdout và stderr
        if sys.stdout.encoding != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr.encoding != 'utf-8':
            sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Fallback cho Python < 3.7 hoặc nếu reconfigure không hoạt động
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Đảm bảo có thể import app
sys.path.insert(0, str(Path(__file__).parent))

def check_env_file():
    """Kiểm tra file .env có tồn tại không"""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        try:
            print("❌ Không tìm thấy file .env!")
            print("Vui lòng tạo file .env với BOT_TOKEN và các cấu hình cần thiết.")
        except UnicodeEncodeError:
            print("[ERROR] Khong tim thay file .env!")
            print("Vui long tao file .env voi BOT_TOKEN va cac cau hinh can thiet.")
        return False
    return True

def check_logs_dir():
    """Kiểm tra và tạo thư mục logs nếu cần"""
    logs_dir = Path(__file__).parent / "logs"
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True, exist_ok=True)
        try:
            print("✅ Đã tạo thư mục logs")
        except UnicodeEncodeError:
            print("[OK] Da tao thu muc logs")

def check_dependencies():
    """Kiểm tra và cài đặt dependencies nếu cần"""
    requirements_file = Path(__file__).parent / "requirements.txt"
    if not requirements_file.exists():
        try:
            print("⚠️ Không tìm thấy requirements.txt")
        except UnicodeEncodeError:
            print("[!] Khong tim thay requirements.txt")
        return False
    
    # Kiểm tra một số package quan trọng
    try:
        import aiogram
        return True
    except ImportError:
        try:
            print("📦 Đang cài đặt dependencies...")
            print("Vui lòng chờ...")
        except UnicodeEncodeError:
            print("[*] Dang cai dat dependencies...")
            print("Vui long cho...")
        import subprocess
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ])
            try:
                print("✅ Đã cài đặt dependencies thành công!")
            except UnicodeEncodeError:
                print("[OK] Da cai dat dependencies thanh cong!")
            return True
        except subprocess.CalledProcessError:
            try:
                print("❌ Lỗi khi cài đặt dependencies!")
                print("Vui lòng chạy thủ công: pip install -r requirements.txt")
            except UnicodeEncodeError:
                print("[ERROR] Loi khi cai dat dependencies!")
                print("Vui long chay thu cong: pip install -r requirements.txt")
            return False

def main():
    """Main function để chạy bot"""
    try:
        print("🚀 Đang khởi động bot Telegram...")
    except UnicodeEncodeError:
        print("[*] Dang khoi dong bot Telegram...")
    
    # Kiểm tra .env
    if not check_env_file():
        sys.exit(1)
    
    # Kiểm tra logs directory
    check_logs_dir()
    
    # Kiểm tra và cài đặt dependencies
    if not check_dependencies():
        try:
            print("\n❌ Không thể cài đặt dependencies. Vui lòng cài thủ công:")
            print("   pip install -r requirements.txt")
        except UnicodeEncodeError:
            print("\n[ERROR] Khong the cai dat dependencies. Vui long cai thu cong:")
            print("   pip install -r requirements.txt")
        sys.exit(1)
    
    # Import và chạy bot
    try:
        from app.main import main as bot_main
        try:
            print("✅ Đã load bot module")
            print("🤖 Đang chạy bot...")
            print("Nhấn Ctrl+C để dừng bot")
        except UnicodeEncodeError:
            print("[OK] Da load bot module")
            print("[*] Dang chay bot...")
            print("Nhan Ctrl+C de dung bot")
        print("")
        
        # Chạy bot với asyncio
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        try:
            print("\n👋 Bot đã dừng (Ctrl+C).")
        except UnicodeEncodeError:
            print("\n[*] Bot da dung (Ctrl+C).")
        sys.exit(0)
    except ModuleNotFoundError as e:
        try:
            print(f"❌ Thiếu module: {e}")
            print("\nVui lòng cài đặt dependencies:")
            print("   pip install -r requirements.txt")
        except UnicodeEncodeError:
            print(f"[ERROR] Thieu module: {e}")
            print("\nVui long cai dat dependencies:")
            print("   pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        try:
            print(f"❌ Lỗi khi chạy bot: {e}")
        except UnicodeEncodeError:
            print(f"[ERROR] Loi khi chay bot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()


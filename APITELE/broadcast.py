#!/usr/bin/env python3
"""
Tool gửi thông báo broadcast cho tất cả khách hàng từ bot Telegram

Usage:
    python broadcast.py "Nội dung thông báo"
    
Hoặc với file:
    python broadcast.py --file message.txt
    
Hoặc interactive:
    python broadcast.py
"""

import asyncio
import sys
import os
import time
from pathlib import Path

# Check và hướng dẫn cài đặt dependencies
try:
    from aiogram import Bot
    from aiogram.enums import ParseMode
    from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramForbiddenError
except ImportError as e:
    print("❌ Thiếu module cần thiết!")
    print(f"   Lỗi: {e}")
    print("\n📦 Hãy cài đặt dependencies:")
    print("\n   CÁCH 1 (Khuyên dùng - Windows):")
    print("      .\\broadcast.ps1")
    print("\n   CÁCH 2 (Với virtual environment):")
    print("      .\\.venv\\Scripts\\pip install aiogram sqlalchemy psycopg2-binary pydantic pydantic-settings")
    print("      .\\.venv\\Scripts\\python.exe broadcast.py")
    print("\n   CÁCH 3 (Nếu chưa có venv):")
    print("      python -m venv .venv")
    print("      .\\.venv\\Scripts\\activate")
    print("      pip install aiogram sqlalchemy psycopg2-binary pydantic pydantic-settings")
    sys.exit(1)

# Setup paths
apitele_dir = Path(__file__).parent
os.chdir(apitele_dir)  # Change to APITELE directory để load .env đúng

# Import database và config từ backend TRƯỚC (tránh conflict với APITELE app)
backend_path = apitele_dir.parent / "token_shop_backend"
if not backend_path.exists():
    print(f"❌ Không tìm thấy thư mục backend: {backend_path}")
    sys.exit(1)

# Load .env từ backend directory để có DATABASE_URL
backend_env = backend_path / ".env"
if backend_env.exists():
    from dotenv import load_dotenv
    load_dotenv(backend_env)

# Thêm backend_path vào sys.path ĐẦU TIÊN để import app.* hoạt động
# Quan trọng: phải thêm trước khi import APITELE app để tránh conflict
backend_path_str = str(backend_path)
if backend_path_str not in sys.path:
    sys.path.insert(0, backend_path_str)

# Giờ mới import từ backend (sau khi đã load .env và thêm path)
try:
    # Import như bình thường vì đã thêm backend_path vào sys.path
    from app.database import SessionLocal
    from app.models.user import User
except ImportError as e:
    print(f"❌ Không thể import từ backend: {e}")
    print(f"   Backend path: {backend_path}")
    print(f"   Backend path exists: {backend_path.exists()}")
    print(f"   app/database.py exists: {(backend_path / 'app' / 'database.py').exists()}")
    
    # Debug: kiểm tra sys.path
    print(f"\n   sys.path (first 3):")
    for i, p in enumerate(sys.path[:3]):
        print(f"     {i}: {p}")
    
    # Thử import với traceback để debug
    import traceback
    traceback.print_exc()
    
    print("\n📦 Đảm bảo đã cài đặt dependencies:")
    print("   pip install sqlalchemy psycopg2-binary pydantic-settings python-dotenv")
    sys.exit(1)
except Exception as e:
    print(f"❌ Lỗi khi import từ backend: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Sau đó mới import APITELE app (để tránh conflict)
# Thêm APITELE vào sys.path sau backend để backend được ưu tiên
if str(apitele_dir) not in sys.path:
    sys.path.insert(0, str(apitele_dir))
from app.config import settings as apitele_settings


async def get_all_users():
    """Lấy danh sách tất cả telegram_id từ database"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        telegram_ids = [u.telegram_id for u in users]
        return telegram_ids
    finally:
        db.close()


async def send_message(bot: Bot, chat_id: int, message: str) -> tuple[bool, str]:
    """
    Gửi message đến 1 user
    Returns: (success: bool, error_message: str)
    """
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return True, ""
    except TelegramForbiddenError:
        # User đã block bot hoặc không thể nhận message
        return False, "Forbidden (blocked/unavailable)"
    except TelegramBadRequest as e:
        return False, f"BadRequest: {str(e)}"
    except TelegramAPIError as e:
        return False, f"APIError: {str(e)}"
    except Exception as e:
        return False, f"Unknown: {str(e)}"


async def broadcast_message(message: str, delay: float = 0.05):
    """
    Gửi broadcast message cho tất cả users
    
    Args:
        message: Nội dung message cần gửi
        delay: Delay giữa các message (giây) để tránh rate limit. Mặc định 0.05s = 20 msg/s
    """
    print(f"🔍 Đang lấy danh sách users từ database...")
    telegram_ids = await get_all_users()
    total = len(telegram_ids)
    
    if total == 0:
        print("❌ Không tìm thấy user nào trong database!")
        return
    
    print(f"✅ Tìm thấy {total} users")
    print(f"📤 Bắt đầu gửi broadcast...")
    print(f"⏱️  Delay: {delay}s giữa các message (~{int(1/delay)} msg/s)")
    print(f"💬 Message preview: {message[:100]}...")
    print("-" * 60)
    
    # Confirm trước khi gửi
    try:
        confirm = input(f"\n⚠️  Bạn có chắc muốn gửi cho {total} users? (yes/no): ")
        if confirm.lower() not in ["yes", "y", "có"]:
            print("❌ Đã hủy!")
            return
    except KeyboardInterrupt:
        print("\n❌ Đã hủy!")
        return
    
    # Khởi tạo bot
    bot = Bot(token=apitele_settings.BOT_TOKEN)
    
    success_count = 0
    failed_count = 0
    blocked_count = 0
    failed_users = []
    
    start_time = time.time()
    
    try:
        for idx, chat_id in enumerate(telegram_ids, 1):
            success, error = await send_message(bot, chat_id, message)
            
            if success:
                success_count += 1
                status = "✅"
            else:
                failed_count += 1
                if "Forbidden" in error:
                    blocked_count += 1
                failed_users.append((chat_id, error))
                status = "❌"
            
            # Progress update mỗi 10 users
            if idx % 10 == 0 or idx == total:
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                print(f"[{idx}/{total}] {status} {chat_id} | "
                      f"✅ {success_count} | ❌ {failed_count} | "
                      f"⏱️  {elapsed:.1f}s | 📊 {rate:.1f} msg/s")
            
            # Delay để tránh rate limit
            if idx < total:
                await asyncio.sleep(delay)
        
        # Summary
        elapsed_total = time.time() - start_time
        print("-" * 60)
        print(f"📊 <b>KẾT QUẢ BROADCAST</b>")
        print(f"✅ Thành công: {success_count}/{total}")
        print(f"❌ Thất bại: {failed_count}/{total}")
        print(f"🚫 Bị block: {blocked_count}/{total}")
        print(f"⏱️  Thời gian: {elapsed_total:.1f}s")
        print(f"📊 Tốc độ: {total/elapsed_total:.1f} msg/s" if elapsed_total > 0 else "")
        
        if failed_users:
            print(f"\n❌ Users thất bại ({len(failed_users)}):")
            for chat_id, error in failed_users[:20]:  # Chỉ hiển thị 20 đầu
                print(f"  - {chat_id}: {error}")
            if len(failed_users) > 20:
                print(f"  ... và {len(failed_users) - 20} users khác")
    
    finally:
        await bot.session.close()


def get_message_from_args():
    """Lấy message từ command line arguments hoặc environment variable"""
    # Kiểm tra environment variable trước (để tránh lỗi với emoji trong PowerShell)
    if "BROADCAST_MESSAGE" in os.environ:
        message = os.environ["BROADCAST_MESSAGE"]
        if message:
            return message
    
    if len(sys.argv) < 2:
        # Interactive mode
        print("📝 Nhập nội dung thông báo (Enter 2 lần để kết thúc):")
        lines = []
        empty_count = 0
        while True:
            try:
                line = input()
                if not line.strip():
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                    lines.append(line)
            except (EOFError, KeyboardInterrupt):
                break
        return "\n".join(lines).strip()
    
    arg = sys.argv[1]
    
    # Nếu là file path
    if arg == "--file" and len(sys.argv) > 2:
        file_path = sys.argv[2]
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        else:
            print(f"❌ File không tồn tại: {file_path}")
            sys.exit(1)
    
    # Nếu là message trực tiếp
    return arg


async def main():
    """Main function"""
    message = get_message_from_args()
    
    if not message:
        print("❌ Không có nội dung message!")
        print("\nUsage:")
        print('  python broadcast.py "Nội dung thông báo"')
        print("  python broadcast.py --file message.txt")
        print("  python broadcast.py  # Interactive mode")
        sys.exit(1)
    
    # Delay mặc định 0.05s = 20 msg/s (an toàn với Telegram limit 30 msg/s)
    delay = float(os.getenv("BROADCAST_DELAY", "0.05"))
    
    await broadcast_message(message, delay=delay)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Đã bị dừng bởi user!")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


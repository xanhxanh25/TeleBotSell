# 🚀 Tool Broadcast Message (PowerShell)

Tool gửi thông báo broadcast cho tất cả khách hàng từ bot Telegram.

## ⚡ Cách sử dụng (Dễ nhất - PowerShell)

### 1. Gửi message trực tiếp:
```powershell
.\broadcast.ps1 "🎉 Thông báo: Có sản phẩm mới!"
```

### 2. Gửi từ file:
```powershell
.\broadcast.ps1 --file message.txt
```

### 3. Interactive mode (nhập message từ console):
```powershell
.\broadcast.ps1
```

## 📋 Script tự động làm gì?

- ✅ Kiểm tra và tạo virtual environment nếu chưa có
- ✅ Cài đặt dependencies (`aiogram`, `sqlalchemy`, `psycopg2-binary`, etc.) nếu thiếu
- ✅ Chạy tool với môi trường đúng

## ⚙️ Nếu gặp lỗi Execution Policy

Nếu PowerShell báo lỗi về execution policy, chạy lệnh này **một lần**:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 📊 Ví dụ Output

```
🔍 Kiểm tra virtual environment...
✅ Dependencies đã sẵn sàng

🚀 Chạy broadcast tool...

🔍 Đang lấy danh sách users từ database...
✅ Tìm thấy 150 users
📤 Bắt đầu gửi broadcast...

⚠️  Bạn có chắc muốn gửi cho 150 users? (yes/no): yes

[10/150] ✅ 123456789 | ✅ 9 | ❌ 1 | ⏱️  0.5s | 📊 20.0 msg/s
[20/150] ✅ 987654321 | ✅ 18 | ❌ 2 | ⏱️  1.0s | 📊 20.0 msg/s

📊 KẾT QUẢ BROADCAST
✅ Thành công: 145/150
❌ Thất bại: 5/150
🚫 Bị block: 3/150
⏱️  Thời gian: 7.5s
```

## 🎯 Tính năng

- ✅ Lấy tự động danh sách users từ database
- ✅ Xử lý rate limiting (20 msg/s mặc định)
- ✅ Xử lý lỗi (user block bot, invalid user)
- ✅ Progress tracking (hiển thị tiến độ)
- ✅ Summary report (thống kê thành công/thất bại)
- ✅ Hỗ trợ HTML formatting

## ⚙️ Tùy chọn

### Điều chỉnh tốc độ gửi

Mặc định: 0.05s giữa các message (~20 msg/s)

```powershell
# Set environment variable trước khi chạy
$env:BROADCAST_DELAY="0.1"
.\broadcast.ps1 "Message"
```

**Lưu ý:** Telegram giới hạn 30 messages/second. Không nên set delay < 0.035s.

## 📝 Lưu ý

- Tool sẽ yêu cầu xác nhận trước khi gửi
- User đã block bot sẽ không nhận được message (sẽ hiển thị trong failed)
- Không nên gửi quá thường xuyên để tránh spam
- Nên test với 1-2 users trước khi broadcast hàng loạt


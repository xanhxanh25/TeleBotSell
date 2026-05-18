# app/utils.py
"""
Utility functions cho bot
"""
from typing import Union


def format_amount(value: Union[int, float, str]) -> str:
    """
    Format số tiền để hiển thị:
    - Nếu số nguyên (10) -> "10.0"
    - Nếu có nhiều số 0 thừa (10.0005000) -> "10.0005"
    - Bỏ số 0 thừa ở cuối nhưng giữ lại ít nhất 1 số sau dấu chấm nếu là số nguyên
    
    Args:
        value: Giá trị số tiền (int, float, hoặc str có thể convert sang số)
    
    Returns:
        Chuỗi đã được format
    """
    try:
        # Convert sang float
        num = float(value)
        
        # Nếu là số nguyên, format thành "X.0"
        if num == int(num):
            return f"{int(num)}.0"
        
        # Nếu là số thập phân, format và bỏ số 0 thừa ở cuối
        # Dùng format với đủ độ chính xác rồi bỏ số 0 thừa
        formatted = f"{num:.10f}".rstrip('0').rstrip('.')
        
        # Đảm bảo có ít nhất 1 số sau dấu chấm nếu ban đầu có phần thập phân
        # (nhưng không áp dụng cho số nguyên đã được xử lý ở trên)
        if '.' not in formatted:
            # Trường hợp này không xảy ra vì đã check số nguyên ở trên
            # Nhưng để an toàn, thêm lại
            formatted = f"{formatted}.0"
        
        return formatted
    except (ValueError, TypeError):
        # Nếu không convert được, trả về string gốc
        return str(value)


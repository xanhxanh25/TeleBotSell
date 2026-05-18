"""
TokenPay Signature Helper - Python Implementation
Dựa trên source code C# và documentation trong Wiki/docs.md
"""

import hashlib
from typing import Dict, Any, Optional


def calculate_signature(params: Dict[str, Any], api_token: str) -> str:
    """
    Tính Signature cho TokenPay API
    
    Quy tắc:
    1. Lấy tất cả các field (trừ Signature)
    2. Bỏ qua các field có giá trị None hoặc empty string
    3. Sắp xếp theo key (ASCII tăng dần)
    4. Ghép thành chuỗi: key1=value1&key2=value2&...
    5. Nối api_token vào cuối (không thêm &)
    6. MD5 chuỗi đó (lowercase hex)
    
    Args:
        params: Dictionary chứa các tham số (không bao gồm Signature)
        api_token: Khóa thông báo async (ApiToken)
    
    Returns:
        Signature dạng MD5 hex string (lowercase)
    
    Example:
        >>> params = {
        ...     "OutOrderId": "AJIHK72N34BR2CWG",
        ...     "OrderUserKey": "admin@qq.com",
        ...     "ActualAmount": 15,
        ...     "Currency": "TRX",
        ...     "NotifyUrl": "http://localhost:5001/pay/tokenpay/notify_url",
        ...     "RedirectUrl": "http://localhost:5001/pay/tokenpay/return_url?order_id=AJIHK72N34BR2CWG"
        ... }
        >>> api_token = "666"
        >>> signature = calculate_signature(params, api_token)
        >>> print(signature)
        e9765880db6081496456283678e70152
    """
    # Tạo dictionary mới, loại bỏ Signature và các giá trị None/empty
    filtered_params = {}
    for key, value in params.items():
        if key == "Signature":
            continue
        if value is None or value == "":
            continue
        # Keep numeric text representation as-is to match TokenPay side verification.
        filtered_params[key] = str(value)
    
    # Sắp xếp theo key (ASCII tăng dần)
    sorted_keys = sorted(filtered_params.keys())
    
    # Ghép thành chuỗi: key1=value1&key2=value2&...
    signature_str = "&".join([f"{key}={filtered_params[key]}" for key in sorted_keys])
    
    # Nối api_token vào cuối (không thêm &)
    signature_str += api_token
    
    # Tính MD5 (lowercase hex)
    md5_hash = hashlib.md5(signature_str.encode('utf-8')).hexdigest()
    
    return md5_hash


def verify_signature(params: Dict[str, Any], api_token: str) -> bool:
    """
    Verify Signature từ callback hoặc response
    
    Args:
        params: Dictionary chứa các tham số (bao gồm Signature)
        api_token: Khóa thông báo async (ApiToken)
    
    Returns:
        True nếu signature hợp lệ, False nếu không
    
    Example:
        >>> callback_data = {
        ...     "Id": "644bc479-df0c-3f1c-00fe-9cb3012b148b",
        ...     "OutOrderId": "AJIHK72N34BR2CWG",
        ...     "Status": 1,
        ...     "Signature": "e5eaa888cd9e80b5c09a0698981757c8"
        ... }
        >>> api_token = "666"
        >>> is_valid = verify_signature(callback_data, api_token)
    """
    if "Signature" not in params:
        return False
    
    received_signature = params["Signature"]
    
    # Tính signature từ các tham số còn lại
    calculated_signature = calculate_signature(params, api_token)
    
    return received_signature.lower() == calculated_signature.lower()


def create_order_with_signature(
    out_order_id: str,
    order_user_key: str,
    actual_amount: float,
    currency: str,
    api_token: str,
    notify_url: Optional[str] = None,
    redirect_url: Optional[str] = None,
    pass_through_info: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tạo request body cho CreateOrder API với Signature đã tính sẵn
    
    Args:
        out_order_id: Mã đơn hàng bên bạn
        order_user_key: Định danh người dùng thanh toán
        actual_amount: Số tiền pháp định (giữ 2 chữ số thập phân)
        currency: Loại coin/token (ví dụ: USDT_TRC20, TRX)
        api_token: Khóa thông báo async
        notify_url: URL callback bất đồng bộ (optional)
        redirect_url: URL chuyển hướng (optional)
        pass_through_info: Thông tin pass through (optional)
    
    Returns:
        Dictionary chứa request body với Signature đã tính
    
    Example:
        >>> order_data = create_order_with_signature(
        ...     out_order_id="AJIHK72N34BR2CWG",
        ...     order_user_key="admin@qq.com",
        ...     actual_amount=15.0,
        ...     currency="TRX",
        ...     api_token="666",
        ...     notify_url="http://localhost:1011/pay/tokenpay/notify_url",
        ...     redirect_url="http://localhost:1011/pay/tokenpay/return_url?order_id=AJIHK72N34BR2CWG"
        ... )
        >>> print(order_data)
    """
    # Tạo params (chưa có Signature)
    params = {
        "OutOrderId": out_order_id,
        "OrderUserKey": order_user_key,
        "ActualAmount": actual_amount,
        "Currency": currency,
    }
    
    if notify_url:
        params["NotifyUrl"] = notify_url
    if redirect_url:
        params["RedirectUrl"] = redirect_url
    if pass_through_info:
        params["PassThroughInfo"] = pass_through_info
    
    # Tính Signature
    signature = calculate_signature(params, api_token)
    
    # Thêm Signature vào params
    params["Signature"] = signature
    
    return params



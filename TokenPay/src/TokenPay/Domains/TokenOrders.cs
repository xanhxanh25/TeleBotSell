using FreeSql.DataAnnotations;
using System.ComponentModel;

namespace TokenPay.Domains
{
    /// <summary>
    /// Đơn hàng thanh toán
    /// </summary>
    public class TokenOrders
    {
        /// <summary>
        /// Mã đơn giao dịch (ID)
        /// </summary>
        public Guid Id { get; set; }

        /// <summary>
        /// Mã đơn hàng bên ngoài (OutOrderId)
        /// </summary>
        public string OutOrderId { get; set; } = null!;

        /// <summary>
        /// Định danh người dùng thanh toán
        /// </summary>
        public string OrderUserKey { get; set; } = null!;

        /// <summary>
        /// Mã giao dịch trên blockchain (TxHash/TransactionId)
        /// </summary>
        public string? BlockTransactionId { get; set; }

        /// <summary>
        /// Thời gian thanh toán
        /// </summary>
        public DateTime? PayTime { get; set; }

        /// <summary>
        /// Số tiền thực tế đã thanh toán của đơn hàng, làm tròn 2 chữ số thập phân
        /// </summary>
        [Column(Precision = 15, Scale = 2)]
        public decimal? PayAmount { get; set; }

        /// <summary>
        /// Có phải đơn hàng số tiền động hay không
        /// </summary>
        public bool IsDynamicAmount { get; set; }

        /// <summary>
        /// Địa chỉ gửi (địa chỉ nguồn)
        /// </summary>
        public string? FromAddress { get; set; } = null!;

        /// <summary>
        /// Số tiền pháp định thực tế cần thanh toán của đơn hàng, làm tròn 2 chữ số thập phân
        /// </summary>
        [Column(Precision = 15, Scale = 2)]
        public decimal ActualAmount { get; set; }

        /// <summary>
        /// Loại coin/token trên blockchain
        /// </summary>
        public required string Currency { get; set; }

        /// <summary>
        /// Số lượng coin/token của đơn hàng, làm tròn 4 chữ số thập phân
        /// </summary>
        [Column(Precision = 15, Scale = 4)]
        public decimal Amount { get; set; }

        /// <summary>
        /// Địa chỉ ví nhận tiền (địa chỉ đích)
        /// </summary>
        public string ToAddress { get; set; } = null!;

        /// <summary>
        /// Trạng thái đơn hàng
        /// </summary>
        public OrderStatus Status { get; set; }

        /// <summary>
        /// Trả về nguyên văn trong callback hoặc trong thông tin đơn hàng
        /// </summary>
        [Column(StringLength = -1)]
        public string? PassThroughInfo { get; set; }

        /// <summary>
        /// URL thông báo bất đồng bộ (callback)
        /// </summary>
        public string? NotifyUrl { get; set; }

        /// <summary>
        /// URL chuyển hướng đồng bộ (redirect)
        /// </summary>
        public string? RedirectUrl { get; set; }

        /// <summary>
        /// Số lần callback bất đồng bộ
        /// </summary>
        public int CallbackNum { get; set; }

        /// <summary>
        /// Trạng thái xác nhận callback bất đồng bộ
        /// </summary>
        public bool CallbackConfirm { get; set; }

        /// <summary>
        /// Thời điểm thông báo lần cuối
        /// </summary>
        public DateTime? LastNotifyTime { get; set; }

        public DateTime CreateTime { get; set; } = DateTime.Now;
    }

    public enum OrderStatus
    {
        Pending,
        Paid,
        Expired
    }
}

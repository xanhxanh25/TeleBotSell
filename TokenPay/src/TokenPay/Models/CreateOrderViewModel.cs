using System.ComponentModel.DataAnnotations;
using TokenPay.Domains;

namespace TokenPay.Models
{
    public class CreateOrderViewModel
    {
        /// <summary>
        /// Mã đơn hàng bên ngoài
        /// </summary>
        [Display(Name = "Mã đơn hàng bên ngoài")]
        [Required(ErrorMessage = "{0} là tham số bắt buộc")]
        public string OutOrderId { get; set; } = null!;

        /// <summary>
        /// Định danh người dùng thanh toán
        /// </summary>
        [Display(Name = "Định danh người dùng thanh toán")]
        [Required(ErrorMessage = "{0} là tham số bắt buộc")]
        public string OrderUserKey { get; set; } = null!;

        /// <summary>
        /// Số tiền pháp định thực tế cần thanh toán của đơn hàng
        /// </summary>
        [Display(Name = "Số tiền thực trả")]
        [Required(ErrorMessage = "{0} là tham số bắt buộc")]
        public decimal ActualAmount { get; set; }

        /// <summary>
        /// Loại coin/token
        /// </summary>
        [Display(Name = "Loại coin/token")]
        [Required(ErrorMessage = "{0} là tham số bắt buộc")]
        //[(ErrorMessage = "{1} không phải là {0} hợp lệ")]
        public required string Currency { get; set; }

        /// <summary>
        /// Trả về nguyên văn trong callback hoặc trong thông tin đơn hàng
        /// </summary>
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
        /// Chữ ký tham số
        /// </summary>
        public string? Signature { get; set; }
    }
}

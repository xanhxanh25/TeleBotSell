using System.ComponentModel.DataAnnotations;

namespace TokenPay.Domains
{
    public class Tokens
    {
        [Key]
        public required string Id { get; set; }

        /// <summary>
        /// Địa chỉ ví
        /// </summary>
        public required string Address { get; set; }

        /// <summary>
        /// Khóa (private key)
        /// </summary>
        public required string Key { get; set; }

        /// <summary>
        /// Loại coin/token
        /// </summary>
        public TokenCurrency Currency { get; set; }

        /// <summary>
        /// Số dư coin gốc (native coin)
        /// </summary>
        public decimal Value { get; set; }

        /// <summary>
        /// Số dư token USDT
        /// </summary>
        public decimal USDT { get; set; }

        /// <summary>
        /// Thời điểm kiểm tra gần nhất
        /// </summary>
        public DateTime? LastCheckTime { get; set; }
    }

    public enum TokenCurrency
    {
        BTC = 10,
        EVM,
        TRX
    }
}

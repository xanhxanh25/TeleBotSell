using FreeSql.DataAnnotations;
using System.ComponentModel.DataAnnotations;

namespace TokenPay.Domains
{
    public class TokenRate
    {
        public string Id { get; set; } = string.Empty;

        /// <summary>
        /// Loại coin/token
        /// </summary>
        [Column(MapType = typeof(string))]
        public required string Currency { get; set; }

        /// <summary>
        /// Loại tiền pháp định (fiat)
        /// </summary>
        [Column(MapType = typeof(string))]
        public FiatCurrency FiatCurrency { get; set; }

        /// <summary>
        /// Tỷ giá
        /// </summary>
        [Column(Precision = 24, Scale = 12)]
        public decimal Rate { get; set; }

        /// <summary>
        /// Thời điểm cập nhật gần nhất
        /// </summary>
        public DateTime LastUpdateTime { get; set; }
    }

    public enum FiatCurrency
    {
        CNY = 10,
        USD,
        EUR,
        GBP,
        AUD,
        HKD,
        TWD,
        SGD
    }
}

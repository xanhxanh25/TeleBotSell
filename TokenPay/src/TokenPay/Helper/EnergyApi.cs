using Flurl;
using Flurl.Http;
using Flurl.Http.Newtonsoft;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using System.Security.AccessControl;
using System.Text;
using System.Threading.Tasks;

namespace TokenPay.Helper
{
    public class EnergyApi
    {
        const string baseUrl = "https://energy-api.trxd.win";

        private readonly FlurlClient client;
        private readonly ILogger _logger;
        private readonly IConfiguration _configuration;

        public EnergyApi(ILogger logger, IConfiguration configuration)
        {
            _logger = logger;
            _configuration = configuration;

            client = new FlurlClient(baseUrl);
            client.WithSettings(fs => fs.JsonSerializer = new NewtonsoftJsonSerializer(null));

            client.BeforeCall(c =>
            {
                // Giữ zh-CN để tương thích với API hiện tại (nếu API hỗ trợ vi/en thì bạn có thể đổi sau)
                c.Request.WithHeader("Lang", "zh-CN");

                _logger.LogInformation("Gửi request\nURL: {url}\nDữ liệu: {body}", c.Request.Url, c.RequestBody);
            });

            client.AfterCall(async c =>
            {
                _logger.LogInformation(
                    "Nhận response\nURL: {url}\nPhản hồi: {@body}",
                    c.Request.Url,
                    c.Response != null ? await c.Response.GetStringAsync() : null
                );
            });
        }

        /// <summary>
        /// Ước tính giá
        /// </summary>
        public async Task<EnergyResponse<OrderPriceData>> OrderPrice(int resource_value, int rent_duration = 10, string rent_time_unit = "m")
        {
            var result = await client
                .Request("OrderPrice")
                .PostJsonAsync(new
                {
                    resource_value,
                    rent_duration,
                    rent_time_unit
                })
                .ReceiveJson<EnergyResponse<OrderPriceData>>();

            return result;
        }

        /// <summary>
        /// Truy vấn đơn hàng
        /// </summary>
        public async Task<EnergyResponse<OrderData>> OrderQuery(string order_no)
        {
            var result = await client.Request($"OrderQuery/{order_no}")
                .GetJsonAsync<EnergyResponse<OrderData>>();

            return result;
        }

        /// <summary>
        /// Tạo đơn (đặt hàng)
        /// </summary>
        public async Task<EnergyResponse<OrderData>> CreateOrder(CreateOrderModel model)
        {
            var result = await client.Request("CreateOrder")
                .PostJsonAsync(model)
                .ReceiveJson<EnergyResponse<OrderData>>();

            return result;
        }
    }

#pragma warning disable CS8618 // Khi thoát khỏi constructor, các field không-null phải có giá trị khác null. Cân nhắc khai báo nullable nếu cần.
    public class CreateOrderModel
    {
        /// <summary>
        /// Địa chỉ thanh toán
        /// </summary>
        [JsonProperty("pay_address")]
        public string PayAddress { get; set; }

        /// <summary>
        /// Số tiền thanh toán
        /// </summary>
        [JsonProperty("pay_amount")]
        public decimal PayAmount { get; set; }

        /// <summary>
        /// Địa chỉ nhận (địa chỉ được cấp năng lượng/tài nguyên)
        /// </summary>
        [JsonProperty("receive_address")]
        public string ReceiveAddress { get; set; }

        /// <summary>
        /// Thời lượng thuê
        /// </summary>
        [JsonProperty("rent_duration")]
        public int RentDuration { get; set; }

        /// <summary>
        /// Số lượng tài nguyên
        /// </summary>
        [JsonProperty("resource_value")]
        public int ResourceValue { get; set; }

        /// <summary>
        /// Đơn vị thời gian
        /// </summary>
        [JsonProperty("rent_time_unit")]
        public string RentTimeUnit { get; set; } = "h";

        [JsonProperty("signed_txn")]
        public object SignedTxn { get; set; }
    }

    public class EnergyResponse<TData>
    {
        [JsonProperty("code")]
        public int Code { get; set; }

        [JsonProperty("msg")]
        public string Msg { get; set; }

        [JsonProperty("request_id")]
        public string RequestId { get; set; }

        [JsonProperty("data")]
        public TData Data { get; set; }
    }

    public class OrderPrice
    {
        [JsonProperty("resource_value")]
        public int ResourceValue { get; set; }

        [JsonProperty("pay_amount")]
        public decimal PayAmount { get; set; }

        [JsonProperty("service_amount")]
        public decimal ServiceAmount { get; set; }

        [JsonProperty("rent_duration")]
        public int RentDuration { get; set; }

        [JsonProperty("rent_time_unit")]
        public string RentTimeUnit { get; set; }

        [JsonProperty("price_in_sun")]
        public decimal PriceInSun { get; set; }
    }

    public class OrderData : OrderPrice
    {
        [JsonProperty("order_no")]
        public string OrderNo { get; set; }

        [JsonProperty("order_num")]
        public int OrderNum { get; set; }

        [JsonProperty("order_type")]
        public int OrderType { get; set; }

        [JsonProperty("resource_type")]
        public int ResourceType { get; set; }

        [JsonProperty("receive_address")]
        public string ReceiveAddress { get; set; }

        [JsonProperty("price_in_sun")]
        public new int PriceInSun { get; set; }

        [JsonProperty("min_amount")]
        public int MinAmount { get; set; }

        [JsonProperty("min_payout")]
        public int MinPayout { get; set; }

        [JsonProperty("min_freeze")]
        public int MinFreeze { get; set; }

        [JsonProperty("max_amount")]
        public int MaxAmount { get; set; }

        [JsonProperty("max_payout")]
        public int MaxPayout { get; set; }

        [JsonProperty("max_freeze")]
        public int MaxFreeze { get; set; }

        [JsonProperty("freeze_time")]
        public int FreezeTime { get; set; }

        [JsonProperty("unfreeze_time")]
        public int UnfreezeTime { get; set; }

        [JsonProperty("expire_time")]
        public int ExpireTime { get; set; }

        [JsonProperty("create_time")]
        public int CreateTime { get; set; }

        [JsonProperty("resource_value")]
        public new int ResourceValue { get; set; }

        [JsonProperty("resource_split_value")]
        public int ResourceSplitValue { get; set; }

        [JsonProperty("frozen_resource_value")]
        public int FrozenResourceValue { get; set; }

        [JsonProperty("rent_duration")]
        public new int RentDuration { get; set; }

        [JsonProperty("rent_time_unit")]
        public new string RentTimeUnit { get; set; }

        [JsonProperty("rent_expire_time")]
        public int RentExpireTime { get; set; }

        [JsonProperty("frozen_balance")]
        public int FrozenBalance { get; set; }

        [JsonProperty("frozen_tx_id")]
        public string FrozenTxId { get; set; }

        [JsonProperty("unfreeze_tx_id")]
        public string UnfreezeTxId { get; set; }

        [JsonProperty("settle_amount")]
        public decimal SettleAmount { get; set; }

        [JsonProperty("settle_address")]
        public string SettleAddress { get; set; }

        [JsonProperty("settle_time")]
        public int SettleTime { get; set; }

        [JsonProperty("pay_action")]
        public int PayAction { get; set; }

        [JsonProperty("pay_address")]
        public string PayAddress { get; set; }

        [JsonProperty("pay_time")]
        public int PayTime { get; set; }

        [JsonProperty("pay_tx_id")]
        public string PayTxId { get; set; }

        [JsonProperty("pay_symbol")]
        public string PaySymbol { get; set; }

        [JsonProperty("pay_amount")]
        public new decimal PayAmount { get; set; }

        [JsonProperty("pay_status")]
        public int PayStatus { get; set; }

        [JsonProperty("refund_amount")]
        public decimal RefundAmount { get; set; }

        [JsonProperty("is_split")]
        public int IsSplit { get; set; }

        [JsonProperty("cancel_tx_id")]
        public string CancelTxId { get; set; }

        [JsonProperty("refund_tx_id")]
        public string RefundTxId { get; set; }

        [JsonProperty("status")]
        public FeeeOrderStatus Status { get; set; }

        /// <summary>
        /// Đơn con (sub-order)
        /// </summary>
        [JsonProperty("sub_order")]
        public List<OrderData> SubOrder { get; set; }
    }

    // Lưu ý: Giữ nguyên tên enum tiếng Trung để KHÔNG phá vỡ các đoạn code đang so sánh trạng thái (ví dụ FeeeOrderStatus.已质押).
    // Nếu bạn muốn đổi sang tiếng Việt (refactor), mình sẽ đổi đồng bộ toàn dự án.
    public enum FeeeOrderStatus
    {
        未支付 = 1,         // Chưa thanh toán
        已关闭支付 = 2,     // Đã đóng thanh toán
        已支付待验证 = 3,   // Đã thanh toán - chờ xác minh
        已支付 = 4,         // Đã thanh toán
        已质押待验证 = 5,   // Đã stake (đóng băng) - chờ xác minh
        已质押 = 6,         // Đã stake (đóng băng)
        质押失败 = 7,       // Stake thất bại
        已解押待验证 = 8,   // Đã unstake - chờ xác minh
        已解押 = 9,         // Đã unstake
        解押失败 = 1,       // Unstake thất bại (giá trị trùng 1 như bản gốc)
        取消待处理 = 11,     // Hủy - đang chờ xử lý
        已取消 = 12,        // Đã hủy
        待退款 = 13,        // Chờ hoàn tiền
        已退款 = 14,        // Đã hoàn tiền
        质押进行中 = 15,     // Đang stake
        暂时锁定 = 16,       // Tạm khóa
        推迟回收 = 17,       // Trì hoãn thu hồi
    }

    public class OrderPriceData
    {
        [JsonProperty("pay_address")]
        public string PayAddress { get; set; }

        [JsonProperty("pay_amount")]
        public decimal Price { get; set; }
    }
#pragma warning restore CS8618 // Khi thoát khỏi constructor, các field không-null phải có giá trị khác null. Cân nhắc khai báo nullable nếu cần.
}

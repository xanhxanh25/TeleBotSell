using Flurl;
using Flurl.Http;
using FreeSql;
using Newtonsoft.Json;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Channels;
using TokenPay.Domains;

namespace TokenPay.BgServices
{
    /// <summary>
    /// Theo dõi nạp tiền qua Binance Pay (P2P transfer giữa các tài khoản Binance).
    ///
    /// Flow người dùng:
    ///   1. Bot hiển thị: "Gửi USDT đến Binance ID: {BinanceId}, Note: SHOP{telegram_id}"
    ///   2. User mở Binance app → Pay → Send → nhập BinanceId → điền Note bắt buộc
    ///   3. Service poll /sapi/v1/pay/transactions mỗi 30s
    ///   4. Tìm giao dịch có remark == "SHOP{OrderUserKey}" → khớp đơn → Paid
    ///
    /// Tại sao match bằng Note (không phải Amount):
    ///   - Note = "SHOP{telegram_id}" → unique per user
    ///   - Python backend giới hạn 1 pending BINANCE_PAY order mỗi lúc
    ///   - → Note đủ để xác định đúng order, không cần unique_amount trick
    ///   - Amount vẫn được validate thêm để chống gian lận
    ///
    /// Cấu hình trong appsettings.json:
    ///   "Binance": {
    ///     "Enable": true,
    ///     "ApiKey":      "read-only API key",
    ///     "ApiSecret":   "api secret",
    ///     "BinanceId":   "711662011",
    ///     "NotePrefix":  "SHOP"
    ///   }
    ///
    /// API key chỉ cần quyền: Enable Reading + Enable Binance Pay (Read)
    /// Không cần quyền Trade hay Withdraw.
    /// </summary>
    public class OrderCheckBinanceService : BaseScheduledService
    {
        private const string BinanceCurrencyPrefix = "BINANCE_";
        private const string BinancePayApiBase     = "https://api.binance.com";

        // Quét giao dịch trong bao nhiêu giờ gần đây
        private const int LookbackHours = 2;

        private readonly IConfiguration _configuration;
        private readonly IFreeSql _freeSql;
        private readonly Channel<TokenOrders> _channel;

        public OrderCheckBinanceService(
            ILogger<OrderCheckBinanceService> logger,
            IConfiguration configuration,
            IFreeSql freeSql,
            Channel<TokenOrders> channel
        ) : base("Kiểm tra nạp Binance Pay (P2P)", TimeSpan.FromSeconds(30), logger)
        {
            _configuration = configuration;
            _freeSql       = freeSql;
            _channel       = channel;
        }

        protected override async Task ExecuteAsync(DateTime runTime, CancellationToken stoppingToken)
        {
            if (!_configuration.GetValue("Binance:Enable", false)) return;

            var apiKey    = _configuration.GetValue<string>("Binance:ApiKey")    ?? "";
            var apiSecret = _configuration.GetValue<string>("Binance:ApiSecret") ?? "";

            if (string.IsNullOrWhiteSpace(apiKey) || string.IsNullOrWhiteSpace(apiSecret))
            {
                _logger.LogWarning("[BinancePay] ApiKey hoặc ApiSecret chưa cấu hình");
                return;
            }

            try
            {
                await CheckPayTransactions(apiKey, apiSecret);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "[BinancePay] Lỗi khi poll giao dịch");
            }
        }

        private async Task CheckPayTransactions(string apiKey, string apiSecret)
        {
            var repo = _freeSql.GetRepository<TokenOrders>();

            // ── 1. Lấy tất cả pending BINANCE_PAY orders ────────────────
            var pendingOrders = await repo
                .Where(x => x.Status == OrderStatus.Pending
                         && x.Currency.StartsWith(BinanceCurrencyPrefix))
                .OrderBy(x => x.CreateTime)
                .ToListAsync();

            if (!pendingOrders.Any()) return;

            // Build map: note → order (note = PassThroughInfo = "SHOP{telegram_id}")
            // Nếu trùng note (do DB có nhiều pending cùng user), lấy order mới nhất
            var noteToOrder = pendingOrders
                .Where(x => !string.IsNullOrEmpty(x.PassThroughInfo))
                .GroupBy(x => x.PassThroughInfo!, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(g => g.Key, g => g.OrderByDescending(o => o.CreateTime).First(), StringComparer.OrdinalIgnoreCase);

            // ── 2. Poll Binance Pay transactions ─────────────────────────
            var startTime = DateTimeOffset.UtcNow
                .AddHours(-LookbackHours)
                .ToUnixTimeMilliseconds();

            var transactions = await FetchPayTransactions(apiKey, apiSecret, startTime);
            if (transactions == null || transactions.Count == 0) return;

            _logger.LogDebug("[BinancePay] Nhận {Count} giao dịch trong {H}h qua",
                transactions.Count, LookbackHours);

            // ── 3. Match từng giao dịch ──────────────────────────────────
            foreach (var tx in transactions)
            {
                // Chỉ xử lý giao dịch NHẬN tiền (CREDIT / C2C incoming)
                if (!IsIncoming(tx)) continue;

                // Dedup
                var txId = tx.TransactionId ?? "";
                if (!string.IsNullOrEmpty(txId)
                    && await repo.Select.AnyAsync(x => x.BlockTransactionId == txId))
                    continue;

                // Lấy note từ giao dịch
                var note = tx.Remark ?? tx.Note ?? "";
                if (string.IsNullOrWhiteSpace(note)) continue;

                // Tìm order theo note
                if (!noteToOrder.TryGetValue(note, out var matched)) continue;

                // Validate time: giao dịch Binance phải SAU thời điểm tạo order
                // Tránh nhận nhầm giao dịch cũ (ví dụ user nạp $1 trước đó)
                // Binance API trả TransactionTime = Unix ms (UTC)
                // matched.CreateTime = DateTime.Now (local time, VN = UTC+7)
                // => Convert txTime về local time để so sánh đồng nhất
                var txTime = DateTimeOffset.FromUnixTimeMilliseconds(tx.TransactionTime).LocalDateTime;
                if (txTime < matched.CreateTime)
                {
                    _logger.LogWarning(
                        "[BinancePay] ⏰ Giao dịch {TxId} trước thời điểm tạo order: tx={TxTime}, order={OrderTime}",
                        txId, txTime, matched.CreateTime);
                    continue;
                }

                // Validate amount: giao dịch phải >= số tiền order yêu cầu
                // (cho phép nạp dư, không cho nạp thiếu)
                var receivedAmount = tx.Amount;
                if (receivedAmount < matched.Amount)
                {
                    _logger.LogWarning(
                        "[BinancePay] ⚠️ Giao dịch {TxId} thiếu tiền: nhận {Got}, cần {Need}",
                        txId, receivedAmount, matched.Amount);
                    continue;
                }

                // ── 4. Cập nhật order → Paid ──────────────────────────
                matched.BlockTransactionId = txId;
                matched.FromAddress        = tx.SenderBinanceId ?? "";
                matched.Status             = OrderStatus.Paid;
                matched.PayTime            = DateTimeOffset
                    .FromUnixTimeMilliseconds(tx.TransactionTime).LocalDateTime;
                matched.PayAmount          = receivedAmount;

                await repo.UpdateAsync(matched);
                noteToOrder.Remove(note); // tránh xử lý lại

                _logger.LogInformation(
                    "[BinancePay] ✅ Khớp | order={OrderId} | note={Note} | amount={Amount} USDT | tx={TxId}",
                    matched.OutOrderId, note, receivedAmount, txId);

                await _channel.Writer.WriteAsync(matched);
            }
        }

        // ─── Binance Pay API ──────────────────────────────────────────────

        /// <summary>
        /// GET /sapi/v1/pay/transactions
        /// Trả về lịch sử giao dịch Binance Pay của tài khoản (cả gửi lẫn nhận).
        /// </summary>
        private async Task<List<BinancePayTransaction>?> FetchPayTransactions(
            string apiKey, string apiSecret, long startTime)
        {
            var timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

            var query = new Dictionary<string, object>
            {
                { "startTime",  startTime },
                { "limit",      100       },
                { "timestamp",  timestamp },
            };

            var queryString = string.Join("&", query.Select(kv => $"{kv.Key}={kv.Value}"));
            var signature   = SignHmacSha256(queryString, apiSecret);
            queryString    += $"&signature={signature}";

            var url = $"{BinancePayApiBase}/sapi/v1/pay/transactions?{queryString}";

            BinancePayResponse? wrapper;
            try
            {
                wrapper = await url
                    .WithHeader("X-MBX-APIKEY", apiKey)
                    .WithTimeout(15)
                    .GetJsonAsync<BinancePayResponse>();
            }
            catch (Flurl.Http.FlurlHttpException ex)
            {
                var body = await ex.GetResponseStringAsync();
                _logger.LogError("[BinancePay] HTTP {Status} body: {Body}", ex.StatusCode, body);
                throw;
            }

            if (wrapper?.Code != "000000")
            {
                _logger.LogWarning("[BinancePay] API trả lỗi: code={Code} msg={Msg}",
                    wrapper?.Code, wrapper?.Message);
                return null;
            }

            return wrapper.Data;
        }

        /// <summary>Giao dịch này là tiền NHẬN về (không phải tiền gửi đi)</summary>
        private static bool IsIncoming(BinancePayTransaction tx)
        {
            // Binance Pay API trả về cả CREDIT (nhận) và DEBIT (gửi)
            // Một số trường hợp field tên khác nhau tùy version API
            var tradeType = (tx.TradeType ?? "").ToUpperInvariant();
            if (tradeType is "CREDIT" or "IN" or "RECEIVE") return true;
            if (tradeType is "DEBIT" or "OUT" or "SEND") return false;

            // Fallback: nếu không rõ tradeType, cứ xử lý
            // (sẽ bị dedup bởi BlockTransactionId nếu là giao dịch gửi đi)
            return true;
        }

        private static string SignHmacSha256(string data, string secret)
        {
            using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
            return Convert.ToHexString(hmac.ComputeHash(Encoding.UTF8.GetBytes(data)))
                          .ToLowerInvariant();
        }
    }

    // ─── Binance Pay API Response Models ─────────────────────────────────

    public class BinancePayResponse
    {
        [JsonProperty("code")]    public string? Code    { get; set; }
        [JsonProperty("message")] public string? Message { get; set; }
        [JsonProperty("success")] public bool    Success { get; set; }
        // Binance Pay API trả "data" là array trực tiếp
        [JsonProperty("data")]    public List<BinancePayTransaction>? Data { get; set; }
    }

    public class BinancePayTransaction
    {
        /// <summary>C2C_TRANSFER, C2B_TRANSFER, etc.</summary>
        [JsonProperty("orderType")]
        public string? OrderType { get; set; }

        /// <summary>ID giao dịch duy nhất — dùng để dedup</summary>
        [JsonProperty("transactionId")]
        public string? TransactionId { get; set; }

        /// <summary>Thời gian giao dịch (Unix ms)</summary>
        [JsonProperty("transactionTime")]
        public long TransactionTime { get; set; }

        /// <summary>Số tiền</summary>
        [JsonProperty("amount")]
        public decimal Amount { get; set; }

        /// <summary>Loại coin (USDT, BNB...)</summary>
        [JsonProperty("currency")]
        public string? Currency { get; set; }

        /// <summary>
        /// CREDIT = nhận tiền vào, DEBIT = gửi tiền đi
        /// Một số phiên bản API dùng: PAY / REFUND / TRANSFER
        /// </summary>
        [JsonProperty("tradeType")]
        public string? TradeType { get; set; }

        /// <summary>
        /// Note/Memo người gửi đính kèm — đây là trường key để match.
        /// Binance Pay gọi là "remark" hoặc "note" tùy version.
        /// </summary>
        [JsonProperty("remark")]
        public string? Remark { get; set; }

        /// <summary>Alias cho Remark (một số API version dùng tên khác)</summary>
        [JsonProperty("note")]
        public string? Note { get; set; }

        /// <summary>Binance Pay ID của người gửi (nếu Binance trả về)</summary>
        [JsonProperty("payerInfo")]
        public BinancePayerInfo? PayerInfo { get; set; }

        public string? SenderBinanceId => PayerInfo?.BinanceId?.ToString();
    }

    public class BinancePayerInfo
    {
        [JsonProperty("binanceId")] public long?   BinanceId { get; set; }
        [JsonProperty("name")]      public string? Name      { get; set; }
    }
}

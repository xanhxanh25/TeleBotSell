using Newtonsoft.Json;
using System.Globalization;
using System.Numerics;

namespace TokenPay.Models.EthModel
{
    // ─────────────────────────────────────────────────────────────
    // Các model dùng cho JSON-RPC trực tiếp (BSC/EVM RPC node)
    // Không cần API key — dùng public free RPC endpoint
    // ─────────────────────────────────────────────────────────────

    public class JsonRpcRequest
    {
        [JsonProperty("jsonrpc")] public string JsonRpc { get; set; } = "2.0";
        [JsonProperty("method")]  public string Method  { get; set; } = "";
        [JsonProperty("params")]  public object? Params { get; set; }
        [JsonProperty("id")]      public int Id { get; set; } = 1;
    }

    public class JsonRpcResponse<T>
    {
        [JsonProperty("result")] public T? Result { get; set; }
        [JsonProperty("error")]  public JsonRpcError? Error { get; set; }
    }

    public class JsonRpcError
    {
        [JsonProperty("code")]    public int    Code    { get; set; }
        [JsonProperty("message")] public string Message { get; set; } = "";
    }

    /// <summary>
    /// Một log entry từ eth_getLogs — đại diện cho 1 Transfer event ERC20
    /// </summary>
    public class EthLog
    {
        [JsonProperty("address")]          public string       Address          { get; set; } = "";
        [JsonProperty("topics")]           public List<string> Topics           { get; set; } = [];
        [JsonProperty("data")]             public string       Data             { get; set; } = "";
        [JsonProperty("blockNumber")]      public string       BlockNumber      { get; set; } = "";
        [JsonProperty("transactionHash")]  public string       TransactionHash  { get; set; } = "";
        [JsonProperty("logIndex")]         public string       LogIndex         { get; set; } = "";
        [JsonProperty("blockHash")]        public string       BlockHash        { get; set; } = "";
        [JsonProperty("transactionIndex")] public string       TransactionIndex { get; set; } = "";
        [JsonProperty("removed")]          public bool         Removed          { get; set; }

        // ── Helpers ──────────────────────────────────────────────

        public long BlockNumberDecimal =>
            string.IsNullOrEmpty(BlockNumber) ? 0 : Convert.ToInt64(BlockNumber, 16);

        public int LogIndexDecimal =>
            string.IsNullOrEmpty(LogIndex) ? 0 : Convert.ToInt32(LogIndex, 16);

        // Transfer(address indexed from, address indexed to, uint256 value)
        // topics[0] = event signature keccak256
        // topics[1] = from (padded 32 bytes)
        // topics[2] = to   (padded 32 bytes)
        // data      = value (uint256 hex, 32 bytes)
        public string From => Topics.Count > 1 && Topics[1].Length >= 42
            ? "0x" + Topics[1][^40..] : "";
        public string To => Topics.Count > 2 && Topics[2].Length >= 42
            ? "0x" + Topics[2][^40..] : "";

        /// <summary>
        /// Chuyển đổi value hex → decimal với số chữ số thập phân chỉ định.
        /// BSC USDT có 18 decimals.
        /// Dùng BigInteger để tránh mất độ chính xác khi giá trị lớn.
        /// </summary>
        public decimal ParseAmount(int decimals = 18)
        {
            var hex = Data.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
                ? Data[2..] : Data;
            if (string.IsNullOrWhiteSpace(hex)) return 0;

            // "0" prefix bắt buộc để BigInteger.Parse nhận là unsigned
            var big = BigInteger.Parse("0" + hex, NumberStyles.HexNumber);
            var divisor = BigInteger.Pow(10, decimals);

            // DivRem an toàn hơn chia trực tiếp khi số lớn
            var quotient  = BigInteger.DivRem(big, divisor, out var remainder);
            return (decimal)quotient + (decimal)remainder / (decimal)divisor;
        }

        /// <summary>Key duy nhất để dedup: tránh xử lý cùng 1 Transfer 2 lần</summary>
        public string UniqueKey => $"{TransactionHash}:{LogIndexDecimal}";
    }
}

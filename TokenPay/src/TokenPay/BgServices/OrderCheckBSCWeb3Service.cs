using Flurl;
using Flurl.Http;
using FreeSql;
using System.Threading.Channels;
using TokenPay.Domains;
using TokenPay.Extensions;
using TokenPay.Models.EthModel;

namespace TokenPay.BgServices
{
    /// <summary>
    /// Theo dõi giao dịch ERC20 trên các chain có UseRpc=true (ví dụ BSC)
    /// thông qua JSON-RPC trực tiếp — MIỄN PHÍ, không cần API key trả phí.
    ///
    /// Chiến lược:
    /// - Mỗi 30s: lấy block mới nhất, quét window [lastBlock+1 .. currentBlock-Confirmations]
    /// - Gọi eth_getLogs với filter: contract = USDT, topics[2] = toAddress
    /// - So khớp amount (Decimal) với pending orders
    /// - Lưu lastProcessedBlock trong bộ nhớ; khi restart tự lùi về -100 block để không bỏ sót
    /// - Dedup bằng TransactionHash+LogIndex → không bao giờ credit 2 lần cho cùng 1 event
    /// </summary>
    public class OrderCheckBSCWeb3Service : BaseScheduledService
    {
        // keccak256("Transfer(address,address,uint256)")
        private const string TransferTopic =
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";

        // Khi restart, lùi về tối đa bao nhiêu block để tránh bỏ sót
        private const int RestartLookbackBlocks = 20;

        // Số block tối đa mỗi lần eth_getLogs (bsc-rpc.publicnode.com hỗ trợ ~1000)
        private const int MaxBlockRange = 200;

        private readonly IConfiguration _configuration;
        private readonly List<EVMChain> _chains;
        private readonly Channel<TokenOrders> _channel;
        private readonly IFreeSql _freeSql;

        // lastBlock per chain: chỉ giữ trong memory, an toàn khi restart (lookback cover it)
        private readonly Dictionary<string, long> _lastProcessedBlock = new();

        public OrderCheckBSCWeb3Service(
            ILogger<OrderCheckBSCWeb3Service> logger,
            IConfiguration configuration,
            List<EVMChain> chains,
            Channel<TokenOrders> channel,
            IFreeSql freeSql
        ) : base("Kiểm tra ERC20 qua Web3 RPC (miễn phí)", TimeSpan.FromSeconds(30), logger)
        {
            _configuration = configuration;
            _chains = chains;
            _channel = channel;
            _freeSql = freeSql;
        }

        protected override async Task ExecuteAsync(DateTime runTime, CancellationToken stoppingToken)
        {
            var repo = _freeSql.GetRepository<TokenOrders>();

            foreach (var chain in _chains)
            {
                // Chỉ xử lý chain đã bật và dùng RPC mode
                if (chain == null || !chain.Enable || chain.UseRpc == false
                    || string.IsNullOrEmpty(chain.RpcUrl)
                    || chain.ERC20 == null) continue;

                foreach (var erc20 in chain.ERC20)
                {
                    // Bỏ qua contract chưa được cấu hình hoặc không hợp lệ
                    if (string.IsNullOrWhiteSpace(erc20.ContractAddress)
                        || erc20.ContractAddress.Equals("NO ADDRESS", StringComparison.OrdinalIgnoreCase))
                        continue;

                    var currency = $"EVM_{chain.ChainNameEN}_{erc20.Name}_{chain.ERC20Name}";
                    try
                    {
                        await ScanERC20(repo, chain, erc20, currency, stoppingToken);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "[Web3] {Currency} lỗi khi quét giao dịch", currency);
                    }
                }
            }
        }

        private async Task ScanERC20(
            IBaseRepository<TokenOrders> repo,
            EVMChain chain,
            EVMErc20 erc20,
            string currency,
            CancellationToken ct)
        {
            var rpcUrl = chain.RpcUrl!;

            // ── 1. Lấy block hiện tại ────────────────────────────────────
            var currentBlock = await GetBlockNumber(rpcUrl);
            if (currentBlock <= 0)
            {
                _logger.LogWarning("[Web3] {Chain} không lấy được block number", chain.ChainNameEN);
                return;
            }

            // Block "safe" = đủ confirmations
            var safeBlock = currentBlock - chain.Confirmations;
            if (safeBlock <= 0) return;

            // ── 2. Xác định fromBlock ────────────────────────────────────
            var chainKey = $"{chain.ChainNameEN}_{erc20.Name}";
            if (!_lastProcessedBlock.TryGetValue(chainKey, out var lastBlock) || lastBlock <= 0)
            {
                // Khởi động lần đầu: lùi về để không bỏ sót pending orders
                lastBlock = Math.Max(0, safeBlock - RestartLookbackBlocks);
            }

            var fromBlock = lastBlock + 1;
            if (fromBlock > safeBlock) return; // chưa có block mới đủ confirm

            // ── 3. Lấy danh sách pending orders của currency này ─────────
            var pendingOrders = await repo
                .Where(x => x.Status == OrderStatus.Pending && x.Currency == currency)
                .OrderBy(x => x.CreateTime)
                .ToListAsync();

            if (!pendingOrders.Any())
            {
                // Không có pending → vẫn cập nhật lastBlock để không scan lại khi có đơn mới
                _lastProcessedBlock[chainKey] = safeBlock;
                return;
            }

            // Tập hợp các toAddress cần lọc (tối ưu: chỉ fetch log liên quan)
            var watchedAddresses = pendingOrders
                .Select(x => x.ToAddress.ToLowerInvariant())
                .Distinct()
                .ToHashSet();

            // ── 4. Quét theo từng toAddress (eth_getLogs lọc topic[2]) ───
            // BSC RPC thường giới hạn 5000 kết quả mỗi request;
            // chia nhỏ block range + filter theo address để không vượt giới hạn.
            var toBlock = Math.Min(fromBlock + MaxBlockRange - 1, safeBlock);

            foreach (var toAddr in watchedAddresses)
            {
                // Pad address thành 32 bytes cho topic filter
                var paddedAddr = "0x" + toAddr.Replace("0x", "").PadLeft(64, '0');

                var logs = await GetLogs(
                    rpcUrl,
                    erc20.ContractAddress,
                    TransferTopic,
                    null,          // topic[1] = from: any
                    paddedAddr,    // topic[2] = to: our address
                    fromBlock,
                    toBlock
                );

                if (logs == null || logs.Count == 0) continue;

                // Lấy các đơn pending cho địa chỉ này
                var addrOrders = pendingOrders
                    .Where(x => x.ToAddress.Equals(toAddr, StringComparison.OrdinalIgnoreCase))
                    .ToList();

                foreach (var log in logs)
                {
                    // Bỏ qua log bị reorg
                    if (log.Removed) continue;

                    // Dedup: tx đã được dùng để khớp đơn khác chưa?
                    if (await repo.Select.AnyAsync(x => x.BlockTransactionId == log.TransactionHash))
                        continue;

                    if (!addrOrders.Any()) break;

                    // Chuyển đổi amount từ hex (USDT BSC = 18 decimals)
                    var receivedAmount = log.ParseAmount(decimals: 18);

                    // Khớp: amount chính xác + toAddress đúng
                    // Ưu tiên đơn tạo gần nhất (OrderByDescending CreateTime)
                    // để người dùng trả đơn mới nhất trước
                    var matched = addrOrders
                        .Where(x => x.Amount == receivedAmount
                                 && x.ToAddress.Equals(log.To, StringComparison.OrdinalIgnoreCase))
                        .OrderByDescending(x => x.CreateTime)
                        .FirstOrDefault();

                    if (matched != null)
                    {
                        matched.FromAddress        = log.From;
                        matched.BlockTransactionId = log.TransactionHash;
                        matched.Status             = OrderStatus.Paid;
                        // BlockTimestamp không có trong log; dùng thời gian hiện tại (local)
                        matched.PayTime  = DateTime.Now;
                        matched.PayAmount = receivedAmount;

                        await repo.UpdateAsync(matched);
                        addrOrders.Remove(matched);

                        _logger.LogInformation(
                            "[Web3] ✅ Khớp đơn {OrderId} | {Currency} | {Amount} | tx={TxHash}",
                            matched.OutOrderId, currency, receivedAmount, log.TransactionHash);

                        await _channel.Writer.WriteAsync(matched);
                    }
                }
            }

            // ── 5. Cập nhật last processed block ────────────────────────
            _lastProcessedBlock[chainKey] = toBlock;
        }

        // ─── JSON-RPC Helpers ─────────────────────────────────────────────

        /// <summary>Gọi eth_blockNumber, trả về block number dạng long</summary>
        private static async Task<long> GetBlockNumber(string rpcUrl)
        {
            var req = new JsonRpcRequest
            {
                Method = "eth_blockNumber",
                Params = Array.Empty<object>()
            };

            var resp = await rpcUrl
                .PostJsonAsync(req)
                .ReceiveJson<JsonRpcResponse<string>>();

            if (resp?.Result == null) return 0;
            return Convert.ToInt64(resp.Result, 16);
        }

        /// <summary>
        /// Gọi eth_getLogs để lấy Transfer events lọc theo contract + topics + block range.
        /// topic1 = from (null = any), topic2 = to (địa chỉ nhận, padded 32 bytes)
        /// </summary>
        private static async Task<List<EthLog>?> GetLogs(
            string rpcUrl,
            string contractAddress,
            string topic0,
            string? topic1,
            string? topic2,
            long fromBlock,
            long toBlock)
        {
            var topics = new List<object?> { topic0, topic1, topic2 };

            var filter = new
            {
                address   = contractAddress,
                topics    = topics,
                fromBlock = "0x" + fromBlock.ToString("X"),
                toBlock   = "0x" + toBlock.ToString("X")
            };

            var req = new JsonRpcRequest
            {
                Method = "eth_getLogs",
                Params = new object[] { filter }
            };

            var resp = await rpcUrl
                .PostJsonAsync(req)
                .ReceiveJson<JsonRpcResponse<List<EthLog>>>();

            if (resp?.Error != null)
                throw new Exception($"eth_getLogs error {resp.Error.Code}: {resp.Error.Message}");

            return resp?.Result;
        }
    }
}

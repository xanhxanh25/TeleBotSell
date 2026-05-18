using Flurl;
using Flurl.Http;
using FreeSql;
using System.Threading.Channels;
using TokenPay.Domains;
using TokenPay.Extensions;
using TokenPay.Helper;
using TokenPay.Models.EthModel;

namespace TokenPay.BgServices
{
    public class OrderCheckEVMBaseService : BaseScheduledService
    {
        private readonly IConfiguration _configuration;
        private readonly IHostEnvironment _env;
        private readonly Channel<TokenOrders> _channel;
        private readonly List<EVMChain> _chains;
        private readonly IFreeSql freeSql;

        private bool UseDynamicAddress => _configuration.GetValue("UseDynamicAddress", true);
        private bool UseDynamicAddressAmountMove => _configuration.GetValue("DynamicAddressConfig:AmountMove", false);

        public OrderCheckEVMBaseService(
            ILogger<OrderCheckEVMBaseService> logger,
            IConfiguration configuration,
            IHostEnvironment env,
            Channel<TokenOrders> channel,
            List<EVMChain> Chains,
            IFreeSql freeSql
        ) : base("Kiểm tra đơn hàng coin gốc EVM", TimeSpan.FromSeconds(15), logger) // "EVM基本币订单检测"
        {
            this._configuration = configuration;
            this._env = env;
            this._channel = channel;
            _chains = Chains;
            this.freeSql = freeSql;
        }

        protected override async Task ExecuteAsync(DateTime RunTime, CancellationToken stoppingToken)
        {
            var _repository = freeSql.GetRepository<TokenOrders>();

            foreach (var chain in _chains)
            {
                if (chain == null || !chain.Enable) continue;

                var Currency = $"EVM_{chain.ChainNameEN}_{chain.BaseCoin}";
                try
                {
                    var Address = await _repository
                        .Where(x => x.Status == OrderStatus.Pending)
                        .Where(x => x.Currency == Currency)
                        .Distinct()
                        .ToListAsync(x => x.ToAddress);

                    var BaseUrl = chain.ApiHost ?? "https://api.etherscan.io/v2/";

                    foreach (var address in Address)
                    {
                        // Truy vấn các đơn hàng đang chờ thanh toán của địa chỉ này
                        var orders = await _repository
                            .Where(x => x.Status == OrderStatus.Pending)
                            .Where(x => x.Currency == Currency)
                            .Where(x => x.ToAddress == address)
                            .OrderBy(x => x.CreateTime)
                            .ToListAsync();

                        if (!orders.Any())
                        {
                            continue;
                        }

                        #region Truy vấn số block mới nhất
                        var queryBlockNumber = new Dictionary<string, object>
                        {
                            { "chainid", chain.ChainId },
                            { "module", "proxy" },
                            { "action", "eth_blockNumber" }
                        };
                        // if (_env.IsProduction())
                        if (!string.IsNullOrEmpty(chain.ApiKey))
                            queryBlockNumber.Add("apikey", chain.ApiKey);

                        var reqBlockNumber = BaseUrl
                            .AppendPathSegment($"api")
                            .SetQueryParams(queryBlockNumber)
                            .WithTimeout(15);

                        var resultBlockNumber = await reqBlockNumber
                            .GetJsonAsync<BaseResponse<string>>();

                        var NowBlockNumber = 0;
                        try
                        {
                            NowBlockNumber = Convert.ToInt32(resultBlockNumber.Result, 16);
                        }
                        catch (Exception e)
                        {
                            _logger.LogError(e, "{coin} truy vấn số block mới nhất thất bại, trả về: {result}", Currency, resultBlockNumber?.Result);
                        }
                        #endregion

                        #region Kiểm tra khớp đơn hàng
                        Func<EthTransaction, Task> CheckOrder = async (EthTransaction item) =>
                        {
                            var RealAmount = item.RealAmount(chain.Decimals);

                            var order = orders
                                .Where(x => x.Amount == RealAmount && x.ToAddress.ToLower() == item.To.ToLower() && x.CreateTime < item.DateTime)
                                .OrderByDescending(x => x.CreateTime) // Ưu tiên khớp với đơn tạo sau cùng
                                .FirstOrDefault();

                        recheck:
                            if (order != null)
                            {
                                order.FromAddress = item.From;
                                order.BlockTransactionId = item.Hash;
                                order.Status = OrderStatus.Paid;
                                order.PayTime = item.DateTime;
                                order.PayAmount = RealAmount;

                                await _repository.UpdateAsync(order);

                                orders.Remove(order);
                                await SendAdminMessage(order);
                            }
                            else
                            {
                                if (UseDynamicAddress && UseDynamicAddressAmountMove)
                                {
                                    // Cho phép thanh toán lệch so với số tiền chính xác
                                    var Move = _configuration.GetSection($"DynamicAddressConfig:{chain.BaseCoin}").Get<decimal[]>() ?? [];
                                    if (Move.Length == 2)
                                    {
                                        var Down = Move[0]; // Mức lệch xuống
                                        var Up = Move[1];   // Mức lệch lên

                                        order = orders
                                            .Where(x => RealAmount >= x.Amount - Down && RealAmount <= x.Amount + Up)
                                            .Where(x => x.ToAddress.ToLower() == item.To.ToLower() && x.CreateTime < item.DateTime)
                                            .OrderByDescending(x => x.CreateTime) // Ưu tiên khớp với đơn tạo sau cùng
                                            .FirstOrDefault();

                                        if (order != null)
                                        {
                                            order.IsDynamicAmount = true;
                                            goto recheck;
                                        }
                                    }
                                }
                            }
                        };
                        #endregion

                        #region Giao dịch ngoài (External Transactions)
                        var query = new Dictionary<string, object>
                        {
                            { "chainid", chain.ChainId },
                            { "module", "account" },
                            { "action", "txlist" },
                            { "address", address },
                            { "page", 1 },
                            { "offset", 100 },
                            { "sort", "desc" }
                        };
                        if (_env.IsProduction())
                            query.Add("apikey", chain.ApiKey);

                        var req = BaseUrl
                            .AppendPathSegment($"api")
                            .SetQueryParams(query)
                            .WithTimeout(15);

                        var result = await req
                            .GetJsonAsync<BaseResponseList<EthTransaction>>();

                        if (result.Status == "1" && result.Result?.Count > 0)
                        {
                            foreach (var item in result.Result)
                            {
                                // Không còn đơn nào cần khớp nữa
                                if (!orders.Any())
                                {
                                    break;
                                }

                                // Giao dịch này đã được dùng để khớp cho đơn khác
                                if (await _repository.Select.AnyAsync(x => x.BlockTransactionId == item.Hash))
                                {
                                    continue;
                                }

                                // Kiểm tra: có phải giao dịch chuyển coin gốc không (không phải contract), method id đúng,
                                // không lỗi, và đủ số confirmations
                                if (!string.IsNullOrEmpty(item.ContractAddress) || item.MethodId != "0x"
                                    || item.IsError != 0 || item.Confirmations < chain.Confirmations)
                                {
                                    continue;
                                }

                                await CheckOrder(item);
                            }
                        }
                        #endregion

                        #region Giao dịch nội bộ (Internal Transactions)
                        var queryInternal = new Dictionary<string, object>
                        {
                            { "chainid", chain.ChainId },
                            { "module", "account" },
                            { "action", "txlistinternal" },
                            { "address", address },
                            { "page", 1 },
                            { "offset", 100 },
                            { "sort", "desc" }
                        };
                        if (_env.IsProduction())
                            queryInternal.Add("apikey", chain.ApiKey);

                        var reqInternal = BaseUrl
                            .AppendPathSegment($"api")
                            .SetQueryParams(queryInternal)
                            .WithTimeout(15);

                        var resultInternal = await reqInternal
                            .GetJsonAsync<BaseResponseList<EthTransaction>>();

                        if (resultInternal.Status == "1" && resultInternal.Result?.Count > 0)
                        {
                            foreach (var item in resultInternal.Result)
                            {
                                // Không còn đơn nào cần khớp nữa
                                if (!orders.Any())
                                {
                                    break;
                                }

                                // Giao dịch này đã được dùng để khớp cho đơn khác
                                if (await _repository.Select.AnyAsync(x => x.BlockTransactionId == item.Hash))
                                {
                                    continue;
                                }

                                // Kiểm tra: không phải contract, không lỗi, và đủ số confirmations theo block hiện tại
                                if (!string.IsNullOrEmpty(item.ContractAddress) || item.IsError != 0
                                    || (NowBlockNumber - item.BlockNumber) < chain.Confirmations)
                                {
                                    continue;
                                }

                                await CheckOrder(item);
                            }
                        }
                        #endregion
                    }
                }
                catch (Exception e)
                {
                    _logger.LogError(e, "{coin} truy vấn lịch sử giao dịch bị lỗi!", Currency); // "{coin}查询交易记录出错！"
                }
            }
        }

        private async Task SendAdminMessage(TokenOrders order)
        {
            await _channel.Writer.WriteAsync(order);
        }
    }
}

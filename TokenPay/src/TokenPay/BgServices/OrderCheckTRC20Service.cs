using Flurl;
using Flurl.Http;
using FreeSql;
using System.Threading.Channels;
using TokenPay.Domains;
using TokenPay.Extensions;
using TokenPay.Helper;
using TokenPay.Models.TronModel;

namespace TokenPay.BgServices
{
    public class OrderCheckTRC20Service : BaseScheduledService
    {
        private readonly IConfiguration _configuration;
        private readonly IHostEnvironment _env;
        private readonly Channel<TokenOrders> _channel;
        private readonly IFreeSql freeSql;

        private bool UseDynamicAddress => _configuration.GetValue("UseDynamicAddress", true);
        private bool UseDynamicAddressAmountMove => _configuration.GetValue("DynamicAddressConfig:AmountMove", false);

        public OrderCheckTRC20Service(
            ILogger<OrderCheckTRC20Service> logger,
            IConfiguration configuration,
            IHostEnvironment env,
            Channel<TokenOrders> channel,
            IFreeSql freeSql
        ) : base("Kiểm tra đơn hàng TRC20", TimeSpan.FromSeconds(3), logger) // TRC20订单检测
        {
            this._configuration = configuration;
            this._env = env;
            this._channel = channel;
            this.freeSql = freeSql;
        }

        protected override async Task ExecuteAsync(DateTime RunTime, CancellationToken stoppingToken)
        {
            var _repository = freeSql.GetRepository<TokenOrders>();
            var _TokensRepository = freeSql.GetRepository<Tokens>();

            var Address = await _repository
                .Where(x => x.Status == OrderStatus.Pending)
                .Where(x => x.Currency == "USDT_TRC20")
                .Distinct()
                .ToListAsync(x => x.ToAddress);

            var ContractAddress = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t";
            var BaseUrl = _configuration.GetValue("TronApiHost", "https://api.trongrid.io");

            if (!_env.IsProduction())
            {
                ContractAddress = "TX8ZUpucJYgHb8wBFQYuYSJ459og32AHWW";
                BaseUrl = "https://api.shasta.trongrid.io";
            }

            var OnlyConfirmed = _configuration.GetValue("OnlyConfirmed", true);
            var start = DateTime.Now.AddMinutes(-10);

            if (!Address.Any())
            {
                return; // Không có địa chỉ nào cần kiểm tra
            }

            _logger.LogDebug("Bắt đầu kiểm tra {Count} địa chỉ cho USDT-TRC20, OnlyConfirmed={OnlyConfirmed}", Address.Count, OnlyConfirmed);

            foreach (var address in Address)
            {
                // Truy vấn các đơn hàng đang chờ thanh toán của địa chỉ này
                var orders = await _repository
                    .Where(x => x.Status == OrderStatus.Pending)
                    .Where(x => x.Currency == "USDT_TRC20")
                    .Where(x => x.ToAddress == address)
                    .OrderBy(x => x.CreateTime)
                    .ToListAsync();

                if (!orders.Any())
                {
                    continue;
                }

                _logger.LogDebug("Địa chỉ {Address} có {Count} orders đang chờ thanh toán USDT-TRC20", address, orders.Count);

                var query = new Dictionary<string, object>();
                if (OnlyConfirmed)
                {
                    query.Add("only_confirmed", true);
                }

                query.Add("only_to", true);
                query.Add("limit", 50);
                query.Add("min_timestamp", start.ToUnixTimeStamp());
                query.Add("contract_address", ContractAddress);

                var req = BaseUrl
                    .AppendPathSegment($"v1/accounts/{address}/transactions/trc20")
                    .SetQueryParams(query)
                    .WithTimeout(15);

                if (_env.IsProduction())
                    req = req.WithHeader("TRON-PRO-API-KEY", _configuration.GetValue<string>("TRON-PRO-API-KEY"));

                BaseResponse<TronTransaction>? result = null;
                try
                {
                    result = await req.GetJsonAsync<BaseResponse<TronTransaction>>();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Lỗi khi truy vấn giao dịch TRC20 cho địa chỉ {Address}", address);
                    continue;
                }

                if (!result.Success)
                {
                    _logger.LogWarning("Lỗi khi truy vấn giao dịch TRC20 cho địa chỉ {Address}: API trả về Success = false", address);
                    continue;
                }

                if (result.Data == null || result.Data.Count == 0)
                {
                    _logger.LogDebug("Không tìm thấy giao dịch TRC20 nào cho địa chỉ {Address} trong {Minutes} phút qua", address, 10);
                    continue;
                }

                _logger.LogDebug("Tìm thấy {Count} giao dịch TRC20 cho địa chỉ {Address}", result.Data.Count, address);
                
                foreach (var item in result.Data)
                {
                    // Địa chỉ hợp đồng không khớp
                    if (item.TokenInfo?.Address != ContractAddress)
                    {
                        _logger.LogDebug("Bỏ qua giao dịch {TxId} vì contract address không khớp: {ContractAddress} != {ExpectedContractAddress}", 
                            item.TransactionId, item.TokenInfo?.Address, ContractAddress);
                        continue;
                    }

                    var types = new string[] { "Transfer", "TransferFrom" };

                    // Địa chỉ nhận (to) phải đúng và loại giao dịch phải phù hợp
                    if (item.To != address)
                    {
                        _logger.LogDebug("Bỏ qua giao dịch {TxId} vì địa chỉ nhận không khớp: {To} != {ExpectedAddress}", 
                            item.TransactionId, item.To, address);
                        continue;
                    }

                    if (!types.Contains(item.Type))
                    {
                        _logger.LogDebug("Bỏ qua giao dịch {TxId} vì type không phù hợp: {Type}", item.TransactionId, item.Type);
                        continue;
                    }

                    // Không còn đơn nào cần khớp nữa
                    if (!orders.Any())
                    {
                        break;
                    }

                    // Giao dịch này đã được dùng để khớp cho đơn khác
                    if (await _repository.Select.AnyAsync(x => x.BlockTransactionId == item.TransactionId))
                    {
                        _logger.LogDebug("Giao dịch {TxId} đã được sử dụng để khớp cho đơn khác", item.TransactionId);
                        continue;
                    }

                    var tokenList = await _TokensRepository
                        .Where(x => x.Currency == TokenCurrency.TRX && x.Address == item.To)
                        .ToListAsync();
                    
                    var token = tokenList.FirstOrDefault();
                    if (token != null)
                    {
                        token.USDT += item.Amount;
                        await _TokensRepository.UpdateAsync(token);
                    }

                    // item.Amount đã là decimal (đã được tính từ Value / 1_000_000)
                    var transactionAmount = item.Amount;

                    // Khớp order với số tiền (cho phép sai lệch nhỏ do làm tròn, ví dụ 0.0001)
                    var order = orders
                        .Where(x => Math.Abs(x.Amount - transactionAmount) < 0.0001m && x.ToAddress == item.To && x.CreateTime < item.BlockTimestamp.ToDateTime())
                        .OrderByDescending(x => x.CreateTime) // Ưu tiên khớp với đơn tạo sau cùng
                        .FirstOrDefault();

                    if (order == null)
                    {
                        _logger.LogInformation("Không tìm thấy order phù hợp cho giao dịch USDT-TRC20: TxId={TxId}, Amount={Amount}, ToAddress={ToAddress}, Có {OrderCount} orders đang chờ. Danh sách orders: {OrderDetails}", 
                            item.TransactionId, transactionAmount, item.To, orders.Count, 
                            string.Join("; ", orders.Select(o => $"OrderId={o.Id}, OutOrderId={o.OutOrderId}, Amount={o.Amount}, CreateTime={o.CreateTime:yyyy-MM-dd HH:mm:ss}")));
                    }

                    recheck:
                    if (order != null)
                    {
                        order.FromAddress = item.From;
                        order.BlockTransactionId = item.TransactionId;
                        order.Status = OrderStatus.Paid;
                        order.PayTime = item.BlockTimestamp.ToDateTime();
                        order.PayAmount = transactionAmount;

                        await _repository.UpdateAsync(order);
                        orders.Remove(order);
                        
                        _logger.LogInformation("Đã khớp thành công order USDT-TRC20: OrderId={OrderId}, OutOrderId={OutOrderId}, TxId={TxId}, Amount={Amount}, PayAmount={PayAmount}", 
                            order.Id, order.OutOrderId, item.TransactionId, order.Amount, order.PayAmount);
                        
                        await SendAdminMessage(order);
                        
                        // Kiểm tra nếu có NotifyUrl để gửi notification
                        if (string.IsNullOrEmpty(order.NotifyUrl))
                        {
                            _logger.LogWarning("Order {OrderId} đã thanh toán thành công nhưng không có NotifyUrl để gửi notification!", order.Id);
                        }
                        else
                        {
                            _logger.LogInformation("Order {OrderId} sẽ được gửi notification đến: {NotifyUrl}", order.Id, order.NotifyUrl);
                        }
                    }
                    else
                    {
                        if (UseDynamicAddress && UseDynamicAddressAmountMove)
                        {
                            // Cho phép thanh toán lệch so với số tiền chính xác
                            var Move = _configuration.GetSection("DynamicAddressConfig:USDT").Get<decimal[]>() ?? [];
                            if (Move.Length == 2)
                            {
                                var Down = Move[0]; // Mức lệch xuống
                                var Up = Move[1];   // Mức lệch lên

                                order = orders
                                    .Where(x => transactionAmount >= x.Amount - Down && transactionAmount <= x.Amount + Up)
                                    .Where(x => x.ToAddress == item.To && x.CreateTime < item.BlockTimestamp.ToDateTime())
                                    .OrderByDescending(x => x.CreateTime) // Ưu tiên khớp với đơn tạo sau cùng
                                    .FirstOrDefault();

                                if (order != null)
                                {
                                    _logger.LogInformation("Tìm thấy order với dynamic amount: OrderId={OrderId}, OrderAmount={OrderAmount}, PayAmount={PayAmount}, MoveDown={Down}, MoveUp={Up}", 
                                        order.Id, order.Amount, transactionAmount, Down, Up);
                                    order.IsDynamicAmount = true;
                                    goto recheck;
                                }
                                else
                                {
                                    _logger.LogDebug("Không tìm thấy order với dynamic amount move cho giao dịch {TxId}, Amount={Amount}, MoveDown={Down}, MoveUp={Up}", 
                                        item.TransactionId, transactionAmount, Down, Up);
                                }
                            }
                        }
                    }
                }
            }
        }

        private async Task SendAdminMessage(TokenOrders order)
        {
            await _channel.Writer.WriteAsync(order);
        }
    }
}

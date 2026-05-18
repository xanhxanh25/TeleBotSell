using System.Threading.Channels;
using TokenPay.Domains;
using TokenPay.Extensions;
using TokenPay.Helper;
using TokenPay.Models.EthModel;

namespace TokenPay.BgServices
{
    public class OrderPaySuccessService : BaseBackgroundService
    {
        private readonly Channel<TokenOrders> _channel;
        private readonly IHostEnvironment _env;
        private readonly TelegramBot _bot;
        private readonly List<EVMChain> _chain;
        private readonly IConfiguration _configuration;

        public OrderPaySuccessService(
            Channel<TokenOrders> channel,
            IHostEnvironment env,
            TelegramBot bot,
            List<EVMChain> chain,
            IConfiguration configuration,
            ILogger<OrderPaySuccessService> logger
        ) : base("Gửi thông báo đơn hàng", logger) // 发送订单通知
        {
            this._channel = channel;
            this._env = env;
            this._bot = bot;
            this._chain = chain;
            this._configuration = configuration;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested && await _channel.Reader.WaitToReadAsync(stoppingToken))
            {
                while (!stoppingToken.IsCancellationRequested && _channel.Reader.TryRead(out var item))
                {
                    try
                    {
                        await SendAdminMessage(item, stoppingToken);
                    }
                    catch (Exception e)
                    {
                        _logger.LogError(e, "Gửi thông báo đơn hàng mới thất bại!");
                    }
                }
            }
        }

        private async Task SendAdminMessage(TokenOrders order, CancellationToken? cancellationToken = null)
        {
            // Tiền tệ mặc định
            var BaseCurrency = _configuration.GetValue<string>("BaseCurrency", "CNY");

            foreach (var item in _chain.Select(x => x.ERC20Name).ToArray())
            {
                order.Currency = order.Currency.Replace(item, "");
            }

            var curreny = order.Currency
                .Replace("TRC20", "")
                .Split("_", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Last();

            var message = @$"<b>Bạn có đơn hàng mới! ({order.ActualAmount} {BaseCurrency})</b>

Mã đơn hàng: <code>{order.OutOrderId}</code>
Số tiền gốc: <b>{order.ActualAmount} {BaseCurrency}</b>
Số tiền đơn hàng: <b>{order.Amount} {curreny}</b>
Số tiền đã thanh toán: <b>{order.PayAmount} {curreny}</b>{(order.IsDynamicAmount ? " (đơn hàng số tiền động)" : "")}
Địa chỉ thanh toán: <code>{order.FromAddress}</code>
Địa chỉ nhận tiền: <code>{order.ToAddress}</code>
Thời gian tạo: <b>{order.CreateTime:yyyy-MM-dd HH:mm:ss}</b>
Thời gian thanh toán: <b>{order.PayTime:yyyy-MM-dd HH:mm:ss}</b>
TxHash: <code>{order.BlockTransactionId}</code>";

            if (order.Currency.Contains("TRX") || order.Currency.Contains("TRC20"))
            {
                if (_env.IsProduction())
                {
                    message += @$"  <b><a href=""https://tronscan.org/#/transaction/{order.BlockTransactionId}?lang=en"">View transaction</a></b>";
                }
                else
                {
                    message += @$"  <b><a href=""https://shasta.tronscan.org/#/transaction/{order.BlockTransactionId}?lang=en"">View transaction</a></b>";
                }
            }
            else if (order.Currency.StartsWith("EVM"))
            {
                foreach (var chain in _chain)
                {
                    if (order.Currency.StartsWith($"EVM_{chain.ChainNameEN}"))
                    {
                        if (!string.IsNullOrEmpty(chain.ScanHost))
                            message += @$"  <b><a href=""{chain.ScanHost}/tx/{order.BlockTransactionId}"">View transaction</a></b>";
                        break;
                    }
                }
            }

            await _bot.SendTextMessageAsync(message, cancellationToken: cancellationToken);
        }
    }
}

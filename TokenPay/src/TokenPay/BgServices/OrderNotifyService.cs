using Flurl.Http;
using FreeSql;
using System.Net;
using TokenPay.Domains;
using TokenPay.Extensions;

namespace TokenPay.BgServices
{
    public class OrderNotifyService : BaseScheduledService
    {
        private readonly IConfiguration _configuration;
        private readonly IFreeSql freeSql;
        private readonly FlurlClient client;

        public OrderNotifyService(
            ILogger<OrderNotifyService> logger,
            IConfiguration configuration,
            IFreeSql freeSql
        ) : base("Thông báo đơn hàng", TimeSpan.FromSeconds(1), logger) // 订单通知
        {
            this._configuration = configuration;
            this.freeSql = freeSql;

            client = new FlurlClient();
            client.Settings.Timeout = TimeSpan.FromSeconds(configuration.GetValue("NotifyTimeOut", 3));

            client.BeforeCall(c =>
            {
                c.Request.WithHeader(
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 TokenPay/1.0"
                );

                _logger.LogInformation("Gửi request\nURL: {url}\nDữ liệu: {body}", c.Request.Url, c.RequestBody); // 发起请求...
            });

            client.AfterCall(async c =>
            {
                if (c.Response != null)
                {
                    _logger.LogInformation("Nhận response\nURL: {url}\nPhản hồi: {@body}",
                        c.Request.Url, await c.Response.GetStringAsync()); // 收到响应...
                }
            });
        }

        protected override async Task ExecuteAsync(DateTime RunTime, CancellationToken stoppingToken)
        {
            var _repository = freeSql.GetRepository<TokenOrders>();
            var start = DateTime.Now.AddMinutes(-1);

            var Orders = await _repository
                .Where(x => x.Status == OrderStatus.Paid)
                .Where(x => !x.CallbackConfirm)
                .Where(x => x.CallbackNum < 3)
                .Where(x => x.LastNotifyTime == null || x.LastNotifyTime < start) // Chưa từng notify, hoặc notify thất bại và đã quá N phút
                .Where(x => x.NotifyUrl!.StartsWith("http"))
                .ToListAsync();

            foreach (var order in Orders)
            {
                _logger.LogInformation("Bắt đầu notify bất đồng bộ cho đơn hàng: {c}", order.Id); // 开始异步通知订单

                order.CallbackNum++;
                order.LastNotifyTime = DateTime.Now;
                await _repository.UpdateAsync(order);

                var result = await Notify(order);

                if (result)
                {
                    order.CallbackConfirm = true;
                    await _repository.UpdateAsync(order);
                }

                _logger.LogInformation("Đơn hàng: {c}, kết quả notify: {d}",
                    order.Id, result ? "Thành công" : "Thất bại"); // 通知结果：成功/失败
            }
        }

        private async Task<bool> Notify(TokenOrders order)
        {
            if (!string.IsNullOrEmpty(order.NotifyUrl))
            {
                try
                {
                    var dic = order.ToDic(_configuration);
                    var SignatureStr = string.Join("&", dic.Select(x => $"{x.Key}={x.Value}"));

                    var ApiToken = _configuration.GetValue<string>("ApiToken");
                    SignatureStr += ApiToken;

                    var Signature = SignatureStr.ToMD5();
                    dic.Add(nameof(Signature), Signature);

                    var result = await client.Request(order.NotifyUrl).PostJsonAsync(dic);
                    var message = await result.GetStringAsync();

                    if (result.StatusCode == 200 && message == "ok")
                    {
                        _logger.LogInformation("Notify bất đồng bộ đơn hàng thành công!\n{msg}", message); // 订单异步通知成功
                        return true;
                    }
                    else
                    {
                        _logger.LogInformation("Notify bất đồng bộ đơn hàng thất bại: {msg}", message); // 订单异步通知失败
                    }
                }
                catch (Exception e)
                {
                    _logger.LogInformation(e, "Notify bất đồng bộ đơn hàng thất bại: {msg}", e.Message); // 订单异步通知失败
                }
            }

            return false;
        }
    }
}

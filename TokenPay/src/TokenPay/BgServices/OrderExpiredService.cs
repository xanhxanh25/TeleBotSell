using FreeSql;
using TokenPay.Domains;

namespace TokenPay.BgServices
{
    public class OrderExpiredService : BaseScheduledService
    {
        private readonly IConfiguration _configuration;
        private readonly IFreeSql freeSql;

        public OrderExpiredService(
            ILogger<OrderExpiredService> logger,
            IConfiguration configuration,
            IFreeSql freeSql
        ) : base("Hết hạn đơn hàng", TimeSpan.FromSeconds(10), logger) // 订单过期
        {
            this._configuration = configuration;
            this.freeSql = freeSql;
        }

        protected override async Task ExecuteAsync(DateTime RunTime, CancellationToken stoppingToken)
        {
            var _repository = freeSql.GetRepository<TokenOrders>();

            var ExpireTime = _configuration.GetValue("ExpireTime", 10 * 60);
            var ExpireDateTime = DateTime.Now.AddSeconds(-1 * ExpireTime);

            var ExpiredOrders = await _repository
                .Where(x => x.CreateTime < ExpireDateTime && x.Status == OrderStatus.Pending)
                .ToListAsync();

            foreach (var order in ExpiredOrders)
            {
                _logger.LogInformation("Đơn hàng [{c}] đã hết hạn!", order.Id); // 订单[{c}]过期了！
                order.Status = OrderStatus.Expired;
                await _repository.UpdateAsync(order);
            }
        }
    }
}

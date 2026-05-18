using System;

namespace TokenPay.BgServices
{
    public abstract class BaseScheduledService : BackgroundService
    {
        protected readonly string jobName;
        private readonly TimeSpan period;
        protected readonly ILogger _logger;
        private PeriodicTimer? _timer;

        protected BaseScheduledService(string JobName, TimeSpan period, ILogger logger)
        {
            _logger = logger;
            jobName = JobName;
            this.period = period;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            _logger.LogInformation("Service {JobName} is starting.", jobName);

            await Task.Delay(3000); // Trì hoãn 3 giây rồi mới bắt đầu chạy tác vụ

            _timer = new PeriodicTimer(period);
            try
            {
                do
                {
                    try
                    {
                        await ExecuteAsync(DateTime.Now, stoppingToken);
                    }
                    catch (Flurl.Http.FlurlHttpException ex) when (ex.StatusCode == 401 || ex.StatusCode == 403)
                    {
                        _logger.LogError(
                            ex,
                            "Tác vụ định kỳ [{jobName}] gặp lỗi khi gọi API, mã trả về: {code}. " +
                            "Thường do lỗi xác thực API hoặc vượt quá giới hạn số lần gọi.",
                            jobName,
                            ex.StatusCode
                        );
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, $"Tác vụ định kỳ [{jobName}] gặp lỗi trong quá trình thực thi");
                    }
                } while (!stoppingToken.IsCancellationRequested && await _timer.WaitForNextTickAsync(stoppingToken));
            }
            catch (OperationCanceledException)
            {
                _logger.LogInformation("Service {JobName} đã bị hủy.", jobName);
            }
        }

        protected abstract Task ExecuteAsync(DateTime RunTime, CancellationToken stoppingToken);

        public override Task StopAsync(CancellationToken cancellationToken)
        {
            _logger.LogInformation("Service {JobName} is stopping.", jobName);
            _timer?.Dispose();
            return base.StopAsync(cancellationToken);
        }
    }
}

using Flurl;
using Flurl.Http;
using FreeSql;
using HDWallet.Tron;
using Nethereum.Signer;
using Org.BouncyCastle.Asn1.X509;
using System.Collections.Generic;
using TokenPay.Domains;
using TokenPay.Extensions;
using TokenPay.Helper;
using TokenPay.Models.EthModel;

namespace TokenPay.BgServices
{
    public class CollectionTRONService : BaseScheduledService
    {
        private readonly IConfiguration _configuration;
        private readonly TelegramBot _bot;
        private readonly IFreeSql freeSql;

        /// <summary>
        /// Có bật chức năng gom (collection) hay không
        /// </summary>
        private bool Enable => _configuration.GetValue("Collection:Enable", false);

        /// <summary>
        /// Có bật thuê năng lượng (Energy) hay không
        /// </summary>
        private bool UseEnergy => _configuration.GetValue("Collection:UseEnergy", true);

        /// <summary>
        /// Mỗi lần gom sẽ bắt buộc kiểm tra số dư tất cả địa chỉ
        /// </summary>
        private bool ForceCheckAllAddress => _configuration.GetValue("Collection:ForceCheckAllAddress", false);

        /// <summary>
        /// Có giữ lại 0.000001 USDT hay không
        /// </summary>
        private bool RetainUSDT => _configuration.GetValue("Collection:RetainUSDT", true);

        /// <summary>
        /// Mức USDT tối thiểu để gom
        /// </summary>
        private decimal MinUSDT => _configuration.GetValue("Collection:MinUSDT", 0.1m);

        /// <summary>
        /// Số năng lượng tiêu hao (vui lòng không chỉnh)
        /// </summary>
        private long DefaultNeedEnergy => _configuration.GetValue("Collection:NeedEnergy", 64285);

        /// <summary>
        /// Mức năng lượng tối thiểu khi thuê (vui lòng không chỉnh)
        /// </summary>
        private long EnergyMinValue => _configuration.GetValue("Collection:EnergyMinValue", 64400);

        /// <summary>
        /// Đơn giá năng lượng hiện tại (vui lòng không chỉnh)
        /// </summary>
        private decimal EnergyPrice => _configuration.GetValue("Collection:EnergyPrice", 210m);

        /// <summary>
        /// Thời lượng thuê năng lượng (vui lòng không chỉnh)
        /// </summary>
        private int RentDuration => _configuration.GetValue("Collection:RentDuration", 10);

        /// <summary>
        /// Đơn vị thời lượng thuê năng lượng (vui lòng không chỉnh)
        /// </summary>
        private string RentTimeUnit => _configuration.GetValue("Collection:RentTimeUnit", "m")!;

        /// <summary>
        /// Địa chỉ nhận gom (địa chỉ đích)
        /// </summary>
        private string Address => _configuration.GetValue<string>("Collection:Address")!;

        private int CheckTime => _configuration.GetValue("Collection:CheckTime", 3);

        /// <summary>
        /// Ước tính TRX tiêu hao cho băng thông (Bandwidth)
        /// </summary>
        private decimal NetUsedTrx => 0.3m;

        private EnergyApi energyApi => new EnergyApi(_logger, _configuration);

        public CollectionTRONService(
            IConfiguration configuration,
            TelegramBot bot,
            IFreeSql freeSql,
            ILogger<CollectionTRONService> logger
        ) : base("Tác vụ gom TRON", TimeSpan.FromHours(configuration.GetValue("Collection:CheckTime", 1)), logger)
        {
            this._configuration = configuration;
            this._bot = bot;
            this.freeSql = freeSql;
        }

        protected override async Task ExecuteAsync(DateTime RunTime, CancellationToken stoppingToken)
        {
            if (!Enable) return;

            var SendToTelegram = false;

            if (!File.Exists("手续费钱包私钥.txt"))
            {
                var ecKey = Nethereum.Signer.EthECKey.GenerateKey();
                var rawPrivateKey = ecKey.GetPrivateKeyAsBytes();
                var hex = Convert.ToHexString(rawPrivateKey);
                File.WriteAllText("手续费钱包私钥.txt", hex);
                SendToTelegram = true;
            }

            var privateKey = File.ReadAllText("手续费钱包私钥.txt");
            var mainWallet = new TronWallet(privateKey);

            _logger.LogInformation("Địa chỉ ví phí (fee wallet) là: {a}", mainWallet.Address);

            if (SendToTelegram)
            {
                await _bot.SendTextMessageAsync(@$"<b>Tạo ví phí</b>

Địa chỉ ví phí: <code>{mainWallet.Address}</code>
Private key ví phí: <tg-spoiler>
{privateKey.Substring(0, 32)}
{privateKey.Substring(32, 32)}
</tg-spoiler>
Không cần thiết thì đừng sao chép private key này!!!
Để tránh bị đánh cắp, private key đã được tách thành 2 đoạn, hãy sao chép từng đoạn

<b>Hãy nạp TRX vào địa chỉ này để dùng cho việc gom USDT</b>
");
            }

            var mainTrx = await QueryTronAction.GetTRXAsync(mainWallet.Address);
            _logger.LogInformation("Số dư TRX hiện tại của ví phí: {trx}", mainTrx);

            if (mainTrx < 1)
            {
                while (!stoppingToken.IsCancellationRequested && mainTrx < 1)
                {
                    var TrxCheckTime = 10;
                    _logger.LogInformation("Địa chỉ ví phí là: {a}", mainWallet.Address);
                    _logger.LogInformation("Đang chờ nạp TRX vào ví phí...");

                    mainTrx = await QueryTronAction.GetTRXAsync(mainWallet.Address);

                    if (mainTrx > 1)
                        _logger.LogInformation("Nạp xong, số dư TRX hiện tại: {trx}", mainTrx);
                    else
                    {
                        await _bot.SendTextMessageAsync(@$"Ví phí cần được nạp TRX

Địa chỉ ví phí: <code>{mainWallet.Address}</code>
Số dư TRX hiện tại: {mainTrx} TRX


Vui lòng nạp TRX trước, hệ thống sẽ kiểm tra lại sau {TrxCheckTime} giây.

Nếu không cần dùng chức năng gom, hãy đặt <b>Collection:Enable</b> = <b>false</b> trong file cấu hình.");
                    }

                    await Task.Delay(TrxCheckTime * 1000);
                }
            }

            try
            {
                Address.Base58ToHex();
            }
            catch (Exception)
            {
                _logger.LogError("Địa chỉ nhận gom {a} không hợp lệ!", Address);
                await _bot.SendTextMessageAsync(@$"Địa chỉ nhận gom không hợp lệ, vui lòng kiểm tra

Địa chỉ nhận gom: <code>{Address}</code>");
                return;
            }

            var usdt = await QueryTronAction.GetUsdtAmountAsync(Address);
            if (usdt <= 0)
            {
                _logger.LogError("Địa chỉ nhận gom {a} bắt buộc phải có USDT!", Address);
                await _bot.SendTextMessageAsync(@$"Địa chỉ nhận gom bắt buộc phải có USDT

Địa chỉ nhận gom: <code>{Address}</code>");
                return;
            }
            else
            {
                var trx = await QueryTronAction.GetTRXAsync(Address);
                _logger.LogInformation("Địa chỉ nhận gom - Số dư TRX: {trx}, Số dư USDT: {usdt}", trx, usdt);

                await _bot.SendTextMessageAsync(@$"Số dư địa chỉ nhận gom

Địa chỉ nhận gom: <code>{Address}</code>
Số dư TRX hiện tại: {trx} USDT
Số dư USDT hiện tại: {usdt} USDT");
            }

            var _repository = freeSql.GetRepository<Tokens>();
            var list = await _repository
                .Where(x => x.Currency == TokenCurrency.TRX)
                .Where(x => ForceCheckAllAddress || (x.USDT > MinUSDT || x.Value > 0.5m))
                .ToListAsync();

            var count = 0;
            foreach (var item in list)
            {
                if (stoppingToken.IsCancellationRequested) return;

                if (item.LastCheckTime.HasValue && (DateTime.Now - item.LastCheckTime.Value).TotalHours <= 1)
                {
                    // Tránh kiểm tra số dư lặp lại trong thời gian ngắn
                    continue;
                }

                var TRX = await QueryTronAction.GetTRXAsync(item.Address);
                var USDT = await QueryTronAction.GetUsdtAmountAsync(item.Address);

                item.Value = TRX;
                item.USDT = USDT;
                item.LastCheckTime = DateTime.Now;

                await _repository.UpdateAsync(item);

                _logger.LogInformation("Cập nhật dữ liệu số dư: {a}/{b}, TRX: {TRX}, USDT: {USDT}",
                    ++count, list.Count, TRX, USDT);

                await Task.Delay(1500);
            }

            list = await _repository
                .Where(x => x.Currency == TokenCurrency.TRX)
                .Where(x => x.USDT > MinUSDT || x.Value > 0.5m)
                .ToListAsync();

            _logger.LogInformation(
                @"Tổng cộng tìm thấy {count} địa chỉ cần gom; địa chỉ có TRX: {a} (tổng {b} TRX); địa chỉ có USDT: {c} (tổng {d} USDT)",
                list.Count,
                list.Where(x => x.Value > 0.5m).Count(),
                list.Where(x => x.Value > 0.5m).Sum(x => x.Value),
                list.Where(x => x.USDT > MinUSDT).Count(),
                list.Where(x => x.USDT > MinUSDT).Sum(x => x.USDT)
            );

            Func<int, Task<(decimal, string)>> GetPrice = async (int ResourceValue) =>
            {
                var resp = await energyApi.OrderPrice(ResourceValue, RentDuration, RentTimeUnit);
                _logger.LogInformation("Ước tính giá năng lượng: {@result}", resp);

                if (resp != null && resp.Code == 0)
                {
                    var EnergyPayAddress = resp.Data.PayAddress;
                    var EnergyPrice = resp.Data.Price;
                    return (EnergyPrice, EnergyPayAddress);
                }

                _logger.LogError("Ước tính giá năng lượng thất bại!");
                await _bot.SendTextMessageAsync(@$"Ước tính giá năng lượng thất bại!

Số năng lượng: {ResourceValue}");

                return (0, string.Empty);
            };

            _logger.LogInformation("------------------------------");

            if (list.Where(x => x.Value > 0.5m).Any())
                _logger.LogInformation("Bắt đầu gom TRX");
            else
                _logger.LogInformation("Bỏ qua gom TRX");

            foreach (var item in list.Where(x => x.Value > 0.5m))
            {
                if (stoppingToken.IsCancellationRequested) return;

                var wallet = new TronWallet(item.Key);
                var account = await QueryTronAction.GetAccountResourceAsync(wallet.Address);

                if (account.FreeNetLimit - account.FreeNetUsed < 280)
                {
                    continue;
                }

                var (success, txid) = await wallet.TransferTrxAsync(item.Value, Address);
                if (success)
                {
                    _logger.LogInformation("Gom TRX thành công, TRX: {a}, Txid: {b}", item.Value, txid);

                    item.Value = 0;
                    await _repository.UpdateAsync(item);

                    await _bot.SendTextMessageAsync(@$"Gom TRX thành công!

Địa chỉ gom: <code>{item.Address}</code>
Số lượng gom: {item.Value} TRX
TxHash: {txid} <b><a href=""https://tronscan.org/#/transaction/{txid}?lang=zh"">Xem giao dịch</a></b>");
                }
                else
                {
                    _logger.LogWarning("Gom TRX thất bại, lý do: {b}", txid);
                }
            }

            _logger.LogInformation("------------------------------");

            if (list.Where(x => x.USDT > MinUSDT).Any())
                _logger.LogInformation("Bắt đầu gom USDT");
            else
                _logger.LogInformation("Bỏ qua gom USDT");

            foreach (var item in list.Where(x => x.USDT > MinUSDT))
            {
                if (stoppingToken.IsCancellationRequested) return;

                var wallet = new TronWallet(item.Key);
                var account = await QueryTronAction.GetAccountAsync(wallet.Address);

                if (account.CreateTime == 0)
                {
                    _logger.LogInformation("Địa chỉ chưa được kích hoạt, đang kích hoạt: {a}", wallet.Address);

                    if (!await CheckMainWalletTrx(mainWallet, NetUsedTrx))
                    {
                        return;
                    }

                    var (success2, txid3) = await mainWallet.TransferTrxAsync(0.000001m, wallet.Address);
                    if (success2)
                    {
                        _logger.LogInformation("Kích hoạt thành công, địa chỉ: {a}", wallet.Address);
                    }
                    else
                    {
                        _logger.LogWarning("Kích hoạt thất bại, bỏ qua địa chỉ này: {a}", wallet.Address);
                        continue;
                    }
                }

                var NeedEnergy = DefaultNeedEnergy;
                var accountResource = await QueryTronAction.GetAccountResourceAsync(wallet.Address);

                var needNet = accountResource.FreeNetLimit - accountResource.FreeNetUsed < 400;
                var energy = accountResource.EnergyLimit - accountResource.EnergyUsed;

                NeedEnergy -= energy;

                if (NeedEnergy > 0)
                {
                    if (!UseEnergy)
                    {
                        var trx = NeedEnergy * EnergyPrice / 1_000_000;
                        if (needNet)
                        {
                            trx += 0.5m;
                        }

                        var nowTrx = await QueryTronAction.GetTRXAsync(wallet.Address);
                        if (nowTrx < trx)
                        {
                            if (!await CheckMainWalletTrx(mainWallet, trx - nowTrx + NetUsedTrx))
                            {
                                return;
                            }

                            var (success2, txid3) = await mainWallet.TransferTrxAsync(trx - nowTrx, wallet.Address);
                            if (success2)
                            {
                                _logger.LogInformation("Chuyển phí giao dịch thành công, địa chỉ: {a}", wallet.Address);
                            }
                            else
                            {
                                _logger.LogWarning("Chuyển phí giao dịch thất bại, bỏ qua địa chỉ: {a}", wallet.Address);
                                continue;
                            }
                        }
                    }
                    else
                    {
                        if (needNet)
                        {
                            var trx = 0.5m;
                            var nowTrx = await QueryTronAction.GetTRXAsync(wallet.Address);

                            if (nowTrx < trx)
                            {
                                if (!await CheckMainWalletTrx(mainWallet, trx + NetUsedTrx))
                                {
                                    return;
                                }

                                var (success2, txid3) = await mainWallet.TransferTrxAsync(trx - nowTrx, wallet.Address);
                                if (success2)
                                {
                                    _logger.LogInformation("Chuyển phí giao dịch thành công, địa chỉ: {a}", wallet.Address);
                                }
                                else
                                {
                                    _logger.LogWarning("Chuyển phí giao dịch thất bại, bỏ qua địa chỉ: {a}", wallet.Address);
                                    continue;
                                }
                            }
                        }

                        if (NeedEnergy < EnergyMinValue)
                        {
                            NeedEnergy = EnergyMinValue;
                        }

                        var (amountTrx, PaymentAddress) = await GetPrice((int)NeedEnergy);
                        if (amountTrx == 0)
                        {
                            _logger.LogWarning("Ước tính giá năng lượng thất bại! Năng lượng: {a}", NeedEnergy);
                            continue;
                        }

                        if (!await CheckMainWalletTrx(mainWallet, amountTrx + NetUsedTrx))
                        {
                            return;
                        }

                        var (success3, msg, txn) = await QueryTronAction.GetTransferTrxSignedTxnToJobjectAsync(
                            mainWallet.Address,
                            privateKey,
                            amountTrx,
                            PaymentAddress
                        );

                        if (success3)
                        {
                            var CreateModel = new CreateOrderModel
                            {
                                PayAddress = mainWallet.Address,
                                PayAmount = amountTrx,
                                ReceiveAddress = wallet.Address,
                                RentDuration = RentDuration,
                                RentTimeUnit = RentTimeUnit,
                                ResourceValue = (int)NeedEnergy,
                                SignedTxn = txn!
                            };

                            var feeResult = await energyApi.CreateOrder(CreateModel);
                            if (feeResult.Code == 0)
                            {
                                var count2 = 0;
                                await Task.Delay(3000);

                                while (!stoppingToken.IsCancellationRequested && count2 < 30)
                                {
                                    try
                                    {
                                        var feeResult2 = await energyApi.OrderQuery(feeResult.Data.OrderNo);
                                        if (feeResult2.Code == 0)
                                        {
                                            if (feeResult2.Data.Status == FeeeOrderStatus.已质押)
                                            {
                                                count = 30;
                                                count2 = 30;

                                                var count3 = 0;
                                                while (!stoppingToken.IsCancellationRequested && count3 < 5)
                                                {
                                                    try
                                                    {
                                                        accountResource = await QueryTronAction.GetAccountResourceAsync(wallet.Address);
                                                        energy = accountResource.EnergyLimit - accountResource.EnergyUsed;

                                                        if (energy >= DefaultNeedEnergy)
                                                        {
                                                            count3 = 5;
                                                            _logger.LogInformation("Thuê năng lượng thành công, năng lượng hiện tại: {e}, địa chỉ: {a}", energy, wallet.Address);
                                                            break;
                                                        }
                                                    }
                                                    catch (Exception)
                                                    {
                                                    }
                                                    finally
                                                    {
                                                        if (count3 < 5)
                                                            await Task.Delay(3000);
                                                        count3++;
                                                    }
                                                }
                                            }
                                        }
                                        else
                                        {
                                            _logger.LogWarning("Không truy vấn được thông tin đơn thuê năng lượng, lý do: {msg}", feeResult2.Msg);
                                            continue;
                                        }
                                    }
                                    catch (Exception e)
                                    {
                                        _logger.LogWarning("Không truy vấn được thông tin đơn thuê năng lượng, lý do: {msg}", e.Message);
                                        continue;
                                    }
                                    finally
                                    {
                                        if (count2 < 30)
                                            await Task.Delay(1000 * 3);
                                        count2++;
                                    }
                                }
                            }
                            else
                            {
                                CreateModel.SignedTxn = new object();
                                _logger.LogWarning("Gom USDT thất bại do thuê năng lượng thất bại, lý do: {msg}\nTham số request: {@CreateModel}", feeResult.Msg, CreateModel);
                                continue;
                            }
                        }
                        else
                        {
                            _logger.LogWarning("Gom USDT thất bại, lý do: {b}", "Thuê năng lượng thất bại! " + msg);
                            continue;
                        }
                    }
                }
                else
                {
                    if (needNet)
                    {
                        var trx = 0.5m;
                        var nowTrx = await QueryTronAction.GetTRXAsync(wallet.Address);

                        if (nowTrx < trx)
                        {
                            if (!await CheckMainWalletTrx(mainWallet, trx - nowTrx + NetUsedTrx))
                            {
                                return;
                            }

                            var (success2, txid3) = await mainWallet.TransferTrxAsync(trx - nowTrx, wallet.Address);
                            if (success2)
                            {
                                _logger.LogInformation("Chuyển phí giao dịch thành công, địa chỉ: {a}", wallet.Address);
                            }
                            else
                            {
                                _logger.LogWarning("Chuyển phí giao dịch thất bại, bỏ qua địa chỉ: {a}", wallet.Address);
                                continue;
                            }
                        }
                    }
                }

                var RetainUSDTAmount = RetainUSDT ? 0.000001m : 0;
                var (success, txid) = await wallet.TransferUSDTAsync(item.USDT - RetainUSDTAmount, Address);

                if (success)
                {
                    _logger.LogInformation("Gom USDT thành công, USDT: {a}, Txid: {b}", item.USDT - RetainUSDTAmount, txid);

                    await _bot.SendTextMessageAsync(@$"Gom USDT thành công!

Địa chỉ gom: <code>{item.Address}</code>
Số lượng gom: {item.USDT - RetainUSDTAmount} USDT
TxHash: {txid} <b><a href=""https://tronscan.org/#/transaction/{txid}?lang=zh"">Xem giao dịch</a></b>");

                    item.USDT = 0;
                    await _repository.UpdateAsync(item);
                }
                else
                {
                    _logger.LogWarning("Gom USDT thất bại, lý do: {b}", txid);
                }
            }
        }

        /// <summary>
        /// Kiểm tra số dư TRX của ví phí có đủ hay không
        /// </summary>
        /// <param name="mainWallet"></param>
        /// <param name="minTrx"></param>
        /// <returns></returns>
        private async Task<bool> CheckMainWalletTrx(TronWallet mainWallet, decimal minTrx)
        {
            var mainTrx = await QueryTronAction.GetTRXAsync(mainWallet.Address);
            if (mainTrx < minTrx)
            {
                _logger.LogWarning("TRX của ví phí không đủ! Cần: {minTrx}, Hiện tại: {mainTrx}", minTrx, mainTrx);

                await _bot.SendTextMessageAsync(@$"TRX ví phí không đủ, không thể tiếp tục tác vụ gom!

Địa chỉ ví phí: <code>{mainWallet.Address}</code>
Số dư TRX hiện tại: {mainTrx} TRX


Vui lòng nạp TRX trước, tác vụ gom sẽ thử lại sau {CheckTime} giờ.");
                return false;
            }
            return true;
        }
    }
}

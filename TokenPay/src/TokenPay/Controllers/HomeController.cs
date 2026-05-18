using FreeSql;
using HDWallet.Tron;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using Org.BouncyCastle.Bcpg;
using SkiaSharp;
using SkiaSharp.QrCode.Image;
using System.Diagnostics;
using System.Reflection;
using TokenPay.Domains;
using TokenPay.Extensions;
using TokenPay.Helper;
using TokenPay.Models;
using TokenPay.Models.EthModel;

namespace TokenPay.Controllers
{
    [Route("{action}")]
    [ApiExplorerSettings(IgnoreApi = true)]
    public class HomeController : Controller
    {
        private readonly IBaseRepository<TokenOrders> _repository;
        private readonly IBaseRepository<TokenRate> _rateRepository;
        private readonly IBaseRepository<Tokens> _tokenRepository;
        private readonly List<EVMChain> _chains;
        private readonly IHostEnvironment _env;
        private readonly ILogger<HomeController> _logger;
        private readonly IConfiguration _configuration;

        private FiatCurrency BaseCurrency => Enum.Parse<FiatCurrency>(_configuration.GetValue("BaseCurrency", "CNY")!);

        public static int GetDecimals(string currency, IConfiguration _configuration)
        {
            var decimals = currency switch
            {
                "TRX" => _configuration.GetValue("Decimals:TRX", 2),
                "EVM_ETH" => _configuration.GetValue("Decimals:ETH", 5),
                _ => _configuration.GetValue($"Decimals:{currency}", 4)
            };

            return decimals;
        }

        private List<string> GetErc20Name()
        {
            var list = new List<string>();
            foreach (var item in _chains)
            {
                list.Add(item.ERC20Name);
            }
            list = list.Distinct().ToList();
            return list;
        }

        private decimal GetRate(string currency)
        {
            // BINANCE_USDT_BSC → lấy phần giữa = "USDT"
            if (currency.StartsWith("BINANCE_", StringComparison.OrdinalIgnoreCase))
            {
                var parts = currency.Split('_', StringSplitOptions.RemoveEmptyEntries);
                var token = parts.Length > 1 ? parts[1] : "USDT";
                return _configuration.GetValue($"Rate:{token}", 0m);
            }

            var erc20Names = GetErc20Name();
            foreach (var item in erc20Names)
            {
                currency = currency.Replace(item, "");
            }

            var _currency = currency.Replace("TRC20", "")
                .Split("_", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Last();

            var value = _currency switch
            {
                "TRX" => _configuration.GetValue("Rate:TRX", 0m),
                "ETH" => _configuration.GetValue("Rate:ETH", 0m),
                "USDT" => _configuration.GetValue("Rate:USDT", 0m),
                "USDC" => _configuration.GetValue("Rate:USDC", 0m),
                _ => _configuration.GetValue($"Rate:{_currency}", 0m)
            };

            return value;
        }

        public List<string> GetActiveCurrency()
            => GetActiveCurrency(_chains, _configuration);

        public static List<string> GetActiveCurrency(List<EVMChain> chains,
            IConfiguration? configuration = null)
        {
            var list = new List<string>()
            {
                "TRX","USDT_TRC20"
            };

            foreach (var chain in chains)
            {
                if (chain == null || !chain.Enable || chain.ERC20 == null) continue;
                list.Add($"EVM_{chain.ChainNameEN}_{chain.BaseCoin}");
                foreach (var erc20 in chain.ERC20)
                {
                    list.Add($"EVM_{chain.ChainNameEN}_{erc20.Name}_{chain.ERC20Name}");
                }
            }

            // Binance Exchange: thêm nếu đã cấu hình Enable=true
            if (configuration != null && configuration.GetValue("Binance:Enable", false))
            {
                var coin    = configuration.GetValue("Binance:Coin",    "USDT");
                var network = configuration.GetValue("Binance:Network", "BSC");
                list.Add($"BINANCE_{coin}_{network}");
            }

            return list;
        }

        public HomeController(
            IBaseRepository<TokenOrders> repository,
            IBaseRepository<TokenRate> rateRepository,
            IBaseRepository<Tokens> tokenRepository,
            List<EVMChain> chain,
            IHostEnvironment env,
            ILogger<HomeController> logger,
            IConfiguration configuration
        )
        {
            this._repository = repository;
            this._rateRepository = rateRepository;
            this._tokenRepository = tokenRepository;
            this._chains = chain;
            this._env = env;
            this._logger = logger;
            this._configuration = configuration;
        }

        [Route("/")]
        public IActionResult Index()
        {
            return View();
        }

        public async Task<IActionResult> Pay(Guid Id)
        {
            var order = await _repository.Where(x => x.Id == Id).FirstAsync();
            if (order == null)
            {
                return View(order);
            }

            ViewData["QrCode"] = Convert.ToBase64String(CreateQrCode(order.ToAddress));
            var ExpireTime = _configuration.GetValue("ExpireTime", 10 * 60);

            if (DateTime.Now > order.CreateTime.AddSeconds(ExpireTime) || order.Status == OrderStatus.Expired)
            {
                return View("OrderExpired", order);
            }

            ViewData["ExpireTime"] = order.CreateTime.AddSeconds(ExpireTime);
            return View(order);
        }

        [HttpGet]
        [ApiExplorerSettings(IgnoreApi = false)]
        public async Task<IActionResult> Query(Guid Id, string Signature)
        {
            if (_env.IsProduction())
            {
                if (!VerifySignature(new
                {
                    Id,
                    Signature
                }))
                {
                    return Json(new ReturnData
                    {
                        Message = "Xác thực chữ ký thất bại!"
                    });
                }
            }

            var order = await _repository.Where(x => x.Id == Id).FirstAsync();
            if (order == null)
            {
                return Json(new ReturnData
                {
                    Message = "Đơn hàng không tồn tại!"
                });
            }

            return Json(new ReturnData<TokenOrders>
            {
                Success = true,
                Message = "Lấy thông tin đơn hàng thành công!",
                Data = order,
            });
        }

        [Route("/{action}/{id}")]
        public async Task<IActionResult> Check(Guid Id)
        {
            var order = await _repository.Where(x => x.Id == Id).FirstAsync();
            if (order == null)
            {
                return Content(OrderStatus.Pending.ToString());
            }
            return Content(order.Status.ToString());
        }

        private bool VerifySignature(object model)
        {
            if (model == null) return false;

            var dic = new SortedDictionary<string, string?>();
            PropertyInfo[] properties = model.GetType().GetProperties();
            if (properties.Length <= 0) { return false; }

            foreach (PropertyInfo item in properties)
            {
                string name = item.Name;
                string? value = item.GetValue(model, null)?.ToString();
                if (string.IsNullOrEmpty(value)) continue;
                dic.Add(name, value);
            }

            if (dic.TryGetValue("Signature", out var Signature))
            {
                dic.Remove("Signature");

                var SignatureStr = string.Join("&", dic.Select(x => $"{x.Key}={x.Value}"));
                var ApiToken = _configuration.GetValue<string>("ApiToken");
                SignatureStr += ApiToken;

                var md5 = SignatureStr.ToMD5();
                return Signature == md5;
            }

            return false;
        }

        /// <summary>
        /// Tạo đơn hàng
        /// </summary>
        [HttpPost]
        [Route("/" + nameof(CreateOrder))]
        [ApiExplorerSettings(IgnoreApi = false)]
        public async Task<IActionResult> CreateOrder([FromBody] CreateOrderViewModel model)
        {
            if (!ModelState.IsValid)
            {
                string messages = string.Join("; ", ModelState.Values
                                        .SelectMany(x => x.Errors)
                                        .Select(x => x.ErrorMessage));

                return Json(new ReturnData
                {
                    Message = messages
                });
            }

            if (_env.IsProduction())
            {
                if (!VerifySignature(model))
                {
                    return Json(new ReturnData
                    {
                        Message = "Xác thực chữ ký thất bại!"
                    });
                }
            }

            if (!GetActiveCurrency().Contains(model.Currency))
            {
                return Json(new ReturnData
                {
                    Message = $"Không hỗ trợ loại coin【{model.Currency}】!\nCác tham số coin hiện đang hỗ trợ: {string.Join(", ", GetActiveCurrency())}"
                });
            }

            if (model.ActualAmount <= 0)
            {
                return Json(new ReturnData
                {
                    Message = "Số tiền không hợp lệ!"
                });
            }

            // Đơn hàng đã tồn tại
            var hasOrder = await _repository
                .Where(x => x.OutOrderId == model.OutOrderId && x.Currency == model.Currency)
                .Where(x => x.Status != OrderStatus.Expired)
                .FirstAsync();

            if (hasOrder != null)
            {
                return Json(new ReturnData<string>
                {
                    Success = true,
                    Message = "Đơn hàng đã tồn tại, trả về đơn cũ!",
                    Data = Host + Url.Action(nameof(Pay), new { Id = hasOrder.Id }),
                    Info = ToPayDic(hasOrder)
                });
            }

            var order = new TokenOrders
            {
                OutOrderId = model.OutOrderId,
                OrderUserKey = model.OrderUserKey,
                Status = OrderStatus.Pending,
                Currency = model.Currency,
                ActualAmount = model.ActualAmount,
                NotifyUrl = model.NotifyUrl,
                RedirectUrl = model.RedirectUrl,
                PassThroughInfo = model.PassThroughInfo,
            };

            var UseDynamicAddress = _configuration.GetValue("UseDynamicAddress", true);
            try
            {
                if (model.Currency.StartsWith("BINANCE_", StringComparison.OrdinalIgnoreCase))
                {
                    // Binance Pay P2P: địa chỉ = Binance ID, note = SHOP{OrderUserKey}
                    var (Address, Amount, Note) = GetBinancePayInfo(model);
                    order.ToAddress      = Address;
                    order.Amount         = Amount;
                    order.PassThroughInfo = Note; // ghi đè PassThroughInfo bằng note tự sinh
                }
                else if (UseDynamicAddress)
                {
                    var (Address, Amount) = await GetUseTokenDynamicAdress(model);
                    order.ToAddress = Address;
                    order.Amount    = Amount;
                }
                else
                {
                    var (Address, Amount) = await GetUseTokenStaticAdress(model);
                    order.ToAddress = Address;
                    order.Amount    = Amount;
                }
            }
            catch (TokenPayException e)
            {
                return Json(new ReturnData
                {
                    Message = e.Message
                });
            }

            if (order.Amount <= 0)
            {
                return Json(new ReturnData
                {
                    Message = "Số tiền đơn hàng này quá nhỏ!"
                });
            }

            await _repository.InsertAsync(order);

            return Json(new ReturnData<string>
            {
                Success = true,
                Message = "Tạo đơn hàng thành công!",
                Data = Host + Url.Action(nameof(Pay), new { Id = order.Id }),
                Info = ToPayDic(order)
            });
        }

        private SortedDictionary<string, object?> ToPayDic(TokenOrders order)
        {
            var BaseCurrency = _configuration.GetValue<string>("BaseCurrency", "CNY");
            var ExpireTime = _configuration.GetValue("ExpireTime", 10 * 60);

            var isBinancePay = order.Currency.StartsWith("BINANCE_", StringComparison.OrdinalIgnoreCase);

            var dic = new SortedDictionary<string, object?>
            {
                { nameof(order.Id), order.Id.ToString() },
                { nameof(order.OutOrderId), order.OutOrderId },
                { nameof(order.OrderUserKey), order.OrderUserKey },
                { nameof(order.Amount), order.Amount.ToString() },
                { nameof(order.ActualAmount), order.ActualAmount.ToString() },
                { nameof(order.ToAddress), order.ToAddress },
                { nameof(order.PassThroughInfo), order.PassThroughInfo },
                { "BaseCurrency", BaseCurrency },
                { "BlockChainName", order.Currency.ToBlockchainEnglishName(_chains) },
                { "CurrencyName", order.Currency.ToCurrency(_chains) },
                { "ExpireTime", order.CreateTime.AddSeconds(ExpireTime).ToString("yyyy-MM-dd HH:mm:ss")},
                // Binance Pay: expose BinanceId và NoteToPayee thay vì QR code ví
                { "BinanceId",    isBinancePay ? order.ToAddress : null },
                { "NoteToPayee",  isBinancePay ? order.PassThroughInfo : null },
                { "QrCodeBase64", isBinancePay ? null
                    : "data:image/png;base64," + Convert.ToBase64String(CreateQrCode(order.ToAddress))},
                { "QrCodeLink",   isBinancePay ? null
                    : Host + Url.Action(nameof(GetQrCode), new { Id = order.Id })},
            };

            return dic;
        }

        /// <summary>
        /// Lấy QR code tương ứng với đơn hàng
        /// Kích thước mặc định: 300x300
        /// </summary>
        public async Task<IActionResult> GetQrCode(Guid Id, int Size = 300)
        {
            var order = await _repository.Where(x => x.Id == Id).FirstAsync();
            if (order == null)
            {
                return File(new byte[0], "image/png");
            }
            return File(CreateQrCode(order.ToAddress, Size), "image/png");
        }

        private string Host
        {
            get
            {
                var host = _configuration.GetValue<string>("WebSiteUrl");
                if (string.IsNullOrEmpty(host))
                {
                    host = $"{Request.Scheme}://{Request.Host}";
                }
                return host;
            }
        }

        /// <summary>
        /// Địa chỉ động
        /// </summary>
        private async Task<(string, decimal)> GetUseTokenDynamicAdress(CreateOrderViewModel model)
        {
            var (UseTokenAdress, _) = await CreateAddress(model.OrderUserKey, model.Currency);
            var rate = GetRate(model.Currency);

            if (rate <= 0)
            {
                var Currency = model.Currency.ToCurrency(_chains);
                rate = await _rateRepository
                    .Where(x => x.Currency == Currency && x.FiatCurrency == BaseCurrency)
                    .FirstAsync(x => x.Rate);
            }

            if (rate <= 0)
            {
                throw new TokenPayException("Tỷ giá không hợp lệ!");
            }

            // Vì mỗi người dùng có một địa chỉ thanh toán riêng, nên logic tính tiền ở đây khác với địa chỉ tĩnh
            var Amount = (model.ActualAmount / rate).ToRound(GetDecimals(model.Currency, _configuration));
            return (UseTokenAdress, Amount);
        }

        /// <summary>
        /// Tạo/lấy một địa chỉ theo ID duy nhất của người dùng
        /// </summary>
        private async Task<(string, string)> CreateAddress(string OrderUserKey, string currency)
        {
            if (string.IsNullOrEmpty(OrderUserKey))
            {
                throw new TokenPayException("Địa chỉ động yêu cầu truyền định danh người dùng!");
            }

            var BaseCurrency = TokenCurrency.TRX;

            // Coin bắt đầu bằng EVM thì xem như EVM
            if (currency.StartsWith("EVM"))
            {
                BaseCurrency = TokenCurrency.EVM;
            }

            var TokenId = $"{BaseCurrency}_{OrderUserKey}";
            var token = await _tokenRepository.Where(x => x.Id == TokenId && x.Currency == BaseCurrency).FirstAsync();

            if (token == null)
            {
                var ecKey = Nethereum.Signer.EthECKey.GenerateKey();
                var rawPrivateKey = ecKey.GetPrivateKeyAsBytes();
                var hex = Convert.ToHexString(rawPrivateKey);

                if (BaseCurrency == TokenCurrency.EVM)
                {
                    var Address = ecKey.GetPublicAddress();
                    token = new Tokens
                    {
                        Id = TokenId,
                        Address = Address,
                        Key = hex,
                        Currency = TokenCurrency.EVM
                    };
                    await _tokenRepository.InsertAsync(token);
                }
                else
                {
                    var tronWallet = new TronWallet(hex);
                    var Address = tronWallet.Address;
                    token = new Tokens
                    {
                        Id = TokenId,
                        Address = Address,
                        Key = hex,
                        Currency = TokenCurrency.TRX
                    };
                    await _tokenRepository.InsertAsync(token);
                }
            }

            return (token.Address, token.Key);
        }

        /// <summary>
        /// Binance Pay P2P:
        ///   - ToAddress  = Binance ID của merchant (hiển thị cho user nhập vào app Binance)
        ///   - Note        = "{NotePrefix}{OrderUserKey}" — ví dụ "SHOP5147388757"
        ///                   Unique per user, dùng để match giao dịch thay vì unique_amount
        ///   - Amount      = ActualAmount (không cần +0.0001 vì note đã unique)
        /// </summary>
        private (string address, decimal amount, string note) GetBinancePayInfo(CreateOrderViewModel model)
        {
            var binanceId  = _configuration.GetValue<string>("Binance:BinanceId") ?? "";
            var notePrefix = _configuration.GetValue("Binance:NotePrefix", "SHOP");

            if (string.IsNullOrWhiteSpace(binanceId))
                throw new TokenPayException(
                    "Chưa cấu hình Binance:BinanceId trong appsettings.json. " +
                    "Vào Binance app → Cài đặt → Binance Pay → ID của tôi để lấy Binance ID.");

            // Note = "SHOP" + OrderUserKey (= telegram_id)
            // Unique per user; Python backend đảm bảo mỗi user chỉ có 1 pending order
            var note = $"{notePrefix}{model.OrderUserKey}";

            // Rate tính như bình thường (USDT=1 nên Amount = ActualAmount)
            var rate = GetRate(model.Currency);
            if (rate <= 0)
                throw new TokenPayException("Tỷ giá không hợp lệ!");

            var amount = (model.ActualAmount / rate)
                .ToRound(GetDecimals(model.Currency, _configuration));

            return (binanceId, amount, note);
        }

        /// <summary>
        /// Địa chỉ tĩnh
        /// </summary>
        private async Task<(string, decimal)> GetUseTokenStaticAdress(CreateOrderViewModel model)
        {
            var TRON = _configuration.GetSection("Address:TRON").Get<string[]>() ?? new string[0];
            var EVM  = _configuration.GetSection("Address:EVM").Get<string[]>()  ?? new string[0];

            string[] CurrentAdress;

            // BINANCE_USDT_BSC: dùng Address:BINANCE (địa chỉ nạp Binance exchange của bạn)
            if (model.Currency.StartsWith("BINANCE_", StringComparison.OrdinalIgnoreCase))
            {
                CurrentAdress = _configuration.GetSection("Address:BINANCE")
                    .Get<string[]>()
                    ?.Where(a => !string.IsNullOrWhiteSpace(a))
                    .ToArray() ?? [];

                if (CurrentAdress.Length == 0)
                    throw new TokenPayException(
                        "Chưa cấu hình Address:BINANCE trong appsettings.json. " +
                        "Vào Binance → Ví → Nạp tiền → USDT → BSC để lấy địa chỉ.");
            }
            else
            {
                var CurrencyAddress = _configuration.GetSection(
                    $"Address:{model.Currency.Replace("EVM", "").Split("_", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).First()}"
                ).Get<string[]>() ?? new string[0];

                CurrentAdress = CurrencyAddress;

                if (CurrentAdress.Length == 0 && (model.Currency == "TRX" || model.Currency.EndsWith("TRC20")))
                    CurrentAdress = TRON;

                if (CurrentAdress.Length == 0 && model.Currency.StartsWith("EVM"))
                    CurrentAdress = EVM;

                if (CurrentAdress.Length == 0)
                    throw new TokenPayException("Chưa cấu hình địa chỉ nhận tiền!");
            }

            var rate = GetRate(model.Currency);
            if (rate <= 0)
            {
                var Currency = model.Currency.ToCurrency(_chains);
                rate = await _rateRepository.Where(x => x.Currency == Currency && x.FiatCurrency == BaseCurrency).FirstAsync(x => x.Rate);
            }

            if (rate <= 0)
            {
                throw new TokenPayException("Tỷ giá không hợp lệ!");
            }

            var Amount = (model.ActualAmount / rate).ToRound(GetDecimals(model.Currency, _configuration));

            // Xáo trộn ngẫu nhiên danh sách địa chỉ nhận tiền
            CurrentAdress = CurrentAdress.OrderBy(x => Guid.NewGuid()).ToArray();

            var UseTokenAdress = string.Empty;

            foreach (var token in CurrentAdress)
            {
                // Kiểm tra: có tồn tại đơn chờ thanh toán với cùng số tiền + địa chỉ + coin hay không
                var has = await _repository
                    .Where(x => x.ToAddress == token)
                    //.Where(x => x.ActualAmount == order.ActualAmount) // Số tiền gốc
                    .Where(x => x.Currency == model.Currency)          // Loại coin
                    .Where(x => x.Amount == Amount)                   // Số coin cần thanh toán
                    .Where(x => x.Status == OrderStatus.Pending)      // Đang chờ thanh toán
                    .AnyAsync();

                if (!has)
                {
                    UseTokenAdress = token;
                    break;
                }
            }

            // Nếu tất cả địa chỉ đều đã có đơn trùng số tiền, thử tăng dần Amount theo số chữ số thập phân
            if (string.IsNullOrEmpty(UseTokenAdress))
            {
                var decimals = GetDecimals(model.Currency, _configuration); // 2 chữ số -> 100 lần; 3 chữ số -> 1000 lần...
                var maxLoop = Math.Max(5, Math.Pow(10, decimals));         // Trường hợp 0 chữ số, giới hạn tối thiểu 5 lần
                var AddAmount = Convert.ToDecimal(1 / maxLoop);            // Bước tăng ban đầu

                for (int i = 0; i < maxLoop; i++)
                {
                    foreach (var token in CurrentAdress)
                    {
                        var currentAmount = Amount + AddAmount * (i + 1);

                        var query = _repository
                            .Where(x => x.ToAddress == token)
                            //.Where(x => x.ActualAmount == order.ActualAmount) // Số tiền gốc
                            .Where(x => x.Currency == model.Currency)
                            .Where(x => x.Amount == currentAmount)
                            .Where(x => x.Status == OrderStatus.Pending);

                        var has = await query.AnyAsync();

                        if (!has)
                        {
                            UseTokenAdress = token;
                            Amount = currentAmount;
                            break;
                        }
                    }

                    if (!string.IsNullOrEmpty(UseTokenAdress))
                    {
                        break;
                    }
                }
            }

            if (string.IsNullOrEmpty(UseTokenAdress))
            {
                throw new TokenPayException("Không có địa chỉ nhận tiền khả dụng!");
            }

            return (UseTokenAdress, Amount);
        }

        [Route("/CheckTron/{address}")]
        [Route("/{action}/{address}")]
        public async Task<IActionResult> CheckTronAddress(string address)
        {
            var item = await _tokenRepository.Where(x => x.Address == address && x.Currency == TokenCurrency.TRX).FirstAsync();
            if (item == null)
            {
                _logger.LogWarning("Địa chỉ cần kiểm tra [{address}] không tồn tại!", address);
                return Content("ok");
            }

            item.Value = await QueryTronAction.GetTRXAsync(address);
            item.USDT = await QueryTronAction.GetUsdtAmountAsync(address);
            await _tokenRepository.UpdateAsync(item);

            return Content("ok");
        }

        [Route("/error-development")]
        public IActionResult HandleErrorDevelopment([FromServices] IHostEnvironment hostEnvironment)
        {
            var exceptionHandlerFeature = HttpContext.Features.Get<IExceptionHandlerFeature>()!;
            var e = exceptionHandlerFeature.Error;

            if (!hostEnvironment.IsDevelopment())
            {
                return Json(new ReturnData
                {
                    Message = e.Message
                });
            }

            return Json(new ReturnData<object>
            {
                Message = e.Message,
                Data = new
                {
                    title = exceptionHandlerFeature.Error.Message,
                    detail = exceptionHandlerFeature.Error.StackTrace,
                }
            });
        }

        [Route("/error")]
        public IActionResult HandleError() => Problem();

        /// <summary>
        /// Tạo QR code
        /// </summary>
        private static byte[] CreateQrCode(string qrcode, int size = 300)
        {
            using var stream = new MemoryStream();
            var qrCode = new QrCode(qrcode, new Vector2Slim(size, size), SKEncodedImageFormat.Png);
            qrCode.GenerateImage(stream);
            return stream.ToArray();
        }
    }
}

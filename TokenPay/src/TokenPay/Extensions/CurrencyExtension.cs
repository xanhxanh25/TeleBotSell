using NBitcoin;
using Nethereum.Signer;
using TokenPay.Domains;
using TokenPay.Models.EthModel;

namespace TokenPay.Extensions
{
    public static class CurrencyExtension
    {
        public static string ToCurrency(this string currency, List<EVMChain> chains, bool hasSuffix = false)
        {
            // BINANCE_USDT_BSC → "USDT"
            if (currency.StartsWith("BINANCE_", StringComparison.OrdinalIgnoreCase))
            {
                var parts = currency.Split('_', StringSplitOptions.RemoveEmptyEntries);
                return parts.Length > 1 ? parts[1] : "USDT";
            }

            if (hasSuffix)
            {
                if (currency.StartsWith("EVM"))
                {
                    currency = currency.Replace("EVM_", "");
                    var coin = currency.Split("_", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).First();
                    currency = currency.Replace($"{coin}_", "");
                }
                return currency.Replace($"_", "-");
            }

            var erc20Names = chains.Select(x => x.ERC20Name).ToArray();
            foreach (var item in erc20Names)
            {
                currency = currency.Replace(item, "");
            }

            var str = currency.Replace("TRC20", "")
                              .Split("_", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                              .Last();

            return str;
        }

        public static string ToBlockchainName(this string currency, List<EVMChain> chains)
        {
            if (currency == "TRX" || currency.EndsWith("TRC20")) return "TRON";
            // BINANCE_USDT_BSC → "Binance Exchange (BSC)"
            if (currency.StartsWith("BINANCE_", StringComparison.OrdinalIgnoreCase))
            {
                var parts = currency.Split('_', StringSplitOptions.RemoveEmptyEntries);
                var network = parts.Length > 2 ? parts[2] : "BSC";
                return $"Binance Exchange ({network})";
            }

            var ChainNameEN = currency.Replace("EVM", "")
                                      .Split("_", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                                      .First();

            var chain = chains.Where(x => x.ChainNameEN == ChainNameEN).FirstOrDefault();
            if (chain != null)
            {
                return chain.ChainName;
            }

            return $"Blockchain không xác định [{currency}]";
        }

        public static string ToBlockchainEnglishName(this string currency, List<EVMChain> chains)
        {
            if (currency == "TRX" || currency.EndsWith("TRC20")) return "TRON";
            // BINANCE_USDT_BSC → "Binance"
            if (currency.StartsWith("BINANCE_", StringComparison.OrdinalIgnoreCase))
                return "Binance";

            var ChainNameEN = currency.Replace("EVM", "")
                                      .Split("_", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                                      .First();

            var chain = chains.Where(x => x.ChainNameEN == ChainNameEN).FirstOrDefault();
            if (chain != null)
            {
                return chain.ChainNameEN;
            }

            return $"Unknown Blockchain[{currency}]";
        }
    }
}

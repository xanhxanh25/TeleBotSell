namespace TokenPay.Extensions
{
    public static class DecimalExtension
    {
        /// <summary>
        /// Làm tròn (tứ xả ngũ nhập) theo quy tắc AwayFromZero
        /// </summary>
        /// <param name="value"></param>
        /// <param name="decimals">Số chữ số thập phân</param>
        /// <returns></returns>
        public static decimal ToRound(this decimal value, int decimals = 4)
        {
            return Math.Round(value, decimals, MidpointRounding.AwayFromZero);
        }

        public static decimal ToRound(this double value, int decimals = 4)
        {
            return Math.Round((decimal)value, decimals, MidpointRounding.AwayFromZero);
        }

        public static decimal ToRound(this float value, int decimals = 4)
        {
            return Math.Round((decimal)value, decimals, MidpointRounding.AwayFromZero);
        }
    }
}

# M-Pesa payment destination

The SaaS keeps the Daraja application Short Code and the actual receiving Till as separate configuration values.

- `DARAJA_SHORTCODE` is the Daraja Short Code supplied by the production application configuration.
- `DARAJA_TILL_NUMBER` is the Buy Goods/Till that should receive the customer's payment.
- When `DARAJA_TRANSACTION_TYPE=CustomerBuyGoodsOnline`, the STK request uses the Till as the receiving BusinessShortCode/PartyB destination and the customer's phone as PartyA.
- When `DARAJA_TRANSACTION_TYPE=CustomerPayBillOnline`, the PayBill Short Code is used instead.
- The callback is derived from the configured root domain when only the root domain is supplied.

Example for the Buy Goods setup used by GEOPRAM TECHNOLOGIES:

- Daraja Short Code: `4574727`
- Receiving Till: `5367886`
- Transaction type: `CustomerBuyGoodsOnline`

Do not expose the Consumer Secret or Passkey in browser code, logs, screenshots or audit metadata.

# 支持的金融产品

> 回答「当前能支持任意金融产品吗？」——**Nautilus 引擎支持所有主流资产类别；ntquant
> 脚手架已把常用类别接入，均可构建并跑回测。** 但每类资产有各自的精度/币种约定，
> 配错会报错。本文档说明现状与开关。

## 结论

- **引擎层**：`nautilus_trader 1.231.0` 完整支持外币、股票、加密、期货、期权、指数、
  商品、CFD、合成等，数据/下单/报表机制（`BarDataWrangler`、`make_qty`、`ReportProvider`）
  与资产类别无关，跨品类通用。
- **脚手架层**：`make_instrument` 已按 `asset_class` 分派到对应 Nautilus instrument 类，
  单资产回测可直接跑通（FX / EQUITY / CRYPTOCURRENCY 均已实测通过完整回测）。
- 当前脚手架仍是**单标的、单策略**设计；切换产品 = 改 `asset_class` 与相关字段 + 配置
  对应的 `bar_type`，无需改引擎。

## asset_class → 映射

| `asset_class`（YAML 值） | Nautilus instrument 类 | 说明 |
|---|---|---|
| `FX` | `CurrencyPair` | 外汇对，默认 |
| `EQUITY` | `Equity` | 股票（如 AAPL） |
| `CRYPTOCURRENCY`（或 `CRYPTO`） | `CryptoPerpetual` | 加密永续（如 BTCUSDT-PERP） |
| `FUTURE`（或 `FUTURES`） | `FuturesContract` | 期货月合约 |
| `INDEX` | `IndexInstrument` | 指数（如 SPX500） |
| `COMMODITY` | `Commodity` | 商品 |
| `CFD` | `Cfd` | 差价合约 |

> `FUTURE`/`CFD` 是 *instrument class*；它们的底层 `asset_class`（如指数期货为 `EQUITY`）
> 已由 `make_instrument` 内部处理，配置里直接写 `FUTURE` / `CFD` 即可。

## 各资产需要对齐的字段

不同 instrument 的**精度**与**币种**字段必须与数据、订单匹配，否则引擎报错
（如 `invalid bar.open.precision=5 did not match instrument.price_precision=2`）。
主要差异：

| 字段 | FX | Crypto | Equity |
|---|---|---|---|
| `price_precision` | 5（如 `1.08500`） | 2（如 `50000.00`） | 2（如 `180.00`） |
| `size_precision` | 2 | 0（整数张数） | 0（整数股数） |
| `price_increment` | `"0.00001"` | `"0.01"` | `"0.01"` |
| `size_increment` | `"0.01"` | `"1"` | `"1"` |
| 报价币种 | `quote_currency` | `quote_currency`/`settlement_currency` | `currency`（用 `base_currency`） |

生成合成数据时，`generate_synthetic_bars` 会自动按 `price_precision`/`size_precision`
生成匹配精度的价格与 volume；`start_price` 用于设置初始价（如 crypto 设为 `50000`，
股票设为 `180`）。

## 账户基币需与标的币种一致

`run_backtest` 的账户 `base_currency` 取自 `venue.base_currency`，**应与标的的结算币种一致**：

- FX：账户 `USD`，标的 `EUR/USD`（quote=USD）✅
- Crypto：账户 `USDT`，标的 `BTCUSDT`（quote=USDT）✅
- 股票：账户 `USD`，标的 `AAPL` ✅

若不一致（如标的 USDT 而账户 USD），会报 `Cannot record ... conversion failed from
USDT to USD` 的 PnL 换算警告。

## 完整切换示例（以 Crypto 为例）

`ntquant/configs/backtest.yaml`：

```yaml
venue:
  base_currency: USDT        # 与标的结算币种一致
  account_type: MARGIN

instrument:
  asset_class: CRYPTOCURRENCY
  instrument_id: BTCUSDT-PERP.SIM
  raw_symbol: BTCUSDT-PERP
  base_currency: BTC
  quote_currency: USDT
  settlement_currency: USDT
  price_precision: 2
  size_precision: 0
  price_increment: "0.01"
  size_increment: "1"
  max_quantity: 100000
  start_price: 50000.0

strategy:
  bar_type: BTCUSDT-PERP.SIM-1-MINUTE-LAST-EXTERNAL
  trade_size: "1"            # 整数张数
```

然后 `make backtest`。

## 尚未覆盖（提示）

- **期权/二元/合成/多标的组合**：`make_instrument` 未分派这些（`BinaryOption`、
  `OptionContract`、`SyntheticInstrument` 等）。如需可仿照 `instruments.py` 新增分派。
- **真实数据**：当前用合成数据；接真实行情走 `data/loaders.py`（占位）+ `DataCatalog`。
- **多标的并行**：脚手架目前单 instrument；多标的需在 `runner` 里循环 add_instrument/
  add_data，策略侧用各自 bar_type。

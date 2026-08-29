# Data Ingestion — 接入真实数据

`ntquant` 的投研目录统一走 **ParquetDataCatalog**：所有真实行情先被拉取、规范化，再由
`BarDataWrangler` 转成 Nautilus `Bar` 写入 catalog。此后回测、参数扫描、分析、可视化全部
从同一个数据层读取（`use_catalog=True` 或 `data.source != synthetic`）。

## 数据管线

```
来源(Csv/Binance/...) ──> pd.DataFrame(OHLCV) ──> normalize_ohlcv_frame ──> BarDataWrangler.process
                                          └────────────> write_data([instrument]+bars) ──> catalog
```

- 所有来源最后落到 `ntquant/data/ingest.py::ingest`，一次调度完成取数→规范→落库。
- 落库后再跑回测会**自动绕过合成数据**（见 `runner._load_bars`）。

## 支持的来源（`data.source`）

| source | 说明 | 关键配置 |
|---|---|---|
| `synthetic` | 默认，内存合成 OHLCV（不落库） | 无 |
| `csv` / `parquet` | 本地 OHLCV 文件 | `source_path` 文件路径 |
| `binance` | Binance 公开 klines REST（免密钥），支持现货与 USDT-M 永续 | `instrument.raw_symbol` + bar_type |

Polygon / Alpha Vantage / Databento 已提供占位类（`PolygonSource` 等），需要 API key 且未接入，
调用会抛 `NotImplementedError`，留作后续扩展。

## 快速上手

### 1. 本地 CSV / Parquet

内置列名规范：`timestamp` 索引 + `open/high/low/close/volume`。若你的 CSV 列名不同，在 YAML 里映射：

```yaml
data:
  source: csv
  source_path: data/eurusd_1min.csv   # 相对或绝对路径
  timestamp_col: time                  # 若时间是一列而非索引
  columns:                             # 可选：任意来源列名 -> 规范列名
    time: timestamp
    open: open
    high: high
    low: low
    close: close
    volume: volume
```

写入 catalog：

```bash
make ingest source=csv
# 或直接：.venv/bin/python run.py ingest --source csv
```

### 2. Binance K 线（免密钥）

把 `instrument` 与 `data` 改成对应合约，例如 BTC/USDT 1 小时：

```yaml
instrument:
  asset_class: CRYPTOCURRENCY
  instrument_id: BTC/USDT.BINANCE
  raw_symbol: BTC/USDT
  base_currency: USDT
  quote_currency: USDT
  settlement_currency: USDT
  price_precision: 2
  size_precision: 4
  price_increment: "0.01"
  size_increment: "0.0001"

data:
  source: binance
  bar_type: BTC/USDT.BINANCE-1-HOUR-LAST-EXTERNAL
  instrument_id: BTC/USDT.BINANCE
```

拉取并落库：

```bash
.venv/bin/python run.py ingest --source binance
```

`BinanceKlineSource` 会从 `raw_symbol` 生成 `BTCUSDT`，从 bar_type 的 `1-HOUR` 推断 `1h`。
默认单次拉 `limit=1000` 根，可在 `ingest --source binance` 外通过配置调整。

**永续合约**：`raw_symbol` 带 `-PERP` 标记（如 `ETHUSDT-PERP`）即自动走 USDT-M 永续端点
`/fapi/v1/klines`，查询符号会去掉 `-PERP`（→ `ETHUSDT`）。`data` 的 `bar_type`/`instrument_id`
同样用 `ETHUSDT-PERP.BINANCE`，例如：

```yaml
instrument:
  asset_class: CRYPTOCURRENCY
  instrument_id: ETHUSDT-PERP.BINANCE
  raw_symbol: ETHUSDT-PERP
  base_currency: ETH
  quote_currency: USDT
  settlement_currency: USDT
  price_precision: 2
  size_precision: 3
  price_increment: "0.01"
  size_increment: "0.001"

data:
  source: binance
  bar_type: ETHUSDT-PERP.BINANCE-15-MINUTE-LAST-EXTERNAL
  instrument_id: ETHUSDT-PERP.BINANCE
```

### 3. 使用代理（跨越地域封禁）

某些网络环境下 Binance 返回 `HTTP 451`（区域限制）。可在 `data.proxy` 配置 HTTP/HTTPS 代理：

```yaml
data:
  source: binance
  proxy: http://127.0.0.1:7890
```

也支持环境变量 `NTA_DATA__PROXY=http://127.0.0.1:7890` 覆盖。代理仅影响网络型数据源
（当前为 `BinanceKlineSource`），本地 `csv`/`parquet` 不受影响。

## 回测使用真实数据

回测只关心 `data.source`：非 `synthetic` 一律从 catalog 读取，**无需** `--catalog` 标志。

```bash
make backtest        # data.source=synthetic 时仍走合成；非 synthetic 走 catalog
make data            # --catalog：显式从 catalog 读（合成场景下预先生成亦可）
```

## 增量与合并

`ParquetDataCatalog` 按时间范围分文件存储，`ingest` 每次用 `write_data` 写入并调用
`consolidate_data` 做去重分区合并，避免碎片化。若自行多次增量写入，建议手动合并：

```python
from ntquant.data.catalog import DataCatalog
from nautilus_trader.model import Bar
cat = DataCatalog("docs/data")
cat.merge_bars(data_cls=Bar, deduplicate=True)
```

## 环境变量覆盖

`NTA_*` 可覆盖 YAML（见 `config.py`）：

```bash
NTA_DATA__SOURCE=binance
NTA_DATA__SOURCE_PATH=/path/bars.csv
NTA_DATA__CATALOG_PATH=docs/data
NTA_DATA__PROXY=http://127.0.0.1:7890
```

真实的 API key 请放 `.env`（参考 `.env.example`），仓库不入库。

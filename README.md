# ntquant

基于 NautilusTrader 1.231.0 的终端回测与投研项目。数据、策略、回测和分析分模块实现；
单次回测与多品种研究共用策略注册表和回测执行路径。

## 安装与运行

使用 Python 3.12 和 uv：

```bash
make install
make backtest
make test
```

`make backtest` 等价于 `.venv/bin/python run.py backtest`。默认运行配置中的策略，
使用合成数据时无需先导入数据；CSV 报表写入 `output/`。

可在终端直接切换策略和参数：

```bash
.venv/bin/python run.py backtest --strategy rsi_reversal --param period=7,oversold=25
.venv/bin/python run.py backtest --config configs/backtest.yaml --prefix rsi
```

可用策略：`ema_cross`、`rsi_reversal`、`bollinger_reversal`、`roc_momentum`、
`macd_cross`。策略类的默认值用于未指定的专属参数。新增策略只需实现类并在
`ntquant/strategies/registry.py` 登记，详见
[新增策略](docs/extending-new-strategy.md)。

## 配置与数据

`configs/backtest.example.yaml` 是回测模板；可复制为被忽略的
`configs/backtest.yaml` 修改。`strategy.name` 选策略，其他专属参数直接写在
`strategy` 段。切换配置中的策略名时，应同步调整其专属参数。
`NTA_<SECTION>__<KEY>` 环境变量优先于 YAML，例如
`NTA_STRATEGY__FAST_PERIOD=15`。

合成数据由回测命令直接生成。CSV、Parquet 或 Binance 数据先通过
`make ingest source=<来源>` 写入 catalog，再运行回测。数据格式和标的配置见
[数据接入](docs/data-ingestion.md)与[支持的标的](docs/supported-instruments.md)。

## 其他命令

| 命令 | 用途 |
|---|---|
| `make param` | 按 `configs/param.yaml` 的网格扫描参数，写入 `output/param_results.csv` |
| `make report` | 生成 CSV 报表和 HTML tearsheet |
| `make ingest source=csv` | 导入真实数据 |
| `make test` | 运行测试 |

研究命令对指定品种和时间窗输出 PnL、收益率、胜率、盈亏比、夏普和最大回撤：

```bash
.venv/bin/python run.py research --strategy ema_cross --symbols BTC,ETH,SOL \
    --market perp --start 2023-01-01 --end 2024-01-01
```

真实数据研究需要相应时间窗的 catalog bars。项目锁定 NautilusTrader 1.231.0；
与当前官方文档的 API 差异见[版本说明](docs/version-notes.md)。

# Version Notes — NautilusTrader 1.231.0

> **为什么有这个文件**：官方文档 `https://nautilustrader.io/docs/latest/` 的部分导入路径
> 与我们实测安装的 `nautilus_trader 1.231.0` 不一致。**照抄 `latest` 文档的导入会直接 `ImportError`。**
> 本项目**一律以实测可用的 1.231.0 真实路径为准**。后续改代码前先查此表。

## 实测 API 路径（1.231.0，已验证 import 可用）

| 能力 | 1.231.0 实测路径 | 文档 `latest` 写的路径（可能报错） |
|---|---|---|
| 低层回测引擎 | `from nautilus_trader.backtest.engine import BacktestEngine` | `from nautilus_trader.backtest import BacktestEngine` ❌ |
| 高层回测节点 | `from nautilus_trader.backtest.node import BacktestNode` | `from nautilus_trader.config import BacktestNode` ❌ |
| 回测运行配置 | `from nautilus_trader.config import BacktestRunConfig` | ✅ 相同 |
| 回测场馆配置 | `from nautilus_trader.config import BacktestVenueConfig` | ✅ 相同 |
| 回测数据配置 | `from nautilus_trader.config import BacktestDataConfig` | ✅ 相同 |
| 引擎配置 | `from nautilus_trader.config import BacktestEngineConfig`（模块在 `nautilus_trader.backtest.config`） | ✅ 可 import |
| 日志配置 | `from nautilus_trader.config import LoggingConfig` | ✅ 相同（模块在 `nautilus_trader.common.config`） |
| 风控配置 | `from nautilus_trader.config import RiskEngineConfig` | ✅ 相同 |
| 策略基类 | `from nautilus_trader.trading.strategy import Strategy` | ✅ 相同 |
| 策略配置基类 | `from nautilus_trader.trading.strategy import StrategyConfig`（模块 `nautilus_trader.trading.config`） | ✅ 可 import |
| 指标 | `from nautilus_trader.indicators import ExponentialMovingAverage` | ✅ 相同 |
| Parquet 目录 | `from nautilus_trader.persistence.catalog import ParquetDataCatalog` | 文档可能写 `nautilus_trader.data.catalog` ❌ |
| 数据 wrangler | `from nautilus_trader.persistence.wranglers import BarDataWrangler` | 文档可能写 `nautilus_trader.data.wranglers` ❌ |
| 分析/tearsheet | `from nautilus_trader.analysis import create_tearsheet, ReportProvider` | ✅ 相同 |

## 已安装 extras

- `nautilus_trader[visualization]` → plotly, kaleido
- 指定版本：`nautilus_trader==1.231.0`
- Python：3.12（uv 管理环境 `.venv`）

## 重要约定

1. **环境**：使用 `.venv`（uv 创建）。安装依赖用 `uv pip install --python .venv/bin/python <pkg>`。
2. **实测优先**：任何 API 改动，先 `import` 验证，再写代码，勿凭文档记忆。
3. **每次运行先在项目根目录**（`pyproject.toml` 所在处）以 `ntquant` 包方式导入。
4. 数据目录 `docs/data/`、输出 `output/`、配置 `ntquant/configs/`。

## 已知坑（1.231.0 实测）

- `strategy_id` 必须传**普通字符串** `"EMA-001"`；传 `StrategyId(...)` 对象会报
  `TypeError: Argument 'name' has incorrect type (expected str, got StrategyId)`。
- `StrategyConfig` 扩展**不能用官方 `__init__`/`__new__` + `_CUSTOM_FIELDS` 模式**
  （报 `TypeError: Struct types cannot define __init__/__new__`）。正确方式：在子类用
  **msgspec 类型注解**声明自有字段（见 `ntquant/strategies/base.py`）。
- 订单/数量精度：bar `volume` 与订单 `quantity` 需匹配 `size_precision`。用
  `instrument.make_qty(...)` 规范化（`ntquant/strategies/base.py`）。
- `BacktestEngine` **没有** `generate_*_report` 方法；报表用
  `nautilus_trader.analysis.ReportProvider.generate_*(cache_data)`。
- `RiskEngineConfig` 接入 `BacktestEngineConfig(risk_engine=...)`：`bypass=False` 时
  `max_notional_per_order` 触发 `AttributeError: 'int' object has no attribute 'split'`。
  安全默认 `bypass=True`（见 `ntquant/risk/__init__.py`）。

# AGENTS.md — ntquant

个人量化投研 + 回测脚手架，基于 **NautilusTrader 1.231.0**。本文档是项目结构与约定的
核心说明，改动代码前请先读完「版本铁律」和「已知坑」。

## 项目定位

- **范围**：回测 + 投研（数据 → 策略 → 回测 → 分析）。实盘仅为占位（`ntquant/live/`）。
- **设计**：沿用官方 `Strategy/StrategyConfig/BacktestEngine/ReportProvider` 等概念，
  但**全部以实测可用的 1.231.0 导入路径为准**，不照抄 `latest` 文档。

## 环境约定

- Python 3.12，**uv 管理的 `.venv`**（项目根，`pyproject.toml` 所在目录）。
- 安装依赖：`uv pip install --python .venv/bin/python -e ".[dev]"`。
- 关键依赖：`nautilus_trader==1.231.0`（含 `[visualization]` → plotly/kaleido）、
  PyYAML、python-dotenv、pytest。
- 运行入口：`.venv/bin/python run.py <cmd>` 或 `make <cmd>`。

## 目录结构

```
vt/
├── pyproject.toml           # 依赖与包元数据（锁定 1.231.0）
├── run.py                   # 最外层启动脚本（python run.py backtest / param / ...）
├── Makefile                 # 常用任务入口
├── AGENTS.md                # 本文档
├── README.md                # 项目简介
├── configs/                 # 外置配置（用户可改，副本被 gitignore）
│   ├── backtest.example.yaml# 模板：拷贝为 backtest.yaml 使用
│   └── param.example.yaml   # 模板：拷贝为 param.yaml 使用
├── .env.example             # 密钥/覆盖模板（复制为 .env）
├── .gitignore               # 忽略 .venv、output/、docs/data/、.env、configs/*.yaml
├── docs/
│   ├── version-notes.md     # Nautilus 1.231.0 实测路径映射与已知坑
│   ├── extending-new-strategy.md  # 如何新增一个策略
│   ├── supported-instruments.md   # 支持的金融产品与配置
│   └── data-ingestion.md   # 如何接入真实数据（CSV/Parquet/Binance）到 catalog
├── ntquant/
│   ├── config.py            # 类型化配置加载（YAML + NTA_* 环境变量覆盖）
│   ├── cli.py               # CLI: backtest / param / report / ingest
│   ├── logging.py           # 统一日志（Python + LoggingConfig）
│   ├── data/
│   │   ├── synthetic.py     # 合成 OHLCV 生成
│   │   ├── catalog.py       # ParquetDataCatalog 封装（写入/读取/合并）
│   │   ├── schema.py        # 统一 OHLCV DataFrame 规范化/列映射
│   │   ├── loaders.py       # 外部数据源注册表（Csv/Binance/占位 providers）
│   │   └── ingest.py        # 取数→规范→wrangler→落库 编排
│   ├── strategies/
│   │   ├── base.py          # BaseStrategyConfig/BaseStrategy 多策略底座
│   │   └── ema_cross.py     # EMA 交叉示例策略
│   ├── backtest/
│   │   ├── runner.py        # 低层 BacktestEngine 运行 + 报表收集
│   │   ├── parameters.py    # 零依赖网格参数扫描 + 结果聚合
│   │   └── instruments.py   # 从配置构建 Instrument/BarType
│   ├── analysis/
│   │   ├── reports.py       # ReportProvider CSV 报表
│   │   ├── stats.py         # 绩效统计（PnL/胜率/夏普等）
│   │   └── visuals.py       # 交互式 HTML tearsheet
│   ├── risk/
│   │   └── __init__.py      # 仓位计算 + RiskEngineConfig 工厂（含 bug 规避）
│   └── live/
│       └── __init__.py      # 实盘占位（phase 2 接入 LiveNode + adapter）
└── tests/                   # pytest 单测（数据/配置/策略/回测/ingest 端到端）
```

## 常用命令

| 命令 | 作用 |
|---|---|
| `make install` | 用 uv 安装本项目 + dev 依赖到 `.venv` |
| `make backtest` | 运行 EMA 交叉回测 + CSV 报表 → `output/` |
| `make param` | 网格参数扫描 → `output/param_results.csv` |
| `make report` | 生成 CSV 报表 + HTML tearsheet `output/tearsheet.html` |
| `make ingest source=csv` | 从外部来源（csv/parquet/binance）拉真实数据落库到 catalog |
| `make test` | `pytest tests/` |
| `make clean` | 清空 `output/`、`docs/data/` |
| `make init` | 从 `.env.example` 复制 `.env` |
| `make init-config` | 从 `configs/*.example.yaml` 复制用户配置到 `configs/*.yaml` |

## 配置约定

- 配置优先级（高→低）：**环境变量 `NTA_*` > 用户 YAML（`configs/<name>.yaml`）>
  `.example` 模板 > dataclass 字段默认值**。
- 仓库只入库 `configs/*.example.yaml` 模板；用户的 `configs/backtest.yaml`、`configs/param.yaml`
  与 `.env` 均被 `.gitignore` 忽略（勿提交个人参数/密钥）。
- 未拷贝用户配置也能运行（自动回落 `.example` 与代码默认值）。

模块内运行示例（在项目根）：

```bash
.venv/bin/python -c "from ntquant.config import load_backtest_config; print(load_backtest_config())"
```

## 版本铁律（务必先读）

官方文档 `nautilustrader.io/docs/latest/` 的导入路径与
`nautilus_trader==1.231.0` **不一致**。**全部以实测路径为准**，完整映射表见
[docs/version-notes.md](docs/version-notes.md)。

- 关键差异：`BacktestEngine` 在 `nautilus_trader.backtest.engine`；`BacktestNode`
  在 `nautilus_trader.backtest.node`；目录/加载在 `nautilus_trader.persistence.*`。
- **每次新增 API 用法先 `import` 验证，勿凭文档记忆。**

## 已知坑（1.231.0 实测，详见 version-notes.md）

- **`strategy_id` 必须传字符串**（如 `"EMA-001"`）；传 `StrategyId(...)` 对象会报
  `name` 类型错。
- **`StrategyConfig` 扩展禁用 `__init__`/`__new__` + `_CUSTOM_FIELDS`**（官方文档示例）；
  1.231.0 报 `Struct types cannot define ...`。正确做法：子类用 **msgspec 类型注解**
  声明自有字段（见 `ntquant/strategies/base.py`）。
- **数量精度**：订单/bar volume 需匹配 `size_precision`。用 `instrument.make_qty(...)`
  规范化（`base.py` 已内置）。
- **报表**：`BacktestEngine` 无 `generate_*_report`；用
  `nautilus_trader.analysis.ReportProvider.generate_*(cache_data)`。
- **RiskEngine**：`RiskEngineConfig` 接入引擎时 `bypass=False` 会触发
  `AttributeError: 'int' object has no attribute 'split'`。默认 `bypass=True` 规避
  （`ntquant/risk/__init__.py`）。
- **数据落库**：`ParquetDataCatalog` **没有** `write_instruments`（文档写法会
  `AttributeError`）；instrument 须随数据用 `write_data([instrument]+bars)` 一起写入。
- **增量合并**：`consolidate_data` 需传 `data_cls`(如 `Bar`) 与 `identifier`(bar_type 字符串)，
  否则 `class_to_filename(None)` 抛 `AttributeError`。
- **Binance interval 推断**：bar_type 形如 `BTCUSDT.BINANCE-1-HOUR-LAST-EXTERNAL`，
  step 与 unit 是两个 `-` 分隔 token，需正则匹配，不能 `split("-")`。
- **真实数据回测**：`data.source != synthetic` 时 `runner` 自动从 catalog 读，需先用
  `make ingest source=<...>` 落库，否则报错。

## 代码风格

- 不加无用注释；公开函数/类用简明 docstring（英文或中文均可）。
- 配置走 `ntquant/config.py` 的类型化加载（YAML + 环境变量）。
- 标的分派：`backtest/instruments.py:make_instrument` 按 `instrument.asset_class`
  构造对应 Nautilus instrument（FX/EQUITY/CRYPTOCURRENCY/FUTURE/INDEX/COMMODITY/CFD）。
  账户 `base_currency` 须与标的结算币种一致，否则 PnL 换算警告。
- 新增匹配通用能力优先下沉到 `strategies/base.py`，示例策略保持薄。
- 新策略需在 `backtest/runner.py` 的 `STRATEGY_CONFIGS` 与 `make_strategy` 两处登记。

## 测试

- `make test` → `pytest tests/`。
- 新策略/runner 必须覆盖关键路径：指标初始化、下单分支、配置加载。
- 用小的 `count`（如 100-300 bar）保证 CI 快速；不要依赖真实网络。

## 输出与安全

- 生成物统一进 `output/`（CSV、HTML tearsheet、日志）。
- 真实密钥只放 `.env`（不入库），仓库不负责任何密钥文件。
